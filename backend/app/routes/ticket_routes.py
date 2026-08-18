"""工单路由

权限规则：
  - 管理员：可见所有工单，可执行任意操作（含关闭）
  - 普通用户：仅可见自己提交的工单 或 指派给自己的工单
  - 状态流转操作按角色限制（见各接口注释）

AI指派：
  - 工单可指派给AI（assignee_type='ai'），由AI自动处理
  - AI处理成功 → processed，AI处理失败 → pending_assignment（待指派）
  - 待指派状态下提交人可重新指派给具体的人（reassign）
"""
import os
import uuid
import json
import threading
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from app import db
from app.models.ticket import Ticket, TicketComment
from app.models.user import User
from app.models.business_system import BusinessSystem
from app.models.ai_agent import AiAgent
from app.models.ai_config import AiConfig
from app.utils.auth import login_required, admin_required, get_current_user

logger = logging.getLogger(__name__)
ticket_bp = Blueprint('ticket', __name__, url_prefix='/api/tickets')

# 状态常量
STATUS_SUBMITTED = 'submitted'
STATUS_RECEIVED = 'received'
STATUS_PROCESSING = 'processing'
STATUS_REJECTED = 'rejected'
STATUS_PROCESSED = 'processed'
STATUS_PENDING_ASSIGNMENT = 'pending_assignment'
STATUS_PENDING_CONFIRMATION = 'pending_confirmation'
STATUS_CLOSED = 'closed'

ACTIVE_STATUSES = (STATUS_SUBMITTED, STATUS_RECEIVED, STATUS_PROCESSING, STATUS_PROCESSED, STATUS_REJECTED, STATUS_PENDING_ASSIGNMENT, STATUS_PENDING_CONFIRMATION)

# 状态标签映射
STATUS_LABELS = {
    STATUS_SUBMITTED: '已提交',
    STATUS_RECEIVED: '已接收',
    STATUS_PROCESSING: '处理中',
    STATUS_REJECTED: '拒绝',
    STATUS_PROCESSED: '已处理',
    STATUS_PENDING_ASSIGNMENT: '待指派',
    STATUS_PENDING_CONFIRMATION: '待确认',
    STATUS_CLOSED: '结束',
}

# 进度条阶段顺序：已提交 → 已接收 → 已处理 → 结束
STATUS_STEPS = [STATUS_SUBMITTED, STATUS_RECEIVED, STATUS_PROCESSED, STATUS_CLOSED]

# 状态映射到任务监控的进度百分比
STATUS_PROGRESS = {
    STATUS_SUBMITTED: 20,
    STATUS_RECEIVED: 45,
    STATUS_PROCESSING: 65,
    STATUS_REJECTED: 30,
    STATUS_PROCESSED: 85,
    STATUS_PENDING_ASSIGNMENT: 15,
    STATUS_PENDING_CONFIRMATION: 50,
    STATUS_CLOSED: 100,
}

# AI处理线程池
_ticket_ai_threads = {}


def _generate_ticket_no():
    """生成工单编号 TKyyyyMMdd + 4位序列"""
    today = datetime.utcnow().strftime('%Y%m%d')
    count = Ticket.query.filter(Ticket.ticket_no.like(f'TK{today}%')).count()
    return f'TK{today}{(count + 1):04d}'


def _can_access(ticket, user):
    """用户是否有权访问该工单"""
    if not user:
        return False
    if user.is_admin():
        return True
    return ticket.created_by == user.id or (ticket.assignee_type == 'user' and ticket.assignee_id == user.id)


def _is_assignee(ticket, user):
    return user and ticket.assignee_type == 'user' and ticket.assignee_id == user.id


def _is_creator(ticket, user):
    return user and ticket.created_by == user.id


def _add_comment(ticket, user_id, content, action='comment', is_ai=False):
    """添加评论记录"""
    if not content:
        return None
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=user_id if not is_ai else None,
        content=content,
        action=action,
        is_ai=is_ai,
    )
    db.session.add(comment)
    return comment


# ── AI处理工单 ──────────────────────────────────────────────

def _process_ticket_with_ai_async(ticket_id, app):
    """后台线程：用AI处理工单（支持工具调用，可匹配系统的导出/查询/系统任务等）"""
    with app.app_context():
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                return

            # 状态改为处理中
            ticket.status = STATUS_PROCESSING
            ticket.received_at = datetime.utcnow()
            db.session.commit()

            # 获取Agent配置
            agent = AiAgent.query.get(ticket.assignee_agent_id) if ticket.assignee_agent_id else None
            # 获取默认AI配置
            ai_config = AiConfig.query.filter_by(is_active=True).first()
            if not ai_config:
                raise Exception('未找到可用的AI模型配置')

            # 获取业务系统名称作为上下文
            system_name = ticket.business_system.name if ticket.business_system else '未指定'

            # 构建工单处理专用系统提示词（含工具说明）
            ticket_system_prompt = _build_ticket_ai_prompt(agent, system_name)

            messages = [
                {'role': 'system', 'content': ticket_system_prompt},
                {'role': 'user', 'content': f'## 工单编号: {ticket.ticket_no}\n## 标题: {ticket.title}\n## 涉及系统: {system_name}\n\n## 工单内容:\n{ticket.content}'},
            ]

            from app.services.ai_service import AiService, filter_tools
            from app.routes.ai_routes import TICKET_FALLBACK_RULE

            # 根据Agent的enabled_tools过滤工具列表
            enabled_tools = agent.get_enabled_tools() if agent else None
            filtered_tools = filter_tools(enabled_tools)

            # 操作型工具：触发即视为已处理（任务已创建）
            action_tools = {'request_export', 'request_query', 'request_system_task', 'request_profit_share'}

            # 工具调用循环（最多3轮，防止死循环）
            max_rounds = 3
            tool_executed = False  # 是否成功执行过工具
            action_triggered = False  # 是否触发了操作型工具
            final_content = ''  # AI最终回复
            tool_log = []  # 工具调用日志（用于工单评论）

            for round_idx in range(max_rounds):
                ai_response = AiService.chat_with_failover(
                    messages, use_tools=True, tools=filtered_tools
                )
                content = ai_response.get('content', '') or ''
                tool_calls = ai_response.get('tool_calls', []) or []

                if not tool_calls:
                    # AI没有调用工具，直接返回文本回复
                    final_content = content
                    break

                # 执行工具调用
                tool_results = []
                # 检测是否有需要确认执行的SQL系统任务
                pending_system_task = None
                for tc in tool_calls:
                    func_name = tc.get('function', {}).get('name', '')
                    func_args = tc.get('function', {}).get('arguments', '')
                    logger.info(f'工单{ticket.ticket_no} AI调用工具(轮次{round_idx+1}): {func_name}({func_args})')

                    result = AiService.execute_tool_call(func_name, func_args, ticket.created_by)
                    tool_results.append({
                        'tool_call_id': tc['id'],
                        'name': func_name,
                        'result': result,
                    })

                    # 记录工具调用日志
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
                                result_summary = f"系统任务已自动执行: {result.get('mapping_summary', '完成')}"
                                tool_executed = True
                            else:
                                # SQL类型系统任务，未自动执行，需要用户确认
                                task_type = result.get('task_type', 'sql')
                                if task_type == 'sql':
                                    # SQL数据变更类任务，需用户确认后执行
                                    pending_system_task = {
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
                                    }
                                    result_summary = f"SQL系统任务「{result.get('task_name', '')}」需用户确认后执行"
                                else:
                                    task_id = result.get('task_id', '')
                                    result_summary = f"已创建系统任务(任务ID: {task_id})" if task_id else "系统任务已触发"
                                    action_triggered = True
                                    tool_executed = True
                        elif result.get('action_type') == 'lookup':
                            total = result.get('total', 0)
                            data = result.get('data', [])
                            result_summary = f"查询到{total}条记录" if total else "未查询到记录"
                            tool_executed = True
                        elif result.get('action_type') == 'profit_share':
                            task_id = result.get('task_id', '')
                            result_summary = f"已创建分润导出任务(任务ID: {task_id})" if task_id else "分润导出已触发"
                            action_triggered = True
                            tool_executed = True
                        elif result.get('total') is not None:
                            result_summary = f"匹配到{result['total']}项"
                        else:
                            result_summary = '已执行'
                    else:
                        result_summary = str(result)[:200]

                    tool_log.append(f'**调用工具**: `{func_name}` → {result_summary}')

                # 如果检测到需要确认的SQL系统任务，暂停处理，等待用户确认
                if pending_system_task:
                    ticket.set_pending_action(pending_system_task)
                    ticket.status = STATUS_PENDING_CONFIRMATION
                    ticket.ai_result = (
                        f"AI识别到需要执行数据变更类操作：**{pending_system_task['task_name']}**\n\n"
                        f"**参数：** {json.dumps(pending_system_task['params_values'], ensure_ascii=False)}\n\n"
                        f"⚠️ 此操作会直接影响生产数据，请提交人确认后执行。\n"
                        f"可在下方评论「同意」、「确认执行」或点击「确认执行」按钮继续。"
                    )
                    if tool_log:
                        tool_log_text = '\n\n'.join(tool_log)
                        ticket.ai_result = f'{ticket.ai_result}\n\n---\n**处理过程：**\n{tool_log_text}'
                    _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
                    _add_comment(ticket, None, '工单状态已转为「待确认」，等待提交人确认后执行数据变更操作', 'status_change', is_ai=True)
                    db.session.commit()
                    logger.info(f'工单 {ticket.ticket_no} AI处理暂停，需用户确认执行SQL系统任务: {pending_system_task["task_name"]}')
                    return

                # 如果触发了操作型工具，不需要继续循环（任务已创建）
                if action_triggered:
                    # 构建工具结果消息，让AI生成一次归总回复
                    messages.append({
                        'role': 'assistant',
                        'content': content,
                        'tool_calls': tool_calls,
                    })
                    for tr in tool_results:
                        messages.append({
                            'role': 'tool',
                            'tool_call_id': tr['tool_call_id'],
                            'content': json.dumps(tr['result'], ensure_ascii=False),
                        })
                    # 请求AI归总结果（不带工具，避免再次调用）
                    try:
                        summary_content, _, _, _, _, _ = AiService.chat_with_failover(messages, use_tools=False)
                        final_content = summary_content or ''
                    except Exception as se:
                        logger.warning(f'工单{ticket.ticket_no} AI归总回复失败: {se}')
                        final_content = '已触发相关任务执行，请到对应模块查看执行结果。'
                    break

                # 非操作型工具（list_*或lookup），构建工具结果消息继续循环
                messages.append({
                    'role': 'assistant',
                    'content': content,
                    'tool_calls': tool_calls,
                })
                for tr in tool_results:
                    messages.append({
                        'role': 'tool',
                        'tool_call_id': tr['tool_call_id'],
                        'content': json.dumps(tr['result'], ensure_ascii=False),
                    })

                # 最后一轮，请求AI生成最终回复（不带工具）
                if round_idx == max_rounds - 1:
                    try:
                        final_content, _, _, _, _, _ = AiService.chat_with_failover(messages, use_tools=False)
                        final_content = final_content or ''
                    except Exception as se:
                        logger.warning(f'工单{ticket.ticket_no} AI最终回复失败: {se}')
                        final_content = content or '处理完成'
            else:
                # 循环正常结束但未break（理论上不会走到这里）
                if not final_content:
                    final_content = content or '处理完成'

            final_content = (final_content or '').strip()
            if not final_content:
                final_content = 'AI已处理，但未返回详细内容。'

            # 判断工单是否处理成功
            # 1. 执行过工具（特别是操作型工具）→ 已处理
            # 2. AI回复以【待人工处理】开头 → 待指派
            # 3. 其他情况默认已处理
            if final_content.startswith('【待人工处理】'):
                is_handled = False
                ai_result = final_content[len('【待人工处理】'):].strip()
            elif final_content.startswith('【已处理】'):
                is_handled = True
                ai_result = final_content[len('【已处理】'):].strip()
            elif tool_executed:
                # 执行过工具，默认视为已处理
                is_handled = True
                ai_result = final_content
            else:
                # 未执行工具，AI纯文本回复，视为已处理（提供方案/解答）
                is_handled = True
                ai_result = final_content

            # 如果有工具调用日志，附加到结果中
            if tool_log:
                tool_log_text = '\n\n'.join(tool_log)
                ai_result = f'{ai_result}\n\n---\n**处理过程：**\n{tool_log_text}'

            ticket.ai_result = ai_result

            if is_handled:
                # AI处理成功 → 已处理
                ticket.status = STATUS_PROCESSED
                ticket.processed_at = datetime.utcnow()
                _add_comment(ticket, None, ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, 'AI已完成处理，等待提交人核实', 'status_change', is_ai=True)
            else:
                # AI处理失败 → 待指派
                ticket.status = STATUS_PENDING_ASSIGNMENT
                _add_comment(ticket, None, ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, 'AI无法直接处理此工单，状态已转为「待指派」，请提交人重新指派给具体的人来人工介入', 'status_change', is_ai=True)

            db.session.commit()
            logger.info(f'工单 {ticket.ticket_no} AI处理完成，结果状态: {ticket.status}，执行工具: {tool_executed}，操作型: {action_triggered}')

        except Exception as e:
            logger.error(f'工单AI处理失败 ticket_id={ticket_id}: {e}', exc_info=True)
            try:
                with app.app_context():
                    # 先rollback清除失败的事务
                    db.session.rollback()
                    ticket = Ticket.query.get(ticket_id)
                    if ticket:
                        ticket.status = STATUS_PENDING_ASSIGNMENT
                        ticket.ai_result = f'AI处理异常: {str(e)}'
                        # 先保存工单状态（确保状态一定能保存）
                        db.session.commit()
                        # 再尝试添加评论（失败不影响工单状态）
                        try:
                            _add_comment(ticket, None, f'AI处理过程中发生异常: {str(e)}', 'status_change', is_ai=True)
                            db.session.commit()
                        except Exception as ce:
                            logger.warning(f'工单异常评论添加失败 ticket_id={ticket_id}: {ce}')
                            db.session.rollback()
            except:
                pass


def _build_ticket_ai_prompt(agent, system_name):
    """构建工单处理专用的系统提示词（含工具说明和工单处理规则）"""
    from app.routes.ai_routes import TICKET_FALLBACK_RULE

    # 基础工具说明
    base_prompt = (
        '你是一个工单处理助手，可以调用系统工具来实际处理工单需求。\n\n'
        '## 可用工具\n'
        '系统中有以下工具可供调用：\n'
        '1. 导出任务（export）：从数据库导出数据到Excel，调用 list_export_options / request_export\n'
        '2. 查询任务（query）：根据Excel文件中的主键数据去数据库批量查询匹配信息，调用 list_query_options / request_query\n'
        '3. 系统任务（system_task）：后台运维类操作（如数据清理、缓存刷新、终端解绑、执行本地脚本等），支持SQL、API和本地脚本三种类型，调用 list_system_tasks / request_system_task\n'
        '4. 信息查询（lookup）：根据用户提供的参数值快速查询数据库返回结果（如查询SN绑定状态、商户是否激活、订单是否出款等），调用 list_lookup_options / request_lookup\n'
        '5. 分润导出（profit_share）：根据代理商编号和交易时间范围计算各级代理分润并导出Excel，调用 request_profit_share\n\n'
        '## 工单处理规则\n'
        '- 仔细分析工单内容，判断属于哪种任务类型，调用对应工具实际执行\n'
        '- 如果工单内容包含明确的参数（如商户号、订单号、SN号、日期等），直接调用 request_* 工具执行\n'
        '- 如果不确定具体任务名称，先调用 list_* 工具查找匹配项\n'
        '- API类型的系统任务参数齐全时会自动执行并返回结果，请根据mapping_summary（映射摘要）用自然语言说明执行结果\n'
        '- 如果用户的意图是条件性的（如"查一下这个SN的绑定状态，如果已绑定就解绑"），先调用 request_lookup 查询状态，再根据结果决定是否调用 request_system_task\n'
        '- 如果同时需要对多个对象执行同样的操作（如"解绑SN001、SN002"），请同时调用多个 request_system_task\n'
        '- 务必从工单内容中提取所有参数值填入 params 对象，params的键名必须使用list_*工具返回的参数配置中的name字段值\n\n'
        '## 回复格式规则\n'
        '- 如果你成功调用了工具并执行了任务（导出/查询/系统任务/信息查询/分润导出），请用自然语言总结执行结果，回复以【已处理】开头\n'
        '- 如果你无法通过工具处理（如需要物理操作、需要人工审批、需要外部协调等），请说明原因，回复以【待人工处理】开头\n'
        '- 如果你能直接给出解决方案或操作指引（如解答问题、提供步骤），请详细回复，回复以【已处理】开头\n'
        '- 回复使用中文，支持Markdown格式\n'
    )

    # 附加Agent的系统提示词（如果存在）
    if agent and agent.system_prompt:
        base_prompt = base_prompt + '\n## Agent专属能力\n' + agent.system_prompt

    # 追加工单兜底规则
    base_prompt = base_prompt + '\n' + TICKET_FALLBACK_RULE

    return base_prompt


def _trigger_ai_processing(ticket):
    """触发AI后台处理工单"""
    app = current_app._get_current_object()
    t = threading.Thread(target=_process_ticket_with_ai_async, args=(ticket.id, app), daemon=True)
    _ticket_ai_threads[ticket.id] = t
    t.start()


def _confirm_ticket_action(ticket, current_user):
    """提交人确认执行待确认的数据变更操作

    将工单从 pending_confirmation 转为 processing，并异步执行pending_action中存储的SQL系统任务。
    """
    pending_action = ticket.get_pending_action()
    if not pending_action:
        raise Exception('没有待确认执行的任务')

    if ticket.status != STATUS_PENDING_CONFIRMATION:
        raise Exception('工单当前状态不允许确认操作')

    # 转为处理中
    ticket.status = STATUS_PROCESSING
    _add_comment(ticket, current_user.id, '提交人已确认执行数据变更操作，AI开始执行', 'status_change')
    db.session.commit()

    # 异步执行待确认的任务
    app = current_app._get_current_object()
    t = threading.Thread(
        target=_execute_pending_action_async,
        args=(ticket.id, app),
        daemon=True
    )
    _ticket_ai_threads[ticket.id] = t
    t.start()


def _execute_pending_action_async(ticket_id, app):
    """后台线程：执行待确认的数据变更操作（SQL系统任务）"""
    with app.app_context():
        try:
            ticket = Ticket.query.get(ticket_id)
            if not ticket:
                return

            pending_action = ticket.get_pending_action()
            if not pending_action:
                raise Exception('没有待确认执行的任务信息')

            task_id = pending_action.get('task_id')
            params_values = pending_action.get('params_values', {})
            database_id = pending_action.get('database_id')

            logger.info(f'工单 {ticket.ticket_no} 开始执行待确认的SQL系统任务: task_id={task_id}')

            from app.models.system_task import SystemTask, SystemTaskExecution
            from app.services.system_task_service import SystemTaskService

            system_task = SystemTask.query.get(task_id) if task_id else None
            if not system_task:
                raise Exception(f'系统任务不存在(ID={task_id})')

            # 创建执行记录并异步执行SQL任务
            execution = SystemTaskService.create_execution(
                system_task_id=system_task.id,
                params_values=params_values,
                created_by=ticket.created_by,
            )
            # 设置任务类型
            execution.task_type = 'sql'
            execution.status = 'running'
            execution.started_at = datetime.utcnow()
            db.session.commit()

            # 异步执行
            SystemTaskService.execute_async(
                execution_id=execution.execution_id,
                system_task_id=system_task.id,
                params_values=params_values,
                database_id=database_id,
            )

            # 等待执行完成（轮询检查状态，最多等待5分钟）
            import time
            max_wait = 300  # 5分钟
            waited = 0
            while waited < max_wait:
                db.session.expire(execution)
                execution = SystemTaskExecution.query.filter_by(execution_id=execution.execution_id).first()
                if not execution:
                    break
                if execution.status in ('completed', 'failed', 'cancelled'):
                    break
                time.sleep(2)
                waited += 2

            # 获取执行结果
            execution = SystemTaskExecution.query.filter_by(execution_id=execution.execution_id).first()
            if not execution:
                raise Exception('执行记录丢失')

            # 构建结果摘要
            result_data = execution.get_result_data()
            logs = execution.get_logs()

            if execution.status == 'completed':
                # 执行成功
                result_summary = 'SQL系统任务执行成功'
                if isinstance(result_data, dict):
                    affected = result_data.get('total_affected', 0)
                    if affected:
                        result_summary = f'SQL系统任务执行成功，影响{affected}行数据'
                    elif result_data.get('message'):
                        result_summary = f'SQL系统任务执行成功：{result_data["message"]}'

                ticket.status = STATUS_PROCESSED
                ticket.processed_at = datetime.utcnow()
                ticket.ai_result = f'✅ {result_summary}\n\n**任务名称：** {system_task.name}\n**执行ID：** {execution.execution_id[:8]}...'
                ticket.clear_pending_action()
                _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, 'AI已完成数据变更操作，等待提交人核实', 'status_change', is_ai=True)
            else:
                # 执行失败
                error_msg = execution.error_message or '执行失败'
                ticket.status = STATUS_PENDING_ASSIGNMENT
                ticket.ai_result = f'❌ SQL系统任务执行失败：{error_msg}'
                ticket.clear_pending_action()
                _add_comment(ticket, None, ticket.ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, '数据变更操作执行失败，工单已转为「待指派」，请重新指派或重试', 'status_change', is_ai=True)

            db.session.commit()
            logger.info(f'工单 {ticket.ticket_no} 待确认任务执行完成，状态: {execution.status}')

        except Exception as e:
            logger.error(f'工单待确认任务执行失败 ticket_id={ticket_id}: {e}', exc_info=True)
            try:
                with app.app_context():
                    db.session.rollback()
                    ticket = Ticket.query.get(ticket_id)
                    if ticket:
                        ticket.status = STATUS_PENDING_ASSIGNMENT
                        ticket.ai_result = f'执行待确认任务时发生异常: {str(e)}'
                        ticket.clear_pending_action()
                        db.session.commit()
                        try:
                            _add_comment(ticket, None, ticket.ai_result, 'status_change', is_ai=True)
                            db.session.commit()
                        except Exception as ce:
                            logger.warning(f'工单异常评论添加失败 ticket_id={ticket_id}: {ce}')
                            db.session.rollback()
            except:
                pass


# ── 路由 ──────────────────────────────────────────────────

@ticket_bp.route('', methods=['GET'])
@login_required
def list_tickets():
    """工单列表

    管理员：所有工单
    普通用户：自己提交的 + 指派给自己的
    支持筛选：status, assignee_id, created_by, business_system_id, keyword
    """
    current_user = get_current_user()
    is_admin = bool(current_user and current_user.is_admin())

    query = Ticket.query
    if not is_admin and current_user:
        query = query.filter(
            db.or_(Ticket.created_by == current_user.id, Ticket.assignee_id == current_user.id)
        )

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    assignee_id = request.args.get('assignee_id', type=int)
    if assignee_id:
        query = query.filter_by(assignee_id=assignee_id)

    created_by = request.args.get('created_by', type=int)
    if created_by:
        query = query.filter_by(created_by=created_by)

    business_system_id = request.args.get('business_system_id', type=int)
    if business_system_id:
        query = query.filter_by(business_system_id=business_system_id)

    keyword = (request.args.get('keyword') or '').strip()
    if keyword:
        query = query.filter(
            db.or_(Ticket.title.contains(keyword), Ticket.ticket_no.contains(keyword))
        )

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = query.order_by(Ticket.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    tickets = [t.to_dict() for t in pagination.items]
    return jsonify({
        'success': True,
        'data': tickets,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@ticket_bp.route('/<int:ticket_id>', methods=['GET'])
@login_required
def get_ticket(ticket_id):
    """工单详情（含评论）"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    current_user = get_current_user()
    if not _can_access(ticket, current_user):
        return jsonify({'success': False, 'message': '无权访问此工单'}), 403

    data = ticket.to_dict(include_comments=True)
    data['status_label'] = STATUS_LABELS.get(ticket.status, ticket.status)
    data['status_steps'] = STATUS_STEPS
    data['status_labels'] = STATUS_LABELS
    return jsonify({'success': True, 'data': data})


@ticket_bp.route('', methods=['POST'])
@login_required
def create_ticket():
    """创建工单

    任何登录用户均可提交工单。
    必填：title, content
    指派（二选一）：
      - assignee_type='user' + assignee_id（指派给具体用户）
      - assignee_type='ai' + assignee_agent_id（指派给AI，可选，默认使用默认Agent）
    可选：business_system_id
    """
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    assignee_type = (data.get('assignee_type') or 'user').strip()

    if not title:
        return jsonify({'success': False, 'message': '标题不能为空'}), 400
    if not content:
        return jsonify({'success': False, 'message': '工单内容不能为空'}), 400

    business_system_id = data.get('business_system_id')
    if business_system_id:
        try:
            business_system_id = int(business_system_id)
        except (TypeError, ValueError):
            business_system_id = None

    current_user = get_current_user()
    now = datetime.utcnow()

    # 处理指派
    assignee_id = None
    assignee_agent_id = None

    if assignee_type == 'ai':
        # 指派给AI
        assignee_agent_id = data.get('assignee_agent_id')
        if assignee_agent_id:
            try:
                assignee_agent_id = int(assignee_agent_id)
            except (TypeError, ValueError):
                assignee_agent_id = None

        # 权限校验：普通用户无切换Agent权限时，忽略指定的Agent，直接用默认
        # 普通用户有切换权限时，校验指定的Agent是否在授权范围内
        if assignee_agent_id and not current_user.is_admin():
            if not current_user.can_switch_agent():
                # 无切换权限：忽略指定，用默认Agent
                assignee_agent_id = None
            elif not current_user.can_use_agent(assignee_agent_id):
                return jsonify({'success': False, 'message': '无权使用该AI Agent，请选择授权范围内的Agent'}), 403

        # 未指定Agent（或被忽略）则用默认Agent
        if not assignee_agent_id:
            agent = AiAgent.query.filter_by(is_active=True, is_default=True).first()
            if not agent:
                agent = AiAgent.query.filter_by(is_active=True).first()
            if agent:
                assignee_agent_id = agent.id
            else:
                return jsonify({'success': False, 'message': '未找到可用的AI Agent'}), 400
    else:
        # 指派给具体用户
        assignee_id = data.get('assignee_id')
        if not assignee_id:
            return jsonify({'success': False, 'message': '请选择指派人'}), 400
        try:
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': '指派人ID格式错误'}), 400

        assignee = User.query.get(assignee_id)
        if not assignee or not assignee.is_active:
            return jsonify({'success': False, 'message': '指派人不存在或已禁用'}), 400

    ticket = Ticket(
        ticket_no=_generate_ticket_no(),
        title=title,
        content=content,
        business_system_id=business_system_id,
        assignee_type=assignee_type,
        assignee_id=assignee_id,
        assignee_agent_id=assignee_agent_id,
        created_by=current_user.id,
        status=STATUS_SUBMITTED,
        submitted_at=now,
    )
    db.session.add(ticket)
    db.session.commit()

    # 如果指派给AI，自动触发AI处理
    if assignee_type == 'ai':
        _trigger_ai_processing(ticket)
        return jsonify({'success': True, 'data': ticket.to_dict(), 'message': '工单已提交，AI正在处理中'})

    return jsonify({'success': True, 'data': ticket.to_dict(), 'message': '工单已提交'})


@ticket_bp.route('/<int:ticket_id>/status', methods=['PUT'])
@login_required
def update_status(ticket_id):
    """状态流转

    操作类型（action）：
      receive        指派人接收          submitted → received
      process        指派人开始处理       received → processing
      complete       指派人完成处理       processing → processed
      reject         指派人拒绝（需reason） submitted/received → rejected
      confirm        提交人核实通过       processed → closed
      reopen         提交人重新发起       processed → submitted
      appeal         提交人申诉重启（需reason） rejected → submitted
      reassign       提交人重新指派       pending_assignment → submitted（需 assignee_id 或 assignee_type='ai'）
      transfer       被指派人移交工单     received/processing → submitted（需 assignee_id 或 assignee_type='ai'）
      close          管理员关闭           any → closed

    请求体：{ action: str, reason?: str, comment?: str, assignee_id?: int, assignee_type?: str }
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    current_user = get_current_user()
    if not _can_access(ticket, current_user):
        return jsonify({'success': False, 'message': '无权操作此工单'}), 403

    data = request.get_json() or {}
    action = (data.get('action') or '').strip()
    reason = (data.get('reason') or '').strip()
    comment_text = (data.get('comment') or '').strip()
    now = datetime.utcnow()

    # 合并 reason 到评论
    if reason and not comment_text:
        comment_text = reason

    transitions = {
        # action: (from_statuses, to_status, role, requires_reason, comment_action)
        'receive': ([STATUS_SUBMITTED], STATUS_RECEIVED, 'assignee', False, 'status_change'),
        'process': ([STATUS_RECEIVED], STATUS_PROCESSING, 'assignee', False, 'status_change'),
        'complete': ([STATUS_PROCESSING], STATUS_PROCESSED, 'assignee', False, 'status_change'),
        'reject': ([STATUS_SUBMITTED, STATUS_RECEIVED], STATUS_REJECTED, 'assignee', True, 'reject'),
        'confirm': ([STATUS_PROCESSED], STATUS_CLOSED, 'creator', False, 'status_change'),
        'reopen': ([STATUS_PROCESSED], STATUS_SUBMITTED, 'creator', False, 'status_change'),
        'appeal': ([STATUS_REJECTED], STATUS_SUBMITTED, 'creator', True, 'appeal'),
        'reassign': ([STATUS_PENDING_ASSIGNMENT, STATUS_PENDING_CONFIRMATION], STATUS_SUBMITTED, 'creator', False, 'status_change'),
        'transfer': ([STATUS_RECEIVED, STATUS_PROCESSING], STATUS_SUBMITTED, 'assignee', False, 'status_change'),
        'close': (list(STATUS_LABELS.keys()), STATUS_CLOSED, 'admin', False, 'status_change'),
    }

    if action not in transitions:
        return jsonify({'success': False, 'message': f'未知操作: {action}'}), 400

    from_statuses, to_status, role, requires_reason, comment_action = transitions[action]

    # 角色校验
    if role == 'assignee' and not _is_assignee(ticket, current_user):
        return jsonify({'success': False, 'message': '仅指派人可执行此操作'}), 403
    if role == 'creator' and not (_is_creator(ticket, current_user) or current_user.is_admin()):
        return jsonify({'success': False, 'message': '仅提交人可执行此操作'}), 403
    if role == 'admin' and not current_user.is_admin():
        return jsonify({'success': False, 'message': '仅管理员可执行此操作'}), 403

    # 状态校验
    if ticket.status not in from_statuses:
        return jsonify({
            'success': False,
            'message': f'当前状态({STATUS_LABELS.get(ticket.status, ticket.status)})不允许此操作'
        }), 400

    # 必填原因校验
    if requires_reason and not reason:
        return jsonify({'success': False, 'message': '此操作必须填写原因'}), 400

    # 重新指派 / 重新发起 / 移交工单 特殊处理（都需要重新指派）
    if action in ('reassign', 'reopen', 'transfer'):
        new_assignee_type = (data.get('assignee_type') or '').strip()
        new_assignee_id = data.get('assignee_id')
        new_assignee_agent_id = data.get('assignee_agent_id')

        # reopen时如果未提供指派类型，默认保留原指派
        if action == 'reopen' and not new_assignee_type:
            new_assignee_type = ticket.assignee_type or 'user'
            # 保留原指派人/Agent
            new_assignee_id = ticket.assignee_id
            new_assignee_agent_id = ticket.assignee_agent_id
        elif not new_assignee_type:
            new_assignee_type = 'user'

        # transfer 必须指定新的指派对象，不能移交给原指派人自己
        if action == 'transfer':
            if new_assignee_type == 'user' and new_assignee_id and int(new_assignee_id) == ticket.assignee_id:
                return jsonify({'success': False, 'message': '不能移交给当前指派人自己'}), 400
            if new_assignee_type == ticket.assignee_type and new_assignee_agent_id and int(new_assignee_agent_id) == (ticket.assignee_agent_id or 0):
                return jsonify({'success': False, 'message': '不能移交给当前指派的AI Agent'}), 400

        if new_assignee_type == 'ai':
            if new_assignee_agent_id:
                try:
                    new_assignee_agent_id = int(new_assignee_agent_id)
                except (TypeError, ValueError):
                    new_assignee_agent_id = None

            # 权限校验：普通用户无切换Agent权限时，忽略指定的Agent，直接用默认
            # 普通用户有切换权限时，校验指定的Agent是否在授权范围内
            if new_assignee_agent_id and not current_user.is_admin():
                if not current_user.can_switch_agent():
                    new_assignee_agent_id = None
                elif not current_user.can_use_agent(new_assignee_agent_id):
                    return jsonify({'success': False, 'message': '无权使用该AI Agent，请选择授权范围内的Agent'}), 403

            if not new_assignee_agent_id:
                agent = AiAgent.query.filter_by(is_active=True, is_default=True).first()
                if not agent:
                    agent = AiAgent.query.filter_by(is_active=True).first()
                if agent:
                    new_assignee_agent_id = agent.id
            ticket.assignee_type = 'ai'
            ticket.assignee_id = None
            ticket.assignee_agent_id = new_assignee_agent_id
        else:
            if not new_assignee_id:
                return jsonify({'success': False, 'message': '请选择新的指派人'}), 400
            try:
                new_assignee_id = int(new_assignee_id)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': '指派人ID格式错误'}), 400
            assignee = User.query.get(new_assignee_id)
            if not assignee or not assignee.is_active:
                return jsonify({'success': False, 'message': '指派人不存在或已禁用'}), 400
            ticket.assignee_type = 'user'
            ticket.assignee_id = new_assignee_id
            ticket.assignee_agent_id = None

        ticket.status = STATUS_SUBMITTED
        ticket.submitted_at = now
        ticket.received_at = None
        ticket.processed_at = None
        ticket.closed_at = None
        ticket.reject_reason = None
        ticket.appeal_reason = None
        # 清空上次AI处理结果和待确认任务信息
        ticket.ai_result = None
        ticket.clear_pending_action()

        if action == 'reassign':
            action_msg = '提交人重新指派了工单'
        elif action == 'transfer':
            if new_assignee_type == 'ai':
                action_msg = '被指派人将工单移交给AI处理'
            else:
                action_msg = '被指派人将工单移交给其他人处理'
        else:
            action_msg = '提交人重新发起了工单'

        _add_comment(ticket, current_user.id, comment_text or action_msg, 'status_change')

        db.session.commit()

        # 如果重新指派给AI，触发AI处理
        if new_assignee_type == 'ai':
            _trigger_ai_processing(ticket)

        if action == 'reassign':
            msg = '工单已重新指派'
        elif action == 'transfer':
            msg = '工单已移交' + ('给AI' if new_assignee_type == 'ai' else '')
        else:
            msg = '工单已重新发起'
        return jsonify({
            'success': True,
            'data': ticket.to_dict(include_comments=True),
            'message': msg + ('，AI正在处理中' if new_assignee_type == 'ai' else '')
        })

    # 执行流转
    ticket.status = to_status

    # 记录拒绝/申诉原因到冗余字段
    if action == 'reject':
        ticket.reject_reason = reason
    elif action == 'appeal':
        ticket.appeal_reason = reason
        ticket.reject_reason = None

    # 更新时间戳
    if to_status == STATUS_RECEIVED:
        ticket.received_at = now
    elif to_status == STATUS_PROCESSED:
        ticket.processed_at = now
    elif to_status == STATUS_CLOSED:
        ticket.closed_at = now
    elif to_status == STATUS_SUBMITTED and action == 'appeal':
        ticket.submitted_at = now
        ticket.received_at = None
        ticket.processed_at = None
        ticket.closed_at = None

    # 添加评论记录
    if comment_text:
        _add_comment(ticket, current_user.id, comment_text, comment_action)
    else:
        # 状态变更也记录一条系统评论
        status_comment = f'状态变更为「{STATUS_LABELS.get(to_status, to_status)}」'
        _add_comment(ticket, current_user.id, status_comment, 'status_change')

    db.session.commit()

    return jsonify({
        'success': True,
        'data': ticket.to_dict(include_comments=True),
        'message': f'工单已{STATUS_LABELS.get(to_status, to_status)}'
    })


@ticket_bp.route('/<int:ticket_id>/comments', methods=['POST'])
@login_required
def add_comment(ticket_id):
    """添加评论"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    current_user = get_current_user()
    if not _can_access(ticket, current_user):
        return jsonify({'success': False, 'message': '无权评论此工单'}), 403

    # 工单已结束，禁止评论
    if ticket.status == STATUS_CLOSED:
        return jsonify({'success': False, 'message': '工单已结束，无法发表评论'}), 400

    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'success': False, 'message': '评论内容不能为空'}), 400

    comment = _add_comment(ticket, current_user.id, content, 'comment')
    db.session.commit()

    # 如果工单处于待确认状态，且评论人是提交人，且评论含确认关键词，则自动触发确认执行
    if (ticket.status == STATUS_PENDING_CONFIRMATION
            and ticket.assignee_type == 'ai'
            and ticket.created_by == current_user.id):
        confirm_keywords = ['同意', '确认执行', '确认', '同意执行', '继续执行', '执行', 'confirmed', 'yes']
        content_lower = content.lower().strip()
        if any(kw in content_lower for kw in confirm_keywords):
            try:
                _confirm_ticket_action(ticket, current_user)
                return jsonify({'success': True, 'data': comment.to_dict(),
                                'message': '已确认执行，AI正在处理中'})
            except Exception as e:
                logger.error(f'评论触发确认执行失败 ticket_id={ticket_id}: {e}', exc_info=True)
                return jsonify({'success': True, 'data': comment.to_dict(),
                                'message': f'评论已添加，但触发确认执行失败: {str(e)}'})

    return jsonify({'success': True, 'data': comment.to_dict(), 'message': '评论已添加'})


@ticket_bp.route('/<int:ticket_id>/retry-ai', methods=['POST'])
@login_required
def retry_ai_processing(ticket_id):
    """重新触发AI处理（仅待指派状态的工单，且当前指派给AI）"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    current_user = get_current_user()
    if not _can_access(ticket, current_user):
        return jsonify({'success': False, 'message': '无权操作此工单'}), 403

    if ticket.status not in (STATUS_PENDING_ASSIGNMENT, STATUS_PENDING_CONFIRMATION):
        return jsonify({'success': False, 'message': '仅待指派或待确认状态的工单可重新触发AI处理'}), 400

    if ticket.assignee_type != 'ai':
        return jsonify({'success': False, 'message': '仅指派给AI的工单可重新触发AI处理'}), 400

    # 清空待确认任务信息并重新触发
    ticket.clear_pending_action()
    ticket.status = STATUS_SUBMITTED
    ticket.submitted_at = datetime.utcnow()
    db.session.commit()
    _trigger_ai_processing(ticket)

    return jsonify({'success': True, 'message': 'AI正在重新处理中'})


@ticket_bp.route('/<int:ticket_id>/confirm-action', methods=['POST'])
@login_required
def confirm_ticket_action(ticket_id):
    """提交人确认执行待确认的数据变更操作

    仅待确认状态(pending_confirmation)且指派给AI的工单可操作，仅提交人可确认。
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    current_user = get_current_user()
    if ticket.created_by != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '仅提交人可确认执行'}), 403

    if ticket.status != STATUS_PENDING_CONFIRMATION:
        return jsonify({'success': False, 'message': f'当前状态({STATUS_LABELS.get(ticket.status, ticket.status)})不允许确认操作'}), 400

    if ticket.assignee_type != 'ai':
        return jsonify({'success': False, 'message': '仅指派给AI的工单支持确认执行'}), 400

    pending_action = ticket.get_pending_action()
    if not pending_action:
        return jsonify({'success': False, 'message': '没有待确认执行的任务信息'}), 400

    try:
        _confirm_ticket_action(ticket, current_user)
        return jsonify({
            'success': True,
            'message': '已确认执行，AI正在执行数据变更操作',
            'data': ticket.to_dict(include_comments=True),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@ticket_bp.route('/<int:ticket_id>/cancel-action', methods=['POST'])
@login_required
def cancel_ticket_action(ticket_id):
    """提交人取消待确认的数据变更操作

    将工单从 pending_confirmation 转为 pending_assignment，清空pending_action。
    """
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    current_user = get_current_user()
    if ticket.created_by != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '仅提交人可取消'}), 403

    if ticket.status != STATUS_PENDING_CONFIRMATION:
        return jsonify({'success': False, 'message': f'当前状态({STATUS_LABELS.get(ticket.status, ticket.status)})不允许取消操作'}), 400

    task_name = ticket.get_pending_action().get('task_name', '')
    ticket.status = STATUS_PENDING_ASSIGNMENT
    ticket.clear_pending_action()
    _add_comment(ticket, current_user.id, f'提交人取消了数据变更操作「{task_name}」，工单转为待指派', 'status_change')
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '已取消执行，工单转为待指派',
        'data': ticket.to_dict(include_comments=True),
    })


@ticket_bp.route('/<int:ticket_id>', methods=['DELETE'])
@admin_required
def delete_ticket(ticket_id):
    """删除工单（仅管理员）"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'success': False, 'message': '工单不存在'}), 404

    db.session.delete(ticket)
    db.session.commit()
    return jsonify({'success': True, 'message': '工单已删除'})


@ticket_bp.route('/assignees', methods=['GET'])
@login_required
def list_assignees():
    """获取可指派的用户列表（供所有登录用户选择指派人）

    返回启用的用户简要信息：id, username, display_name
    """
    users = User.query.filter_by(is_active=True).order_by(User.username.asc()).all()
    data = [
        {
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name or u.username,
        }
        for u in users
    ]
    return jsonify({'success': True, 'data': data})


@ticket_bp.route('/ai-agents', methods=['GET'])
@login_required
def list_ai_agents():
    """获取可指派的AI Agent列表

    权限规则：
      - 管理员：返回所有启用的Agent
      - 普通用户有切换Agent权限：返回授权过的Agent（含默认）
      - 普通用户无切换Agent权限：返回空列表，前端隐藏选择框直接用默认Agent
    返回 can_switch_agent 标识供前端控制是否显示Agent选择框
    """
    current_user = get_current_user()
    can_switch = current_user.can_switch_agent()

    if current_user.is_admin():
        agents = AiAgent.query.filter_by(is_active=True).order_by(AiAgent.is_default.desc(), AiAgent.name).all()
    elif can_switch:
        # 有切换权限：返回授权过的Agent（get_allowed_agents 已包含默认Agent）
        agents = current_user.get_allowed_agents()
        # 按 is_default 优先排序
        agents = sorted(agents, key=lambda a: (not a.is_default, a.name))
    else:
        # 无切换权限：返回空列表，前端直接用默认Agent
        agents = []

    data = [
        {
            'id': a.id,
            'name': a.name,
            'description': a.description or '',
            'is_default': a.is_default,
        }
        for a in agents
    ]
    return jsonify({'success': True, 'data': data, 'can_switch_agent': can_switch})


@ticket_bp.route('/upload', methods=['POST'])
@login_required
def upload_attachment():
    """上传工单附件（图片/视频）

    返回 { url, filename, size, type }
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': '文件名为空'}), 400

    # 允许的扩展名
    allowed_img = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
    allowed_video = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_img and ext not in allowed_video:
        return jsonify({'success': False, 'message': f'不支持的文件类型: {ext}'}), 400

    # MIME type validation (prevent extension spoofing)
    import magic
    file_content = file.read(2048)
    file.seek(0)
    try:
        mime_type = magic.from_buffer(file_content, mime=True)
        if ext in allowed_img and not mime_type.startswith('image/'):
            return jsonify({'success': False, 'message': '文件内容与扩展名不匹配（非图片文件）'}), 400
        if ext in allowed_video and not mime_type.startswith('video/'):
            return jsonify({'success': False, 'message': '文件内容与扩展名不匹配（非视频文件）'}), 400
    except Exception:
        # If magic library is not available, skip MIME validation
        pass

    # 保存到 uploads/tickets/
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tickets')
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"ticket_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    file_type = 'image' if ext in allowed_img else 'video'
    size = os.path.getsize(file_path)

    # 返回相对 URL，由前端拼接
    url = f"/api/tickets/files/{filename}"

    return jsonify({
        'success': True,
        'data': {
            'url': url,
            'filename': file.filename,
            'saved_name': filename,
            'size': size,
            'type': file_type,
        }
    })


@ticket_bp.route('/files/<filename>', methods=['GET'])
@login_required
def serve_file(filename):
    """访问工单附件文件"""
    from flask import send_from_directory
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tickets')
    return send_from_directory(upload_dir, filename)


@ticket_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """工单统计（用于 Dashboard）"""
    current_user = get_current_user()
    is_admin = bool(current_user and current_user.is_admin())

    query = Ticket.query
    if not is_admin and current_user:
        query = query.filter(
            db.or_(Ticket.created_by == current_user.id, Ticket.assignee_id == current_user.id)
        )

    total = query.count()
    by_status = {}
    for status, label in STATUS_LABELS.items():
        by_status[status] = query.filter_by(status=status).count()

    active_count = sum(by_status.get(s, 0) for s in
                       [STATUS_SUBMITTED, STATUS_RECEIVED, STATUS_PROCESSING, STATUS_PROCESSED, STATUS_PENDING_ASSIGNMENT])

    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'active': active_count,
            'by_status': by_status,
            'status_labels': STATUS_LABELS,
        }
    })


@ticket_bp.route('/analytics', methods=['GET'])
@login_required
def get_analytics():
    """工单统计分析

    支持按天/月/年维度统计每个用户的工单提交数、处理数、完成数、完成占比、平均处理时长。

    查询参数：
      dimension  维度：day/month/year，默认 month
      start_date 起始日期 YYYY-MM-DD（含）
      end_date   结束日期 YYYY-MM-DD（含）
      date_field 时间字段：submitted(按提交时间，默认)/processed(按处理完成时间)
    """
    from sqlalchemy import func

    current_user = get_current_user()
    is_admin = bool(current_user and current_user.is_admin())

    dimension = (request.args.get('dimension') or 'month').strip().lower()
    if dimension not in ('day', 'month', 'year'):
        dimension = 'month'
    date_field = (request.args.get('date_field') or 'submitted').strip().lower()
    if date_field not in ('submitted', 'processed'):
        date_field = 'submitted'

    # 时间范围解析
    def _parse_date(s, end_of_day=False):
        if not s:
            return None
        try:
            d = datetime.strptime(s, '%Y-%m-%d')
            if end_of_day:
                d = d.replace(hour=23, minute=59, second=59)
            return d
        except ValueError:
            return None

    start_date = _parse_date(request.args.get('start_date'))
    end_date = _parse_date(request.args.get('end_date'), end_of_day=True)

    # 时间字段选择
    # submitted: 趋势图按提交时间分组；processed: 趋势图按处理完成时间分组
    time_col = Ticket.submitted_at if date_field == 'submitted' else Ticket.processed_at

    def _apply_time_filter(query, col):
        """对查询应用时间范围过滤"""
        q = query.filter(col.isnot(None))
        if start_date:
            q = q.filter(col >= start_date)
        if end_date:
            q = q.filter(col <= end_date)
        return q

    # 趋势图基础查询：按选定时间字段过滤
    period_base = _apply_time_filter(Ticket.query, time_col)

    # 用户统计基础查询：
    # - 提交数：始终按 submitted_at 过滤时间范围
    # - 处理相关统计：按选定时间字段过滤（与趋势图一致）
    submitted_base = _apply_time_filter(Ticket.query, Ticket.submitted_at)
    processed_base = _apply_time_filter(Ticket.query, time_col)

    # 按维度分组的时间表达式（北京时间 = UTC + 8h）
    if dimension == 'day':
        time_expr = func.date(func.convert_tz(time_col, '+00:00', '+08:00'))
        date_label = '日期'
    elif dimension == 'year':
        time_expr = func.year(func.convert_tz(time_col, '+00:00', '+08:00'))
        date_label = '年份'
    else:
        time_expr = func.date_format(func.convert_tz(time_col, '+00:00', '+08:00'), '%Y-%m')
        date_label = '月份'

    # 时段维度汇总（总览）
    period_query = period_base.with_entities(
        time_expr.label('period'),
        func.count(Ticket.id).label('count'),
    ).group_by(time_expr).order_by(time_expr)

    period_rows = period_query.all()
    periods = []
    for row in period_rows:
        periods.append({'period': str(row.period), 'count': row.count})

    # 各用户统计
    # 1) 提交数（按 created_by）
    # 2) 被指派处理数（按 assignee_id，仅指派给具体人的工单）
    # 3) 处理完成数（被指派且状态为 processed/closed）
    # 4) 平均处理时长（processed_at - received_at，按 assignee_id 聚合）

    def _aggregate_by_user(base_q, group_col, extra_filters=None):
        """按指定列聚合统计"""
        q = base_q.filter(group_col.isnot(None))
        if extra_filters is not None:
            q = q.filter(extra_filters)
        return q.with_entities(
            group_col.label('user_id'),
            func.count(Ticket.id).label('count'),
        ).group_by(group_col)

    user_assignee_filter = Ticket.assignee_type == 'user'

    # 提交数统计（按 created_by，用 submitted_base）
    submitted_rows = _aggregate_by_user(submitted_base, Ticket.created_by).all()
    # 处理数统计（被指派给具体人，用 processed_base）
    assigned_rows = _aggregate_by_user(processed_base, Ticket.assignee_id, user_assignee_filter).all()
    # 完成数统计（被指派且状态为已处理/已结束）
    completed_rows = _aggregate_by_user(
        processed_base, Ticket.assignee_id,
        db.and_(user_assignee_filter, Ticket.status.in_([STATUS_PROCESSED, STATUS_CLOSED]))
    ).all()
    # 平均处理时长统计：查询每个用户处理完成的工单明细，Python端计算平均时长
    # 优先用 received_at → processed_at（实际处理耗时），无法获取时用 submitted_at → processed_at
    duration_query = processed_base.filter(
        user_assignee_filter,
        Ticket.assignee_id.isnot(None),
        Ticket.processed_at.isnot(None),
    ).with_entities(
        Ticket.assignee_id.label('user_id'),
        Ticket.received_at,
        Ticket.submitted_at,
        Ticket.processed_at,
    )
    duration_rows = duration_query.all()

    # AI Agent 统计：按 assignee_agent_id 聚合（指派给AI的工单）
    ai_assignee_filter = Ticket.assignee_type == 'ai'
    ai_assigned_rows = _aggregate_by_user(processed_base, Ticket.assignee_agent_id, ai_assignee_filter).all()
    ai_completed_rows = _aggregate_by_user(
        processed_base, Ticket.assignee_agent_id,
        db.and_(ai_assignee_filter, Ticket.status.in_([STATUS_PROCESSED, STATUS_CLOSED]))
    ).all()
    # AI 待确认工单数
    ai_pending_rows = _aggregate_by_user(
        processed_base, Ticket.assignee_agent_id,
        db.and_(ai_assignee_filter, Ticket.status == STATUS_PENDING_CONFIRMATION)
    ).all()
    # AI 失败转待指派工单数
    ai_failed_rows = _aggregate_by_user(
        processed_base, Ticket.assignee_agent_id,
        db.and_(ai_assignee_filter, Ticket.status == STATUS_PENDING_ASSIGNMENT)
    ).all()
    # AI 处理时长明细
    ai_duration_query = processed_base.filter(
        ai_assignee_filter,
        Ticket.assignee_agent_id.isnot(None),
        Ticket.processed_at.isnot(None),
    ).with_entities(
        Ticket.assignee_agent_id.label('agent_id'),
        Ticket.received_at,
        Ticket.submitted_at,
        Ticket.processed_at,
    )
    ai_duration_rows = ai_duration_query.all()

    # 汇总到用户维度
    user_map = {}  # user_id -> {submitted, assigned, completed, avg_duration, durations}

    for row in submitted_rows:
        user_map.setdefault(row.user_id, {})['submitted'] = row.count
    for row in assigned_rows:
        user_map.setdefault(row.user_id, {})['assigned'] = row.count
    for row in completed_rows:
        user_map.setdefault(row.user_id, {})['completed'] = row.count
    # 平均处理时长：收集每个用户的处理耗时（秒），后续统一计算平均值
    for row in duration_rows:
        uid = row.user_id
        # 优先用 received_at → processed_at，无法获取时用 submitted_at → processed_at
        start_time = row.received_at or row.submitted_at
        if start_time and row.processed_at:
            delta_sec = (row.processed_at - start_time).total_seconds()
            if delta_sec > 0:
                user_map.setdefault(uid, {}).setdefault('durations', []).append(delta_sec)

    # AI Agent 维度汇总
    agent_map = {}  # agent_id -> {assigned, completed, pending, failed, durations}
    for row in ai_assigned_rows:
        agent_map.setdefault(row.user_id, {})['assigned'] = row.count
    for row in ai_completed_rows:
        agent_map.setdefault(row.user_id, {})['completed'] = row.count
    for row in ai_pending_rows:
        agent_map.setdefault(row.user_id, {})['pending'] = row.count
    for row in ai_failed_rows:
        agent_map.setdefault(row.user_id, {})['failed'] = row.count
    for row in ai_duration_rows:
        aid = row.agent_id
        start_time = row.received_at or row.submitted_at
        if start_time and row.processed_at:
            delta_sec = (row.processed_at - start_time).total_seconds()
            if delta_sec > 0:
                agent_map.setdefault(aid, {}).setdefault('durations', []).append(delta_sec)

    # 获取用户信息
    user_ids = list(user_map.keys())
    users_info = {}
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids)).all()
        for u in users:
            users_info[u.id] = {
                'username': u.username,
                'display_name': u.display_name or u.username,
            }

    # 非管理员只看自己的统计
    if not is_admin and current_user:
        user_map = {k: v for k, v in user_map.items() if k == current_user.id}

    # 组装返回数据
    user_stats = []
    for uid, stats in user_map.items():
        submitted = stats.get('submitted', 0)
        assigned = stats.get('assigned', 0)
        completed = stats.get('completed', 0)
        durations = stats.get('durations', [])
        info = users_info.get(uid, {})
        # 完成占比 = 完成数 / 被指派数
        completion_rate = round(completed / assigned * 100, 2) if assigned > 0 else 0
        # 平均处理时长（秒）：用收集到的耗时列表计算平均值
        avg_sec = round(sum(durations) / len(durations), 1) if durations else 0
        user_stats.append({
            'user_id': uid,
            'username': info.get('username', f'用户{uid}'),
            'display_name': info.get('display_name', f'用户{uid}'),
            'submitted_count': submitted,
            'assigned_count': assigned,
            'completed_count': completed,
            'completion_rate': completion_rate,
            'avg_duration_seconds': avg_sec,
            'processed_count': len(durations),
        })

    # 按提交数降序
    user_stats.sort(key=lambda x: x['submitted_count'], reverse=True)

    # 组装 AI Agent 统计数据
    agent_ids = list(agent_map.keys())
    agents_info = {}
    if agent_ids:
        agents = AiAgent.query.filter(AiAgent.id.in_(agent_ids)).all()
        for a in agents:
            agents_info[a.id] = {
                'name': a.name,
                'is_default': a.is_default,
            }

    ai_stats = []
    for aid, stats in agent_map.items():
        assigned = stats.get('assigned', 0)
        completed = stats.get('completed', 0)
        pending = stats.get('pending', 0)
        failed = stats.get('failed', 0)
        durations = stats.get('durations', [])
        info = agents_info.get(aid, {})
        # AI完成占比 = 完成数 / 指派数
        completion_rate = round(completed / assigned * 100, 2) if assigned > 0 else 0
        # AI平均处理时长（秒）
        avg_sec = round(sum(durations) / len(durations), 1) if durations else 0
        ai_stats.append({
            'agent_id': aid,
            'agent_name': info.get('name', f'Agent#{aid}'),
            'is_default': info.get('is_default', False),
            'assigned_count': assigned,
            'completed_count': completed,
            'pending_count': pending,
            'failed_count': failed,
            'completion_rate': completion_rate,
            'avg_duration_seconds': avg_sec,
            'processed_count': len(durations),
        })

    # AI 按指派数降序
    ai_stats.sort(key=lambda x: x['assigned_count'], reverse=True)

    # 总览（含AI）
    total_submitted = sum(u['submitted_count'] for u in user_stats)
    total_assigned = sum(u['assigned_count'] for u in user_stats) + sum(a['assigned_count'] for a in ai_stats)
    total_completed = sum(u['completed_count'] for u in user_stats) + sum(a['completed_count'] for a in ai_stats)
    overall_completion_rate = round(total_completed / total_assigned * 100, 2) if total_assigned > 0 else 0
    # 全局平均处理时长（秒，含AI）
    all_durations = [u['avg_duration_seconds'] for u in user_stats if u['avg_duration_seconds'] > 0]
    all_durations.extend([a['avg_duration_seconds'] for a in ai_stats if a['avg_duration_seconds'] > 0])
    overall_avg_sec = round(sum(all_durations) / len(all_durations), 1) if all_durations else 0
    # AI 总览
    ai_total_assigned = sum(a['assigned_count'] for a in ai_stats)
    ai_total_completed = sum(a['completed_count'] for a in ai_stats)
    ai_total_pending = sum(a['pending_count'] for a in ai_stats)
    ai_total_failed = sum(a['failed_count'] for a in ai_stats)
    ai_completion_rate = round(ai_total_completed / ai_total_assigned * 100, 2) if ai_total_assigned > 0 else 0
    ai_durations = [a['avg_duration_seconds'] for a in ai_stats if a['avg_duration_seconds'] > 0]
    ai_avg_sec = round(sum(ai_durations) / len(ai_durations), 1) if ai_durations else 0

    return jsonify({
        'success': True,
        'data': {
            'dimension': dimension,
            'date_field': date_field,
            'date_label': date_label,
            'start_date': request.args.get('start_date'),
            'end_date': request.args.get('end_date'),
            'periods': periods,
            'user_stats': user_stats,
            'ai_stats': ai_stats,
            'summary': {
                'total_submitted': total_submitted,
                'total_assigned': total_assigned,
                'total_completed': total_completed,
                'overall_completion_rate': overall_completion_rate,
                'overall_avg_duration_seconds': overall_avg_sec,
                'user_count': len(user_stats),
                'ai_total_assigned': ai_total_assigned,
                'ai_total_completed': ai_total_completed,
                'ai_total_pending': ai_total_pending,
                'ai_total_failed': ai_total_failed,
                'ai_completion_rate': ai_completion_rate,
                'ai_avg_duration_seconds': ai_avg_sec,
                'ai_agent_count': len(ai_stats),
            },
            'status_labels': STATUS_LABELS,
        }
    })


# ── 供AI工具调用的工单创建服务方法 ──────────────────────────

def create_ticket_from_ai(title, content, assignee_type='user', assignee_id=None,
                           assignee_agent_id=None, business_system_id=None,
                           created_by=None):
    """AI工具调用的工单创建方法（非路由，供ai_service调用）

    返回 ticket 对象或 None
    """
    if not title or not content:
        return None

    if business_system_id:
        try:
            business_system_id = int(business_system_id)
        except (TypeError, ValueError):
            business_system_id = None

    assignee_id_val = None
    assignee_agent_id_val = None

    if assignee_type == 'ai':
        if assignee_agent_id:
            try:
                assignee_agent_id_val = int(assignee_agent_id)
            except (TypeError, ValueError):
                assignee_agent_id_val = None

        # 权限校验：普通用户无切换Agent权限时，忽略指定的Agent，直接用默认
        # 普通用户有切换权限时，校验指定的Agent是否在授权范围内（不在则降级用默认）
        creator = User.query.get(created_by) if created_by else None
        if assignee_agent_id_val and creator and not creator.is_admin():
            if not creator.can_switch_agent():
                # 无切换权限：忽略指定，用默认Agent
                assignee_agent_id_val = None
            elif not creator.can_use_agent(assignee_agent_id_val):
                # 无权使用该Agent：降级用默认Agent
                assignee_agent_id_val = None

        if not assignee_agent_id_val:
            agent = AiAgent.query.filter_by(is_active=True, is_default=True).first()
            if not agent:
                agent = AiAgent.query.filter_by(is_active=True).first()
            if agent:
                assignee_agent_id_val = agent.id
    else:
        if assignee_id:
            try:
                assignee_id_val = int(assignee_id)
            except (TypeError, ValueError):
                assignee_id_val = None

    ticket = Ticket(
        ticket_no=_generate_ticket_no(),
        title=title.strip(),
        content=content.strip(),
        business_system_id=business_system_id,
        assignee_type=assignee_type,
        assignee_id=assignee_id_val,
        assignee_agent_id=assignee_agent_id_val,
        created_by=created_by,
        status=STATUS_SUBMITTED,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(ticket)
    db.session.commit()

    # 如果指派给AI，自动触发AI处理
    if assignee_type == 'ai':
        _trigger_ai_processing(ticket)

    return ticket
