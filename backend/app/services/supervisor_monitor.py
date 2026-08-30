"""监督者监控调度器

后台线程定期检查并处理以下场景：
1. 智能重试：检测 processing 状态超时的工单，由监督者评估是否重试
2. 自动验收：工单变为 processed 后，由监督者自动验收并决定是否结束
"""
import logging
import threading
import time
from datetime import datetime, timedelta

from app import db

logger = logging.getLogger(__name__)

_monitor_thread = None
_monitor_lock = threading.Lock()
_running = False

# 处理中超时阈值（秒），超过此时间未更新视为卡住
PROCESSING_TIMEOUT_SECONDS = 10 * 60  # 10分钟
# 检查间隔（秒）
CHECK_INTERVAL_SECONDS = 30


def start_supervisor_monitor(app):
    """启动监督者监控调度器"""
    global _monitor_thread, _running
    with _monitor_lock:
        if _monitor_thread and _monitor_thread.is_alive():
            return
        _running = True
        _monitor_thread = threading.Thread(
            target=_monitor_loop,
            args=(app,),
            daemon=True,
            name='supervisor-monitor'
        )
        _monitor_thread.start()
        logger.info('监督者监控调度器已启动')


def stop_supervisor_monitor():
    """停止调度器"""
    global _running
    _running = False


def _monitor_loop(app):
    """主循环：定期检查"""
    while _running:
        try:
            _check_stuck_processing(app)
        except Exception as e:
            logger.error(f'监督者监控调度器异常: {e}', exc_info=True)
        time.sleep(CHECK_INTERVAL_SECONDS)


def _check_stuck_processing(app):
    """检查 processing 状态超时的工单，由授权监督者评估是否重试"""
    with app.app_context():
        from app.models.ticket import Ticket
        from app.models.ai_agent import AiAgent

        timeout_threshold = datetime.utcnow() - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)

        # 查找超时的 processing 工单（有监督者且监督者授权重试）
        stuck_tickets = Ticket.query.filter(
            Ticket.status == 'processing',
            Ticket.assignee_type == 'ai',
            Ticket.supervisor_agent_id.isnot(None),
            db.or_(
                Ticket.last_activity_at < timeout_threshold,
                db.and_(Ticket.last_activity_at.is_(None), Ticket.received_at < timeout_threshold)
            )
        ).all()

        if not stuck_tickets:
            return

        for ticket in stuck_tickets:
            supervisor = AiAgent.query.get(ticket.supervisor_agent_id)
            if not supervisor or not supervisor.is_active or not supervisor.can_retry_processing:
                continue

            logger.info(f'工单 {ticket.ticket_no} processing超时({PROCESSING_TIMEOUT_SECONDS}s)，监督者评估是否重试')
            _supervisor_evaluate_retry(ticket, supervisor, app)


def _supervisor_evaluate_retry(ticket, supervisor, app):
    """监督者评估卡住的工单是否需要重试"""
    from app.services.ai_service import AiService
    from app.routes.ticket_routes import _add_comment, STATUS_PROCESSING, _trigger_ai_processing

    prompt = (
        '你是一个工单质量监督者（Supervisor），现在有一笔工单在AI处理过程中疑似中断（处理时间过长且无进展），'
        '你需要评估是否应该重新触发AI处理。\n\n'
        '## 评估输出格式（严格遵守）\n'
        '- 如果应该重试（可能是网络抖动、服务器临时故障等）：回复以【重试处理】开头，简述原因\n'
        '- 如果不应该重试（如工单内容本身有问题、重复重试无意义等）：回复以【放弃重试】开头，说明原因\n\n'
        '## 评估原则\n'
        '- 如果工单之前没有任何处理记录（无评论、无工具调用日志），很可能是首次处理就中断了，应重试\n'
        '- 如果工单之前已有部分处理结果但中途失败，可以重试让执行者继续\n'
        '- 如果工单已经重试过多次仍然失败，应放弃重试，由人工介入\n'
    )
    if supervisor.system_prompt:
        prompt += '\n## 监督者专属要求\n' + supervisor.system_prompt

    # 收集工单当前状态信息
    comments = [c.content or '' for c in (ticket.comments or [])[:5]]
    recent_comments = '\n'.join(comments) if comments else '（无评论记录）'

    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': (
            f'## 工单信息\n'
            f'- 编号: {ticket.ticket_no}\n'
            f'- 标题: {ticket.title}\n'
            f'- 状态: processing（已超时）\n'
            f'- 协作轮次: {ticket.collaboration_rounds or 0}\n'
            f'- 最后活动: {ticket.last_activity_at or ticket.received_at or "未知"}\n\n'
            f'## 工单内容\n{ticket.content or ""}\n\n'
            f'## 最近评论/处理记录\n{recent_comments}\n\n'
            f'## AI处理结果（如有）\n{ticket.ai_result or "（无）"}\n\n'
            f'请评估是否应该重试AI处理。'
        )},
    ]

    try:
        content, tokens, p_tokens, c_tokens, cache_create, cache_read, headroom = AiService.chat_with_failover(
            messages, use_tools=False, scope='ticket'
        )
        ticket.accumulate_ai_token_usage({
            'tokens': tokens, 'prompt_tokens': p_tokens, 'completion_tokens': c_tokens,
            'cache_creation_tokens': cache_create, 'cache_read_tokens': cache_read, 'headroom_stats': headroom,
        })
    except Exception as e:
        logger.warning(f'工单 {ticket.ticket_no} 监督者重试评估失败: {e}')
        return

    decision = (content or '').strip()
    if decision.startswith('【重试处理】'):
        reason = decision[len('【重试处理】'):].strip() or decision
        logger.info(f'工单 {ticket.ticket_no} 监督者决定重试: {reason}')
        ticket.last_activity_at = datetime.utcnow()
        _add_comment(ticket, None, f'监督者检测到工单处理超时，决定重新触发AI处理：{reason}', 'status_change', is_ai=True)
        db.session.commit()
        _trigger_ai_processing(ticket)
    elif decision.startswith('【放弃重试】'):
        reason = decision[len('【放弃重试】'):].strip() or decision
        logger.info(f'工单 {ticket.ticket_no} 监督者决定放弃重试: {reason}')
        ticket.last_activity_at = datetime.utcnow()
        _add_comment(ticket, None, f'监督者检测到工单处理超时，决定放弃重试：{reason}，请人工介入', 'status_change', is_ai=True)
        ticket.status = 'pending_assignment'
        db.session.commit()
    else:
        # 未按格式输出，保守处理：记录但不操作
        logger.warning(f'工单 {ticket.ticket_no} 监督者重试评估输出格式异常: {decision[:100]}')
        ticket.last_activity_at = datetime.utcnow()
        db.session.commit()


def trigger_auto_close(ticket_id, app):
    """工单变为 processed 后，由授权监督者自动验收并决定是否结束

    在独立线程中运行，不阻塞调用方。
    """
    def _run():
        with app.app_context():
            _do_auto_close(ticket_id, app)

    t = threading.Thread(target=_run, daemon=True, name=f'auto-close-{ticket_id}')
    t.start()


def trigger_supervisor_evaluate_before_retry(ticket_id, app):
    """在重试/重新发起/重新指派前，让监督者评估当前工单执行状态

    评估结果：
    - 已执行完成，需要验收 → 触发监督者验收
    - 有遗漏/未完成，需要补充执行 → 返回反馈供执行者使用
    - 无法评估 → 返回 None，让执行者正常处理

    返回：(need_execute, feedback)
    - need_execute=True, feedback=反馈内容：需要执行者补充处理
    - need_execute=False, feedback=None：已执行完成，已触发验收
    - need_execute=True, feedback=None：无法评估，执行者正常处理
    """
    try:
        from app.models.ticket import Ticket
        from app.models.ai_agent import AiAgent
        from app.services.ai_service import AiService
        from app.routes.ticket_routes import _add_comment

        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return True, None
        if not ticket.supervisor_agent_id:
            return True, None

        supervisor = AiAgent.query.get(ticket.supervisor_agent_id)
        if not supervisor or not supervisor.is_active:
            return True, None

        # 检查是否有历史执行记录
        has_history = False
        history_text = ''

        # 检查 ai_result
        if ticket.ai_result and len(ticket.ai_result.strip()) > 10:
            has_history = True
            history_text += f'## 上次处理结果\n{ticket.ai_result}\n\n'

        # 检查评论记录
        comments = ticket.comments or []
        if len(comments) > 1:
            has_history = True
            history_text += '## 历史评论记录\n'
            for c in comments[-5:]:  # 只看最近5条
                role = 'AI' if c.is_ai else '用户'
                content = (c.content or '').strip()
                if content:
                    history_text += f'[{c.action}] {role}: {content[:200]}\n\n'

        if not has_history:
            # 没有历史记录，执行者正常处理
            return True, None

        logger.info(f'工单 {ticket.ticket_no} 检测到历史执行记录，监督者评估执行状态')

        prompt = (
            '你是一个工单质量监督者（Supervisor），现在工单需要重新处理（可能是重试、重新发起或重新指派）。'
            '你需要评估工单当前的执行状态，判断是否需要补充执行遗漏的任务。\n\n'
            '## 评估输出格式（严格遵守）\n'
            '- 如果工单已经执行完成，只需要验收：回复以【已执行完成，需要验收】开头\n'
            '- 如果工单有遗漏任务需要补充执行：回复以【需要补充执行】开头，随后详细说明哪些任务已经执行完成，哪些任务还需要补充执行\n\n'
            '## 评估原则\n'
            '- 仔细对比工单需求和执行记录，判断执行是否完整覆盖\n'
            '- 如果执行记录显示任务成功且参数覆盖了工单需求的所有数据项，应判定为已执行完成\n'
            '- 如果有部分任务未执行或执行失败，应判定为需要补充执行，并明确指出需要补充的内容\n'
        )
        if supervisor.system_prompt:
            prompt += '\n## 监督者专属要求\n' + supervisor.system_prompt

        messages = [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': (
                f'## 工单信息\n'
                f'- 编号: {ticket.ticket_no}\n'
                f'- 标题: {ticket.title}\n\n'
                f'## 工单内容（原始需求）\n{ticket.content or ""}\n\n'
                f'{history_text}'
                f'请评估当前执行状态，判断是否需要补充执行。'
            )},
        ]

        content, tokens, p_tokens, c_tokens, cache_create, cache_read, headroom = AiService.chat_with_failover(
            messages, use_tools=False, scope='ticket'
        )
        ticket.accumulate_ai_token_usage({
            'tokens': tokens, 'prompt_tokens': p_tokens, 'completion_tokens': c_tokens,
            'cache_creation_tokens': cache_create, 'cache_read_tokens': cache_read, 'headroom_stats': headroom,
        })

        decision = (content or '').strip()
        logger.info(f'工单 {ticket.ticket_no} 监督者评估结果: {decision[:100]}')

        if '已执行完成' in decision or '需要验收' in decision:
            # 已执行完成，直接触发验收
            logger.info(f'工单 {ticket.ticket_no} 监督者判定已执行完成，触发验收')
            ticket.status = 'processed'
            ticket.processed_at = datetime.utcnow()
            ticket.last_activity_at = datetime.utcnow()
            _add_comment(ticket, None, f'📋 监督者评估：工单已执行完成，直接进入验收\n\n{decision}', 'status_change', is_ai=True)
            db.session.commit()
            trigger_auto_close(ticket.id, app)
            return False, None
        elif '需要补充执行' in decision:
            # 有遗漏，返回反馈供执行者使用
            feedback = decision
            if decision.startswith('【需要补充执行】'):
                feedback = decision[len('【需要补充执行】'):].strip() or decision
            logger.info(f'工单 {ticket.ticket_no} 监督者判定需要补充执行')
            _add_comment(ticket, None, f'📋 监督者评估：工单有遗漏任务需要补充执行\n\n{decision}', 'status_change', is_ai=True)
            db.session.commit()
            return True, feedback
        else:
            # 无法判断，执行者正常处理
            logger.info(f'工单 {ticket.ticket_no} 监督者无法判断执行状态，执行者正常处理')
            return True, None

    except Exception as e:
        logger.warning(f'工单{ticket_id}监督者评估失败: {e}')
        return True, None


def _trigger_executor_retry_with_feedback(ticket_id, feedback, app):
    """监督者验收不通过后，触发执行者补充处理

    流程：执行者处理（带反馈） → 完成后再次触发监督者验收
    """
    def _run():
        with app.app_context():
            try:
                from app.models.ticket import Ticket
                from app.services.multi_agent_service import MultiAgentService
                from app.routes.ticket_routes import _add_comment, _build_ticket_ai_prompt, STATUS_PROCESSING, STATUS_PROCESSED
                from app.models.ai_config import AiConfig
                from app.services.ai_service import AiService, get_effective_tools
                
                ticket = Ticket.query.get(ticket_id)
                if not ticket:
                    return
                
                # 记录监督者反馈到评论区
                _add_comment(ticket, None, f'📋 监督者反馈（需补充处理）：\n\n{feedback}', 'ai_process', is_ai=True)
                ticket.status = STATUS_PROCESSING
                ticket.last_activity_at = datetime.utcnow()
                db.session.commit()
                
                logger.info(f'工单 {ticket.ticket_no} 触发执行者补充处理（第{ticket.collaboration_rounds}轮）')
                
                # 直接调用执行者工具循环（不走 _process_ticket_with_ai_async，避免多agent协作）
                executor = AiAgent.query.get(ticket.assignee_agent_id) if ticket.assignee_agent_id else None
                ai_config = AiConfig.query.filter_by(is_active=True).first()
                
                if not ai_config:
                    logger.error(f'工单 {ticket.ticket_no} 未找到可用的AI模型配置')
                    ticket.status = 'pending_assignment'
                    ticket.ai_result = '未找到可用的AI模型配置'
                    db.session.commit()
                    return
                
                # 构建执行者消息（带监督者反馈）
                system_name = ticket.business_system.name if ticket.business_system else '未指定'
                ticket_system_prompt = _build_ticket_ai_prompt(executor, system_name)
                
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
                    {'role': 'user', 'content': f'## 监督者反馈（请务必根据以下反馈补充处理）\n{feedback}\n\n请根据以上反馈，补充处理遗漏的任务，确保完整覆盖工单需求。'},
                ]
                
                # 执行者工具循环（简化版，只执行一轮）
                filtered_tools = get_effective_tools(executor)
                tool_executed = False
                action_triggered = False
                final_content = ''
                tool_log = []
                
                ai_response = AiService.chat_with_failover(messages, use_tools=True, tools=filtered_tools, scope='ticket')
                content = ai_response.get('content', '') or ''
                tool_calls = ai_response.get('tool_calls', []) or []
                ticket.accumulate_ai_token_usage(ai_response)
                
                if tool_calls:
                    tool_results = []
                    for tc in tool_calls:
                        func_name = tc.get('function', {}).get('name', '')
                        func_args = tc.get('function', {}).get('arguments', '')
                        logger.info(f'工单{ticket.ticket_no} 执行者补充处理调用工具: {func_name}')
                        
                        result = AiService.execute_tool_call(func_name, func_args, ticket.created_by, agent_id=executor.id if executor else None)
                        tool_results.append({'tool_call_id': tc['id'], 'name': func_name, 'result': result})
                        
                        # 生成结果摘要
                        if isinstance(result, dict):
                            if result.get('error'):
                                tool_log.append(f'**调用工具**: `{func_name}` → 错误: {result["error"]}')
                            elif result.get('action_type') in ('export', 'query', 'profit_share', 'pay_withdraw'):
                                action_triggered = True
                                tool_executed = True
                                tool_log.append(f'**调用工具**: `{func_name}` → 已触发任务')
                            else:
                                tool_executed = True
                                tool_log.append(f'**调用工具**: `{func_name}` → 已执行')
                    
                    # 追加工具结果到消息
                    messages.append({'role': 'assistant', 'content': content, 'tool_calls': tool_calls})
                    for tr in tool_results:
                        messages.append({'role': 'tool', 'tool_call_id': tr['tool_call_id'], 'content': json.dumps(tr['result'], ensure_ascii=False)})
                    
                    # 获取AI总结
                    try:
                        summary_content, tokens, p_tokens, c_tokens, cache_create, cache_read, headroom = AiService.chat_with_failover(messages, use_tools=False, scope='ticket')
                        final_content = summary_content or ''
                        ticket.accumulate_ai_token_usage({
                            'tokens': tokens, 'prompt_tokens': p_tokens, 'completion_tokens': c_tokens,
                            'cache_creation_tokens': cache_create, 'cache_read_tokens': cache_read, 'headroom_stats': headroom,
                        })
                    except Exception as se:
                        logger.warning(f'工单{ticket.ticket_no} 执行者补充处理归总失败: {se}')
                        final_content = content or '补充处理完成'
                else:
                    final_content = content
                
                # 设置工单状态
                final_content = (final_content or '').strip() or '执行者已补充处理'
                if tool_log:
                    tool_log_text = '\n\n'.join(tool_log)
                    ticket.ai_result = f'{final_content}\n\n---\n**补充处理过程：**\n{tool_log_text}'
                else:
                    ticket.ai_result = final_content
                
                ticket.status = STATUS_PROCESSED
                ticket.processed_at = datetime.utcnow()
                ticket.last_activity_at = datetime.utcnow()
                _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, '执行者补充处理完成，等待监督者验收', 'status_change', is_ai=True)
                db.session.commit()
                
                logger.info(f'工单 {ticket.ticket_no} 执行者补充处理完成，触发监督者验收')
                
                # 触发监督者验收
                trigger_auto_close(ticket.id, app)
                
            except Exception as e:
                logger.error(f'工单{ticket_id}执行者补充处理失败: {e}', exc_info=True)
                try:
                    with app.app_context():
                        db.session.rollback()
                        ticket = Ticket.query.get(ticket_id)
                        if ticket:
                            ticket.status = 'pending_assignment'
                            ticket.ai_result = f'执行者补充处理异常: {str(e)}'
                            db.session.commit()
                except Exception:
                    pass
    
    t = threading.Thread(target=_run, daemon=True, name=f'executor-retry-{ticket_id}')
    t.start()


def _do_auto_close(ticket_id, app):
    """监督者自动验收已处理工单，决定是否结束"""
    from app.models.ticket import Ticket
    from app.models.ai_agent import AiAgent
    from app.services.ai_service import AiService
    from app.routes.ticket_routes import _add_comment

    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return
    if ticket.status != 'processed':
        return  # 状态已变化，跳过
    if not ticket.supervisor_agent_id:
        return

    supervisor = AiAgent.query.get(ticket.supervisor_agent_id)
    if not supervisor or not supervisor.is_active or not supervisor.can_close_ticket:
        return

    logger.info(f'工单 {ticket.ticket_no} 监督者自动验收开始')

    # 收集完整的执行记录（评论区）
    comments_text = ''
    for c in (ticket.comments or []):
        role = 'AI' if c.is_ai else '用户'
        action = c.action or 'comment'
        content = (c.content or '').strip()
        if content:
            comments_text += f'[{action}] {role}: {content}\n\n'

    prompt = (
        '你是一个工单质量监督者（Supervisor），执行者已完成工单处理（工单状态为「已处理」），'
        '你需要最终验收并决定是否结束此工单。\n\n'
        '## 验收输出格式（严格遵守，按行输出）\n'
        '第一行：\n'
        '- 如果工单处理结果满足提交人要求，应结束：回复以【验收通过，结束工单】开头\n'
        '- 如果工单处理结果仍有问题，不应结束：回复以【验收不通过】开头\n'
        '第二行：综合评分：X（0-100整数，综合考虑执行质量、完整性、协作过程）\n'
        '第三行起：简述验收结论或不通过原因\n\n'
        '## 综合评分标准\n'
        '基础分80分，根据以下因素调整：\n'
        '- 执行完整性：所有需求数据项是否都被处理（缺失一项扣10-20分）\n'
        '- 执行质量：任务是否成功完成、参数是否正确（错误扣20-30分）\n'
        '- 协作效率：是否一次通过（每返工一轮扣5分，最低扣到40分）\n'
        '- 结果可验证性：执行记录是否清晰可查（模糊扣5-10分）\n\n'
        '## 验收原则\n'
        '- 以提交人的原始需求为唯一验收标准\n'
        '- **仔细阅读执行记录**：不要简单比较任务数量，要查看每个任务的实际执行内容和参数。一个任务可能批量处理多个数据项（如一个任务包含多个SN、多个商户号等）\n'
        '- 判断执行是否完整：对比工单需求中的数据项与执行记录中的参数，确认所有数据项是否都已被处理\n'
        '- 如果执行记录显示任务成功且参数覆盖了工单需求的所有数据项，应验收通过\n'
        '- 如果执行者只是给出了方案但未真正执行，不应结束\n'
        '- 如果工单有待确认操作未执行，不应结束\n'
    )
    if supervisor.system_prompt:
        prompt += '\n## 监督者专属要求\n' + supervisor.system_prompt

    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': (
            f'## 工单信息\n'
            f'- 编号: {ticket.ticket_no}\n'
            f'- 标题: {ticket.title}\n'
            f'- 状态: 已处理（待最终验收）\n\n'
            f'## 工单内容（提交人的原始需求）\n{ticket.content or ""}\n\n'
            f'## 完整执行记录（评论区）\n{comments_text or "（无记录）"}\n\n'
            f'## AI处理结果摘要\n{ticket.ai_result or "（无）"}\n\n'
            f'## 监督评分\n{ticket.final_score or "（无评分）"}\n\n'
            f'请仔细对比工单需求和执行记录，判断执行是否完整覆盖了所有需求，然后做最终验收决定。'
        )},
    ]

    try:
        content, tokens, p_tokens, c_tokens, cache_create, cache_read, headroom = AiService.chat_with_failover(
            messages, use_tools=False, scope='ticket'
        )
        ticket.accumulate_ai_token_usage({
            'tokens': tokens, 'prompt_tokens': p_tokens, 'completion_tokens': c_tokens,
            'cache_creation_tokens': cache_create, 'cache_read_tokens': cache_read, 'headroom_stats': headroom,
        })
    except Exception as e:
        logger.warning(f'工单 {ticket.ticket_no} 监督者自动验收失败: {e}')
        return

    decision = (content or '').strip()

    # 解析综合评分
    from app.services.multi_agent_service import MultiAgentService
    final_score = MultiAgentService._parse_score(decision)
    if final_score is not None:
        ticket.final_score = final_score
        logger.info(f'工单 {ticket.ticket_no} 监督者综合评分: {final_score}')
    
    # 放宽格式判断：检查关键词而非严格格式（覆盖多种表达方式）
    has_pass = (
        '验收通过' in decision or '通过验收' in decision or '【通过】' in decision or
        '验收结论：通过' in decision or '验收结论:通过' in decision or
        '同意关闭' in decision or '可以关闭' in decision or '应关闭' in decision or
        '同意结束' in decision or '可以结束' in decision or '应结束' in decision
    )
    has_close = '结束工单' in decision or '自动结束' in decision or '可以结束' in decision or '应结束' in decision
    has_reject = (
        '验收不通过' in decision or '不通过' in decision or '【不通过】' in decision or
        '不应结束' in decision or '不应关闭' in decision or '不同意关闭' in decision or
        '需要返工' in decision or '补充处理' in decision or '任务遗漏' in decision or
        '执行不完整' in decision or '结果不完整' in decision
    )
    
    # 调试日志
    logger.info(f'工单 {ticket.ticket_no} 监督者验收决策: has_pass={has_pass}, has_close={has_close}, has_reject={has_reject}, score={final_score}')
    logger.info(f'工单 {ticket.ticket_no} 监督者输出前100字: {decision[:100]}')

    if has_pass and not has_reject:
        # 监督者验收通过（且没有明确说不通过），自动结束工单
        # "验收通过"本身就隐含应该结束
        score_text = f'，综合评分：{final_score}分' if final_score is not None else ''
        logger.info(f'工单 {ticket.ticket_no} 监督者验收通过{score_text}，自动结束工单')
        ticket.status = 'closed'
        ticket.closed_at = datetime.utcnow()
        _add_comment(ticket, None, f'✅ 监督者最终验收通过{score_text}，工单自动结束\n\n{decision}', 'status_change', is_ai=True)
        db.session.commit()
    elif has_reject:
        # 监督者验收不通过，检查是否需要重新执行
        score_text = f'，综合评分：{final_score}分' if final_score is not None else ''
        
        # 检查是否超过最大补充处理轮数（默认3轮）
        # 使用 ticket.collaboration_rounds 作为补充处理轮数计数
        max_retry_rounds = 3
        current_rounds = ticket.collaboration_rounds or 0
        
        if current_rounds < max_retry_rounds:
            # 未超过最大轮数，触发执行者补充处理
            logger.info(f'工单 {ticket.ticket_no} 监督者验收不通过{score_text}，触发执行者补充处理（第{current_rounds + 1}轮）')
            ticket.status = 'processing'
            ticket.collaboration_rounds = current_rounds + 1
            ticket.last_activity_at = datetime.utcnow()
            _add_comment(ticket, None, f'❌ 监督者验收不通过{score_text}，将由执行者补充处理（第{current_rounds + 1}轮）\n\n{decision}', 'status_change', is_ai=True)
            db.session.commit()
            
            # 提取反馈内容（去掉【验收不通过】前缀）
            feedback = decision
            if decision.startswith('【验收不通过】'):
                feedback = decision[len('【验收不通过】'):].strip() or decision
            
            # 触发执行者重新处理（带监督者反馈）
            _trigger_executor_retry_with_feedback(ticket.id, feedback, app)
        else:
            # 超过最大轮数，强制结束并记录
            logger.info(f'工单 {ticket.ticket_no} 已达最大补充处理轮数({max_retry_rounds}轮)，强制结束')
            ticket.status = 'closed'
            ticket.closed_at = datetime.utcnow()
            _add_comment(ticket, None, f'⚠️ 已达最大补充处理轮数({max_retry_rounds}轮)，工单强制结束\n\n监督者最终意见：{decision}', 'status_change', is_ai=True)
            db.session.commit()
    else:
        # 未按格式输出，保守处理：不结束，记录监督者意见
        logger.warning(f'工单 {ticket.ticket_no} 监督者验收输出格式异常: {decision[:100]}')
        _add_comment(ticket, None, f'监督者最终验收意见：{decision}', 'ai_process', is_ai=True)
        db.session.commit()
