"""多Agent协作服务（执行者 + 监督者）

当工单指派给AI且配置了监督者Agent（supervisor_agent_id）时启用：
  - 执行者Agent（executor，即工单的 assignee_agent）：调用系统工具实际处理工单任务
  - 监督者Agent（supervisor）：审查执行者是否真正执行了任务、执行结果是否满足要求

协作流程：
  执行者执行一轮 → 监督者审查 → 通过则完结 / 不通过则反馈给执行者重新处理
  循环直到验收通过或达到最大协作轮数（默认3轮）。

异步任务（导出/查询/分润/代付）执行完成后，也会由监督者审查执行结果。
"""
import json
import logging
import threading
from datetime import datetime

from app import db
from app.models.ticket import Ticket
from app.models.ai_agent import AiAgent
from app.models.ai_config import AiConfig

logger = logging.getLogger(__name__)

# 最大协作轮数（执行者处理 + 监督者审查 算一轮）
MAX_COLLABORATION_ROUNDS = 3

# 从 ticket_routes 复用状态常量与工具函数（延迟 import 避免循环依赖）
from app.routes.ticket_routes import (
    STATUS_PROCESSING,
    STATUS_PROCESSED,
    STATUS_PENDING_ASSIGNMENT,
    STATUS_PENDING_CONFIRMATION,
    _add_comment,
    _build_ticket_ai_prompt,
)


def _execute_async_for_ticket(action_type, ticket, result, tool_log_text, app):
    """根据 action_type 启动对应的异步任务（延迟 import 避免循环依赖）"""
    from app.routes.ticket_routes import (
        _execute_export_for_ticket,
        _execute_query_for_ticket,
        _execute_profit_share_for_ticket,
        _execute_pay_withdraw_for_ticket,
        _finish_ticket_with_failure,
    )
    if action_type == 'export':
        _execute_export_for_ticket(ticket, result, tool_log_text, app)
    elif action_type == 'query':
        _execute_query_for_ticket(ticket, result, tool_log_text, app)
    elif action_type == 'profit_share':
        _execute_profit_share_for_ticket(ticket, result, tool_log_text, app)
    elif action_type == 'pay_withdraw':
        _execute_pay_withdraw_for_ticket(ticket, result, tool_log_text, app)
    else:
        _finish_ticket_with_failure(ticket, '未知的任务类型，无法执行', tool_log_text)


class MultiAgentService:
    """多Agent协作编排服务"""

    # ── 主入口 ──────────────────────────────────────────────

    @staticmethod
    def process_ticket(ticket_id, app):
        """多agent协作处理工单（后台线程入口）

        执行者 + 监督者协作循环，直到验收通过或达到最大轮数。
        """
        with app.app_context():
            try:
                ticket = Ticket.query.get(ticket_id)
                if not ticket:
                    return

                ticket.status = STATUS_PROCESSING
                ticket.received_at = datetime.utcnow()
                db.session.commit()

                executor = AiAgent.query.get(ticket.assignee_agent_id) if ticket.assignee_agent_id else None
                supervisor = AiAgent.query.get(ticket.supervisor_agent_id) if ticket.supervisor_agent_id else None
                if not supervisor:
                    # 监督者已被删除/禁用，退化为单agent处理
                    logger.warning(f'工单 {ticket.ticket_no} 配置的监督者Agent不存在，退化为单agent处理')
                    MultiAgentService._fallback_to_single_agent(ticket, app)
                    return

                feedback = None
                max_rounds = MultiAgentService._get_max_rounds(ticket)
                for round_no in range(1, max_rounds + 1):
                    ticket.collaboration_rounds = round_no

                    # 1. 执行者执行一轮
                    result = MultiAgentService._executor_tool_loop(ticket, executor, app, feedback)
                    MultiAgentService._log_collaboration(ticket, 'executor', executor.name if executor else 'AI助手', result)

                    if result.get('mode') == 'async':
                        # 异步任务已启动，回调完成后由 review_async_result 继续监督者审查
                        db.session.commit()
                        logger.info(f'工单 {ticket.ticket_no} 执行者触发异步任务，等待完成后监督者审查')
                        return

                    if result.get('mode') == 'pending':
                        # 需确认执行（SQL系统任务/生产代付）
                        if supervisor and supervisor.can_confirm_execution:
                            # 监督者被授权确认执行：由监督者审查并直接确认/拒绝，无需提交者人工介入
                            MultiAgentService._supervisor_confirm_pending(ticket, supervisor, app)
                            logger.info(f'工单 {ticket.ticket_no} 监督者被授权确认执行，已由监督者处理待确认操作')
                            return
                        # 未授权：等待提交者人工确认
                        db.session.commit()
                        logger.info(f'工单 {ticket.ticket_no} 执行者需用户确认，暂停协作')
                        return

                    if not result.get('is_handled'):
                        # 执行者认为无法处理（待人工处理），转待指派，无需监督者审查
                        MultiAgentService._finalize_pending_assignment(ticket, result)
                        return

                    # 2. 监督者审查执行结果
                    approved, feedback, review_summary, score = MultiAgentService._supervisor_review(
                        ticket, supervisor, result
                    )
                    MultiAgentService._log_collaboration(ticket, 'supervisor', supervisor.name, {
                        'approved': approved,
                        'feedback': feedback,
                        'summary': review_summary,
                        'score': score,
                    })
                    ticket.final_score = score
                    db.session.commit()

                    if approved:
                        MultiAgentService._finalize_processed(ticket, review_summary, result)
                        logger.info(f'工单 {ticket.ticket_no} 监督者验收通过（第{round_no}轮，评分{score}），协作完成')
                        return

                    # 不通过，反馈继续下一轮
                    logger.info(f'工单 {ticket.ticket_no} 监督者第{round_no}轮未通过（评分{score}），反馈给执行者继续处理')
                    if round_no >= max_rounds:
                        # 达到最大轮数，强制完结并注明未完全验收
                        MultiAgentService._finalize_processed(
                            ticket,
                            f'（已达最大协作轮数{max_rounds}轮，监督者最后一次评分{score}，反馈如下）\n\n{review_summary}',
                            result,
                            force=True,
                        )
                        return

                logger.info(f'工单 {ticket.ticket_no} 多agent协作结束')
            except Exception as e:
                logger.error(f'工单多agent协作处理失败 ticket_id={ticket_id}: {e}', exc_info=True)
                try:
                    with app.app_context():
                        db.session.rollback()
                        t = Ticket.query.get(ticket_id)
                        if t:
                            t.status = STATUS_PENDING_ASSIGNMENT
                            t.ai_result = f'多Agent协作处理异常: {str(e)}'
                            db.session.commit()
                except Exception:
                    pass

    # ── 执行者工具循环 ───────────────────────────────────────

    @staticmethod
    def _executor_tool_loop(ticket, agent, app, feedback=None):
        """执行者Agent执行一轮工具调用循环

        返回结果字典：
          {'mode': 'done', 'final_content', 'tool_log', 'tool_executed', 'action_triggered', 'is_handled'}
          {'mode': 'async', 'action_type', 'tool_log_text'}
          {'mode': 'pending', 'pending_type', ...}
        """
        from app.services.ai_service import AiService, get_effective_tools

        ai_config = AiConfig.query.filter_by(is_active=True).first()
        if not ai_config:
            raise Exception('未找到可用的AI模型配置')

        system_name = ticket.business_system.name if ticket.business_system else '未指定'
        ticket_system_prompt = _build_ticket_ai_prompt(agent, system_name)

        # 附件清单
        att_lines = ''
        if ticket.attachments:
            att_items = [f'- {a.file_name}（{a.file_size // 1024}KB）' for a in ticket.attachments]
            att_lines = ('\n\n## 工单附件\n提交人随工单上传了以下数据文件（处理人可在工单详情页下载）：\n'
                         + '\n'.join(att_items)
                         + '\n如工单需求依赖附件中的数据（如按Excel主键批量查询），请在结果中说明需使用对应附件执行查询任务。')

        messages = [
            {'role': 'system', 'content': ticket_system_prompt},
            {'role': 'user', 'content': f'## 工单编号: {ticket.ticket_no}\n## 标题: {ticket.title}\n## 涉及系统: {system_name}\n\n## 工单内容:\n{ticket.content}{att_lines}'},
        ]

        # 监督者反馈（第二轮及以后）
        if feedback:
            messages.append({
                'role': 'user',
                'content': (
                    f'## 监督者反馈（请务必根据以下反馈重新处理，不要重复之前的无效操作）\n{feedback}\n\n'
                    f'请重新分析工单需求，调整处理方案，确保最终结果满足提交人的要求。'
                ),
            })

        filtered_tools = get_effective_tools(agent)

        max_rounds = 3
        tool_executed = False
        action_triggered = False
        final_content = ''
        tool_log = []

        for round_idx in range(max_rounds):
            ai_response = AiService.chat_with_failover(
                messages, use_tools=True, tools=filtered_tools, scope='ticket'
            )
            content = ai_response.get('content', '') or ''
            tool_calls = ai_response.get('tool_calls', []) or []
            ticket.accumulate_ai_token_usage(ai_response)

            if not tool_calls:
                final_content = content
                break

            tool_results = []
            pending_system_tasks = []
            pending_pay_withdraw = None

            for tc in tool_calls:
                func_name = tc.get('function', {}).get('name', '')
                func_args = tc.get('function', {}).get('arguments', '')
                logger.info(f'工单{ticket.ticket_no} 执行者调用工具(轮次{round_idx+1}): {func_name}({func_args})')

                result = AiService.execute_tool_call(func_name, func_args, ticket.created_by, agent_id=agent.id if agent else None)
                tool_results.append({
                    'tool_call_id': tc['id'],
                    'name': func_name,
                    'result': result,
                })

                # 生成结果摘要（与单agent逻辑保持一致）
                result_summary = ''
                if isinstance(result, dict):
                    if result.get('error'):
                        result_summary = f"错误: {result['error']}"
                    elif result.get('action_type') == 'export':
                        task_id = result.get('task_id', '')
                        result_summary = f"已创建导出任务(任务ID: {task_id})" if task_id else "导出任务已触发"
                        action_triggered = True
                        tool_executed = True
                    elif result.get('action_type') == 'query':
                        task_id = result.get('task_id', '')
                        result_summary = f"已创建查询任务(任务ID: {task_id})" if task_id else "查询任务已触发"
                        action_triggered = True
                        tool_executed = True
                    elif result.get('action_type') == 'system_task':
                        if result.get('auto_executed'):
                            ai_notes = result.get('ai_notes', '')
                            result_summary = f"系统任务已自动执行: {result.get('mapping_summary', '完成')}"
                            if ai_notes:
                                result_summary = f"{result_summary}\n\n⚠️ 任务执行要点(务必遵守)：{ai_notes}"
                            tool_executed = True
                        else:
                            task_type = result.get('task_type', 'sql')
                            if task_type == 'sql':
                                pending_system_tasks.append({
                                    'func_name': func_name,
                                    'func_args': func_args,
                                    'task_id': result.get('task_id'),
                                    'task_name': result.get('task_name', ''),
                                    'task_type': task_type,
                                    'params_values': result.get('params_values', {}),
                                    'databases': result.get('databases', []),
                                    'database_id': result.get('database_id'),
                                    'description': result.get('description', ''),
                                    'confirm_message': result.get('confirm_message', ''),
                                })
                                result_summary = f"SQL系统任务「{result.get('task_name', '')}」需用户确认后执行"
                            else:
                                task_id = result.get('task_id', '')
                                result_summary = f"已创建系统任务(任务ID: {task_id})" if task_id else "系统任务已触发"
                                action_triggered = True
                                tool_executed = True
                    elif result.get('action_type') == 'lookup':
                        total = result.get('total', 0)
                        result_summary = f"查询到{total}条记录" if total else "未查询到记录"
                        tool_executed = True
                    elif result.get('action_type') == 'profit_share':
                        task_id = result.get('task_id', '')
                        result_summary = f"已创建分润导出任务(任务ID: {task_id})" if task_id else "分润导出已触发"
                        action_triggered = True
                        tool_executed = True
                    elif result.get('action_type') == 'pay_withdraw':
                        env = result.get('environment', 'test')
                        if env == 'pro':
                            pending_pay_withdraw = {
                                'func_name': func_name,
                                'func_args': func_args,
                                'channel': result.get('channel', ''),
                                'channel_name': result.get('channel_name', ''),
                                'interface_type': result.get('interface_type', ''),
                                'environment': env,
                                'file_path': result.get('file_path', ''),
                                'sheet_index': result.get('sheet_index', 0),
                                'sheet_name': result.get('sheet_name', ''),
                                'real_time': result.get('real_time', '是'),
                                'execute_type': result.get('execute_type', '创建代付'),
                                'description': result.get('description', ''),
                                'confirm_message': result.get('confirm_message', ''),
                            }
                            result_summary = f"代付提现「{result.get('channel_name', '')}」生产环境需用户确认后执行"
                        else:
                            result_summary = f"代付提现参数已确认：{result.get('channel_name', result.get('channel', ''))} {result.get('interface_type', '')}"
                            action_triggered = True
                            tool_executed = True
                    elif result.get('total') is not None:
                        result_summary = f"匹配到{result['total']}项"
                    else:
                        result_summary = '已执行'
                else:
                    result_summary = str(result)[:200]

                tool_log.append(f'**调用工具**: `{func_name}` → {result_summary}')

            # 待确认的SQL系统任务
            if pending_system_tasks:
                ticket.set_pending_action({'tasks': pending_system_tasks})
                ticket.status = STATUS_PENDING_CONFIRMATION
                task_lines = []
                for i, t in enumerate(pending_system_tasks, 1):
                    task_lines.append(
                        f"**{i}. {t['task_name']}**\n   参数：{json.dumps(t['params_values'], ensure_ascii=False)}"
                    )
                tasks_text = '\n\n'.join(task_lines)
                ticket.ai_result = (
                    f"AI识别到需要执行数据变更类操作（共{len(pending_system_tasks)}个任务）：\n\n"
                    f"{tasks_text}\n\n"
                    f"⚠️ 此操作会直接影响生产数据，请提交人确认后执行。\n"
                    f"可在下方评论「同意」、「确认执行」或点击「确认执行」按钮继续。"
                )
                if tool_log:
                    tool_log_text = '\n\n'.join(tool_log)
                    ticket.ai_result = f'{ticket.ai_result}\n\n---\n**处理过程：**\n{tool_log_text}'
                _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, f'工单状态已转为「待确认」，等待提交人确认后执行{len(pending_system_tasks)}个数据变更操作', 'status_change', is_ai=True)
                return {'mode': 'pending', 'pending_type': 'system_tasks'}

            # 待确认的生产环境代付提现
            if pending_pay_withdraw:
                ticket.set_pending_action(pending_pay_withdraw)
                ticket.status = STATUS_PENDING_CONFIRMATION
                confirm_msg = pending_pay_withdraw.get('confirm_message', '')
                ticket.ai_result = (
                    f"AI识别到需要执行**生产环境代付提现**操作：\n\n"
                    f"{confirm_msg}\n\n"
                    f"⚠️ 此操作将真实执行代付提现，请提交人确认后执行。\n"
                    f"可在下方评论「同意」、「确认执行」或点击「确认执行」按钮继续。"
                )
                if tool_log:
                    tool_log_text = '\n\n'.join(tool_log)
                    ticket.ai_result = f'{ticket.ai_result}\n\n---\n**处理过程：**\n{tool_log_text}'
                _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, '工单状态已转为「待确认」，等待提交人确认后执行生产环境代付提现', 'status_change', is_ai=True)
                return {'mode': 'pending', 'pending_type': 'pay_withdraw'}

            # 触发操作型工具
            if action_triggered:
                tool_log_text = '\n\n'.join(tool_log) if tool_log else ''

                action_detail = None
                for tr in tool_results:
                    r = tr['result']
                    if isinstance(r, dict):
                        if r.get('action_type') == 'export' and not r.get('error'):
                            action_detail = {'type': 'export', 'result': r}
                            break
                        elif r.get('action_type') == 'query' and not r.get('error'):
                            action_detail = {'type': 'query', 'result': r}
                            break
                        elif r.get('action_type') == 'profit_share' and not r.get('error'):
                            action_detail = {'type': 'profit_share', 'result': r}
                            break
                        elif r.get('action_type') == 'pay_withdraw' and not r.get('error'):
                            action_detail = {'type': 'pay_withdraw', 'result': r}
                            break

                if action_detail:
                    _add_comment(ticket, None, f'AI正在执行任务...\n\n---\n**处理过程：**\n{tool_log_text}', 'ai_process', is_ai=True)
                    db.session.commit()
                    _execute_async_for_ticket(action_detail['type'], ticket, action_detail['result'], tool_log_text, app)
                    return {'mode': 'async', 'action_type': action_detail['type'], 'tool_log_text': tool_log_text}

                # 其他操作型工具，归总回复
                messages.append({'role': 'assistant', 'content': content, 'tool_calls': tool_calls})
                for tr in tool_results:
                    messages.append({'role': 'tool', 'tool_call_id': tr['tool_call_id'], 'content': json.dumps(tr['result'], ensure_ascii=False)})
                try:
                    summary_content, tokens, prompt_tokens, completion_tokens, cache_creation, cache_read, headroom_stats = AiService.chat_with_failover(messages, use_tools=False, scope='ticket')
                    final_content = summary_content or ''
                    ticket.accumulate_ai_token_usage({
                        'tokens': tokens, 'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'cache_creation_tokens': cache_creation,
                        'cache_read_tokens': cache_read,
                        'headroom_stats': headroom_stats,
                    })
                except Exception as se:
                    logger.warning(f'工单{ticket.ticket_no} 执行者归总回复失败: {se}')
                    final_content = '已触发相关任务执行，请到对应模块查看执行结果。'
                break

            # 非操作型工具，继续循环
            messages.append({'role': 'assistant', 'content': content, 'tool_calls': tool_calls})
            for tr in tool_results:
                messages.append({'role': 'tool', 'tool_call_id': tr['tool_call_id'], 'content': json.dumps(tr['result'], ensure_ascii=False)})

            if round_idx == max_rounds - 1:
                try:
                    final_content, tokens, prompt_tokens, completion_tokens, cache_creation, cache_read, headroom_stats = AiService.chat_with_failover(messages, use_tools=False, scope='ticket')
                    final_content = final_content or ''
                    ticket.accumulate_ai_token_usage({
                        'tokens': tokens, 'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'cache_creation_tokens': cache_creation,
                        'cache_read_tokens': cache_read,
                        'headroom_stats': headroom_stats,
                    })
                except Exception as se:
                    logger.warning(f'工单{ticket.ticket_no} 执行者最终回复失败: {se}')
                    final_content = content or '处理完成'
        else:
            if not final_content:
                final_content = content or '处理完成'

        final_content = (final_content or '').strip()
        if not final_content:
            final_content = 'AI已处理，但未返回详细内容。'

        # 判断是否已处理
        if final_content.startswith('【待人工处理】'):
            is_handled = False
            ai_result = final_content[len('【待人工处理】'):].strip()
        elif final_content.startswith('【已处理】'):
            is_handled = True
            ai_result = final_content[len('【已处理】'):].strip()
        elif tool_executed:
            is_handled = True
            ai_result = final_content
        else:
            is_handled = True
            ai_result = final_content

        if tool_log:
            tool_log_text = '\n\n'.join(tool_log)
            ai_result = f'{ai_result}\n\n---\n**处理过程：**\n{tool_log_text}'

        return {
            'mode': 'done',
            'final_content': ai_result,
            'tool_log': tool_log,
            'tool_executed': tool_executed,
            'action_triggered': action_triggered,
            'is_handled': is_handled,
        }

    # ── 监督者审查 ───────────────────────────────────────────

    @staticmethod
    def _build_supervisor_prompt(supervisor):
        """构建监督者系统提示词"""
        base = (
            '你是一个工单质量监督者（Supervisor），负责审查执行者（Executor）处理工单的结果。\n\n'
            '## 你的职责\n'
            '1. 判断执行者是否真正执行了工单要求的任务（是否调用了正确的工具、是否得到了正确的结果）\n'
            '2. 判断执行者的处理结果是否满足提交人的需求，是否存在遗漏、错误或不完整的地方\n'
            '3. 只有在执行结果确实满足工单要求时才验收通过\n\n'
            '## 审查输出格式（严格遵守，按行输出）\n'
            '第一行：如果执行结果满足要求，回复以【验收通过】开头；如果不满足，回复以【需要返工】开头\n'
            '第二行：评分：X（X为0-100的整数，代表对执行结果质量的评分；验收通过通常不低于60分，返工通常低于60分）\n'
            '第三行起：如果验收通过，简述验收结论（用中文）；如果需要返工，详细、具体地说明执行者需要改进或补充的地方，'
            '这些反馈会原样交给执行者重新处理，因此必须可执行、可验证，避免空泛\n\n'
            '## 审查原则\n'
            '- 严格但公正：只对真实存在的缺陷要求返工，不吹毛求疵\n'
            '- 聚焦工单要求：以提交人的原始需求为唯一验收标准\n'
            '- 如果执行者声称已完成但实际只是给出方案、未真正执行任务，应要求返工\n'
            '- 如果执行者确实调用了工具并成功完成任务，应验收通过\n'
        )
        if supervisor and supervisor.system_prompt:
            base = base + '\n## 监督者专属要求\n' + supervisor.system_prompt
        return base

    @staticmethod
    def _parse_score(text):
        """从监督者输出中提取评分（0-100），未提取到返回 None"""
        import re
        if not text:
            return None
        m = re.search(r'评分\s*[:：]\s*(-?\d{1,3})', text)
        if not m:
            return None
        try:
            return max(0, min(100, int(m.group(1))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_max_rounds(ticket):
        """获取工单级配置的最大协作轮数（非法或未配置则用全局默认）"""
        try:
            v = int(ticket.max_collaboration_rounds)
            if 1 <= v <= 20:
                return v
        except (TypeError, ValueError):
            pass
        return MAX_COLLABORATION_ROUNDS

    @staticmethod
    def _supervisor_review(ticket, supervisor, executor_result):
        """监督者审查执行者的处理结果，返回 (approved, feedback, review_summary, score)"""
        from app.services.ai_service import AiService

        system_name = ticket.business_system.name if ticket.business_system else '未指定'
        supervisor_prompt = MultiAgentService._build_supervisor_prompt(supervisor)

        review_messages = [
            {'role': 'system', 'content': supervisor_prompt},
            {'role': 'user', 'content': (
                f'## 工单信息\n'
                f'- 编号: {ticket.ticket_no}\n'
                f'- 标题: {ticket.title}\n'
                f'- 涉及系统: {system_name}\n\n'
                f'## 工单内容\n{ticket.content or ""}\n\n'
                f'## 执行者的处理结果\n{executor_result.get("final_content", "")}\n\n'
                f'## 执行者是否调用过工具\n{"是" if executor_result.get("tool_executed") else "否"}\n\n'
                f'请审查执行者是否真正完成了工单要求，并给出验收结论。'
            )},
        ]

        try:
            content, tokens, prompt_tokens, completion_tokens, cache_creation, cache_read, headroom_stats = AiService.chat_with_failover(
                review_messages, use_tools=False, scope='ticket'
            )
            ticket.accumulate_ai_token_usage({
                'tokens': tokens, 'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'cache_creation_tokens': cache_creation,
                'cache_read_tokens': cache_read,
                'headroom_stats': headroom_stats,
            })
        except Exception as e:
            logger.warning(f'工单 {ticket.ticket_no} 监督者审查失败: {e}')
            # 审查失败时，保守处理：不通过，要求人工介入
            return False, '监督者审查调用失败，请人工核实处理结果。', f'（监督者审查异常：{e}）', None

        review_summary = (content or '').strip()
        if not review_summary:
            return False, '监督者未给出明确结论，请人工核实。', '（监督者无有效输出）', None

        score = MultiAgentService._parse_score(review_summary)

        if review_summary.startswith('【验收通过】'):
            summary = review_summary[len('【验收通过】'):].strip() or review_summary
            return True, '', summary, score
        elif review_summary.startswith('【需要返工】'):
            feedback = review_summary[len('【需要返工】'):].strip() or review_summary
            return False, feedback, review_summary, score
        else:
            # 未按约定格式输出，保守处理为需要返工
            return False, review_summary, review_summary, score

    # ── 监督者确认执行待确认操作 ──────────────────────────────

    @staticmethod
    def _build_pending_description(ticket):
        """把待确认操作(pending_action)转成可读文本，供监督者审查决策"""
        pending_action = ticket.get_pending_action()
        if not pending_action:
            return '（无待确认操作信息）'

        if 'tasks' in pending_action:
            tasks = pending_action.get('tasks') or []
            lines = [f'待执行的数据变更类SQL系统任务（共{len(tasks)}个）：']
            for i, t in enumerate(tasks, 1):
                lines.append(f'  {i}. {t.get("task_name", "未命名任务")}')
                params = t.get('params_values', {})
                if params:
                    lines.append(f'     参数：{json.dumps(params, ensure_ascii=False)}')
                if t.get('description'):
                    lines.append(f'     说明：{t["description"]}')
                if t.get('confirm_message'):
                    lines.append(f'     确认提示：{t["confirm_message"]}')
            return '\n'.join(lines)

        # 生产环境代付提现
        channel_name = pending_action.get('channel_name', pending_action.get('channel', ''))
        lines = [
            '待执行的生产环境代付提现操作：',
            f'  - 渠道：{channel_name}',
            f'  - 接口类型：{pending_action.get("interface_type", "")}',
            f'  - 环境：{pending_action.get("environment", "")}',
            f'  - 实时代付：{pending_action.get("real_time", "")}',
            f'  - 执行类型：{pending_action.get("execute_type", "")}',
        ]
        if pending_action.get('description'):
            lines.append(f'  - 说明：{pending_action["description"]}')
        if pending_action.get('confirm_message'):
            lines.append(f'  - 确认提示：{pending_action["confirm_message"]}')
        return '\n'.join(lines)

    @staticmethod
    def _supervisor_confirm_pending(ticket, supervisor, app):
        """监督者被授权确认执行时，审查待确认操作并决定确认/拒绝

        确认 → 转 processing 并异步执行 pending_action；拒绝 → 转 pending_assignment。
        """
        from app.services.ai_service import AiService

        system_name = ticket.business_system.name if ticket.business_system else '未指定'
        pending_desc = MultiAgentService._build_pending_description(ticket)

        base_prompt = (
            '你是一个工单质量监督者（Supervisor），现在执行者处理工单时识别到一项需要确认后才能执行的操作，'
            '你已被授权直接确认执行（无需提交者人工介入）。请评估该操作并决定是否执行。\n\n'
            '## 决策输出格式（严格遵守）\n'
            '- 如果该操作符合工单需求且安全合理，应执行：回复以【确认执行】开头，随后简述理由\n'
            '- 如果该操作存在风险、不符合工单要求或不应执行：回复以【拒绝执行】开头，随后说明原因\n\n'
            '## 决策原则\n'
            '- 以提交人的原始需求为唯一依据，操作必须确实服务于工单目标\n'
            '- 对涉及生产数据/真实资金的变更操作保持审慎，但不因过度保守而拒绝合理的操作\n'
        )
        if supervisor and supervisor.system_prompt:
            base_prompt = base_prompt + '\n## 监督者专属要求\n' + supervisor.system_prompt

        messages = [
            {'role': 'system', 'content': base_prompt},
            {'role': 'user', 'content': (
                f'## 工单信息\n'
                f'- 编号: {ticket.ticket_no}\n'
                f'- 标题: {ticket.title}\n'
                f'- 涉及系统: {system_name}\n\n'
                f'## 工单内容\n{ticket.content or ""}\n\n'
                f'## 待确认的操作\n{pending_desc}\n\n'
                f'请评估并决定是否确认执行。'
            )},
        ]

        try:
            content, tokens, prompt_tokens, completion_tokens, cache_creation, cache_read, headroom_stats = AiService.chat_with_failover(
                messages, use_tools=False, scope='ticket'
            )
            ticket.accumulate_ai_token_usage({
                'tokens': tokens, 'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'cache_creation_tokens': cache_creation,
                'cache_read_tokens': cache_read,
                'headroom_stats': headroom_stats,
            })
        except Exception as e:
            logger.warning(f'工单 {ticket.ticket_no} 监督者确认决策失败: {e}')
            # 审查失败保守处理：拒绝执行，转待指派，由人工介入
            MultiAgentService._reject_pending_by_supervisor(ticket, f'（监督者决策异常：{e}）')
            return

        decision = (content or '').strip()
        if not decision:
            decision = '（监督者未给出有效决策）'

        if decision.startswith('【确认执行】'):
            reason = decision[len('【确认执行】'):].strip() or decision
            MultiAgentService._log_collaboration(ticket, 'supervisor', supervisor.name, {
                'decision': 'confirm', 'summary': reason,
            })
            # 监督者确认执行：转 processing 并异步执行待确认操作
            ticket.status = STATUS_PROCESSING
            _add_comment(ticket, None, f'监督者已确认执行该操作：{reason}', 'status_change', is_ai=True)
            db.session.commit()
            from app.routes.ticket_routes import _execute_pending_action_async, _ticket_ai_threads
            t = threading.Thread(target=_execute_pending_action_async, args=(ticket.id, app), daemon=True)
            _ticket_ai_threads[ticket.id] = t
            t.start()
            logger.info(f'工单 {ticket.ticket_no} 监督者确认执行待确认操作，已异步执行')
        else:
            # 拒绝执行（含【拒绝执行】或未按格式输出，保守拒绝）
            MultiAgentService._log_collaboration(ticket, 'supervisor', supervisor.name, {
                'decision': 'reject', 'summary': decision,
            })
            MultiAgentService._reject_pending_by_supervisor(ticket, decision)

    @staticmethod
    def _reject_pending_by_supervisor(ticket, decision):
        """监督者拒绝执行待确认操作：转待指派并记录原因"""
        ticket.ai_result = f'监督者拒绝执行该操作：{decision}'
        ticket.status = STATUS_PENDING_ASSIGNMENT
        ticket.clear_pending_action()
        _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
        _add_comment(ticket, None, '监督者拒绝执行该操作，工单已转为「待指派」，请提交人重新指派或人工介入', 'status_change', is_ai=True)
        db.session.commit()
        logger.info(f'工单 {ticket.ticket_no} 监督者拒绝执行待确认操作')

    # ── 异步任务完成后的监督者审查 ────────────────────────────

    @staticmethod
    def review_async_result(ticket_id, executor_summary, app):
        """异步任务（导出/查询/分润/代付）完成后，监督者审查执行结果

        由 ticket_routes.py 中各异步任务的 on_complete 回调在设置 processed 前调用。
        注意：复用调用者已有的 app context（异步回调已在后台线程的 app context 中），
        避免嵌套 app_context 导致 Flask-SQLAlchemy session 隔离、评论丢失。
        """
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                return False
            if not ticket.supervisor_agent_id:
                # 无监督者，保持原逻辑（由回调继续处理）
                return False

            supervisor = AiAgent.query.get(ticket.supervisor_agent_id)
            if not supervisor:
                return False

            # 监督者审查属于执行者刚完成的那一轮，不递增轮数
            round_no = ticket.collaboration_rounds or 1
            max_rounds = MultiAgentService._get_max_rounds(ticket)

            result = {
                'mode': 'done',
                'final_content': executor_summary or ticket.ai_result or '',
                'tool_log': [],
                'tool_executed': True,
                'action_triggered': True,
                'is_handled': True,
            }
            approved, feedback, review_summary, score = MultiAgentService._supervisor_review(ticket, supervisor, result)
            MultiAgentService._log_collaboration(ticket, 'supervisor', supervisor.name, {
                'approved': approved,
                'feedback': feedback,
                'summary': review_summary,
                'score': score,
            })
            ticket.final_score = score

            if approved:
                MultiAgentService._finalize_processed(ticket, review_summary, result)
                logger.info(f'工单 {ticket.ticket_no} 异步任务完成后监督者验收通过（评分{score}）')
                return True

            # 不通过
            if round_no >= max_rounds:
                MultiAgentService._finalize_processed(
                    ticket,
                    f'（已达最大协作轮数{max_rounds}轮，监督者最后一次评分{score}，反馈如下）\n\n{review_summary}',
                    result,
                    force=True,
                )
                return True

            # 触发执行者重新处理（带反馈）
            db.session.commit()
            MultiAgentService._trigger_executor_retry(ticket_id, feedback, app)
            return True
        except Exception as e:
            logger.error(f'工单{ticket_id}异步任务完成后监督者审查异常: {e}', exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            return False

    @staticmethod
    def _trigger_executor_retry(ticket_id, feedback, app):
        """后台线程：带着监督者反馈重新触发执行者处理"""
        def _run():
            with app.app_context():
                try:
                    ticket = Ticket.query.get(ticket_id)
                    if not ticket:
                        return
                    executor = AiAgent.query.get(ticket.assignee_agent_id) if ticket.assignee_agent_id else None
                    supervisor = AiAgent.query.get(ticket.supervisor_agent_id) if ticket.supervisor_agent_id else None
                    # 进入新一轮协作：递增轮数
                    ticket.collaboration_rounds = (ticket.collaboration_rounds or 0) + 1
                    ticket.status = STATUS_PROCESSING
                    db.session.commit()

                    # 直接运行执行者工具循环（带反馈），随后继续监督者审查
                    result = MultiAgentService._executor_tool_loop(ticket, executor, app, feedback)
                    MultiAgentService._log_collaboration(ticket, 'executor', executor.name if executor else 'AI助手', result)

                    if result.get('mode') == 'async':
                        db.session.commit()
                        return
                    if result.get('mode') == 'pending':
                        # 需确认执行（SQL系统任务/生产代付）
                        if supervisor and supervisor.can_confirm_execution:
                            # 监督者被授权确认执行：由监督者审查并直接确认/拒绝
                            MultiAgentService._supervisor_confirm_pending(ticket, supervisor, app)
                            return
                        db.session.commit()
                        return
                    if not result.get('is_handled'):
                        MultiAgentService._finalize_pending_assignment(ticket, result)
                        return

                    if not supervisor:
                        MultiAgentService._finalize_processed(ticket, result.get('final_content', ''), result)
                        return

                    approved, feedback2, review_summary, score = MultiAgentService._supervisor_review(ticket, supervisor, result)
                    MultiAgentService._log_collaboration(ticket, 'supervisor', supervisor.name, {
                        'approved': approved, 'feedback': feedback2, 'summary': review_summary, 'score': score,
                    })
                    ticket.final_score = score

                    if approved:
                        MultiAgentService._finalize_processed(ticket, review_summary, result)
                    elif (ticket.collaboration_rounds or 0) >= MultiAgentService._get_max_rounds(ticket):
                        max_rounds = MultiAgentService._get_max_rounds(ticket)
                        MultiAgentService._finalize_processed(
                            ticket,
                            f'（已达最大协作轮数{max_rounds}轮，监督者最后一次评分{score}，反馈如下）\n\n{review_summary}',
                            result,
                            force=True,
                        )
                    else:
                        # 继续下一轮协作（递归调用，下一轮会再递增轮数）
                        db.session.commit()
                        MultiAgentService._trigger_executor_retry(ticket_id, feedback2, app)
                        return
                    db.session.commit()
                except Exception as e:
                    logger.error(f'工单{ticket_id}执行者重试异常: {e}', exc_info=True)
                    try:
                        db.session.rollback()
                        t = Ticket.query.get(ticket_id)
                        if t:
                            t.status = STATUS_PENDING_ASSIGNMENT
                            t.ai_result = f'多Agent协作重试异常: {str(e)}'
                            db.session.commit()
                    except Exception:
                        pass

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    # ── 完结处理 ─────────────────────────────────────────────

    @staticmethod
    def _finalize_processed(ticket, review_summary, executor_result, force=False):
        """标记工单已处理（含监督者验收结论）"""
        base_result = executor_result.get('final_content', '') if executor_result else ''
        if review_summary:
            if force:
                ticket.ai_result = f'{base_result}\n\n---\n**监督者审查（未完全验收）**\n{review_summary}'
            else:
                ticket.ai_result = f'{base_result}\n\n---\n**监督者验收**\n{review_summary}'
        else:
            ticket.ai_result = base_result

        ticket.status = STATUS_PROCESSED
        ticket.processed_at = datetime.utcnow()
        _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
        _add_comment(ticket, None, 'AI已完成处理并通过监督者验收，等待提交人核实', 'status_change', is_ai=True)
        db.session.commit()

    @staticmethod
    def _finalize_pending_assignment(ticket, executor_result):
        """执行者无法处理，转待指派"""
        ticket.ai_result = executor_result.get('final_content', '') if executor_result else ''
        ticket.status = STATUS_PENDING_ASSIGNMENT
        _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
        _add_comment(ticket, None, 'AI无法直接处理此工单，状态已转为「待指派」，请提交人重新指派给具体的人来人工介入', 'status_change', is_ai=True)
        db.session.commit()

    @staticmethod
    def _log_collaboration(ticket, role, agent_name, result):
        """追加一条协作日志"""
        entry = {
            'round': ticket.collaboration_rounds or 1,
            'role': role,
            'agent_name': agent_name or '',
            'created_at': datetime.utcnow().isoformat(),
        }
        if role == 'executor':
            if isinstance(result, dict):
                entry['mode'] = result.get('mode')
                entry['summary'] = (result.get('final_content') or '')[:500]
                entry['tool_executed'] = bool(result.get('tool_executed'))
        else:
            if isinstance(result, dict):
                if result.get('decision') is not None:
                    # 确认决策（confirm/reject），非验收审查
                    entry['decision'] = result.get('decision')
                    entry['approved'] = None
                else:
                    entry['approved'] = bool(result.get('approved'))
                entry['summary'] = (result.get('summary') or '')[:500]
                if result.get('score') is not None:
                    entry['score'] = result.get('score')
        ticket.append_collaboration_log(entry)

    @staticmethod
    def _fallback_to_single_agent(ticket, app):
        """监督者缺失时退化为单agent处理"""
        from app.routes.ticket_routes import _process_ticket_with_ai_async
        # 清空监督者配置，避免再次进入多agent协作造成无限循环
        ticket.supervisor_agent_id = None
        db.session.commit()
        _process_ticket_with_ai_async(ticket.id, app)
