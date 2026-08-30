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
        '## 验收输出格式（严格遵守）\n'
        '- 如果工单处理结果满足提交人要求，应结束：回复以【验收通过，结束工单】开头，简述结论\n'
        '- 如果工单处理结果仍有问题，不应结束：回复以【验收不通过】开头，说明原因\n\n'
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

    # 放宽格式判断：检查关键词而非严格格式
    has_pass = '验收通过' in decision or '通过验收' in decision or '【通过】' in decision
    has_close = '结束工单' in decision or '自动结束' in decision or '可以结束' in decision or '应结束' in decision
    has_reject = '验收不通过' in decision or '不通过' in decision or '【不通过】' in decision or '不应结束' in decision
    
    # 调试日志
    logger.info(f'工单 {ticket.ticket_no} 监督者验收决策: has_pass={has_pass}, has_close={has_close}, has_reject={has_reject}')
    logger.info(f'工单 {ticket.ticket_no} 监督者输出前100字: {decision[:100]}')

    if has_pass and not has_reject:
        # 监督者验收通过（且没有明确说不通过），自动结束工单
        # "验收通过"本身就隐含应该结束
        logger.info(f'工单 {ticket.ticket_no} 监督者验收通过，自动结束工单')
        ticket.status = 'closed'
        ticket.closed_at = datetime.utcnow()
        _add_comment(ticket, None, f'监督者最终验收通过，工单自动结束：{decision}', 'status_change', is_ai=True)
        db.session.commit()
    elif has_reject:
        # 监督者验收不通过，保持 processed 状态，提交者仍可手动结束
        logger.info(f'工单 {ticket.ticket_no} 监督者验收不通过，保持已处理状态')
        _add_comment(ticket, None, f'监督者最终验收未通过，工单保持「已处理」状态：{decision}', 'status_change', is_ai=True)
        db.session.commit()
    else:
        # 未按格式输出，保守处理：不结束，记录监督者意见
        logger.warning(f'工单 {ticket.ticket_no} 监督者验收输出格式异常: {decision[:100]}')
        _add_comment(ticket, None, f'监督者最终验收意见：{decision}', 'ai_process', is_ai=True)
        db.session.commit()
