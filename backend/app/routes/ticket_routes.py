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
STATUS_CLOSED = 'closed'

ACTIVE_STATUSES = (STATUS_SUBMITTED, STATUS_RECEIVED, STATUS_PROCESSING, STATUS_PROCESSED, STATUS_REJECTED, STATUS_PENDING_ASSIGNMENT)

# 状态标签映射
STATUS_LABELS = {
    STATUS_SUBMITTED: '已提交',
    STATUS_RECEIVED: '已接收',
    STATUS_PROCESSING: '处理中',
    STATUS_REJECTED: '拒绝',
    STATUS_PROCESSED: '已处理',
    STATUS_PENDING_ASSIGNMENT: '待指派',
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
    """后台线程：用AI处理工单"""
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

            # 构建系统提示词
            system_prompt = agent.system_prompt if agent and agent.system_prompt else (
                '你是一个工单处理助手。用户会提交工单描述问题或需求。'
                '请根据工单内容尝试给出解决方案或处理结果。\n\n'
                '重要规则：\n'
                '- 如果你能直接给出解决方案（如解答问题、提供操作指引），请详细回复，回复以【已处理】开头。\n'
                '- 如果你无法直接处理（如需要人工操作数据库、需要物理操作、需要权限审批等），'
                '请说明原因，回复以【待人工处理】开头。\n'
                '- 回复使用中文，支持Markdown格式。'
            )

            # 获取业务系统名称作为上下文
            system_name = ticket.business_system.name if ticket.business_system else '未指定'

            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f'## 工单编号: {ticket.ticket_no}\n## 标题: {ticket.title}\n## 涉及系统: {system_name}\n\n## 工单内容:\n{ticket.content}'},
            ]

            # 调用LLM
            from app.services.ai_service import AiService
            content, tokens, p_tokens, c_tokens, cache_create, cache_read = AiService.chat(ai_config, messages)

            if not content or not content.strip():
                raise Exception('AI返回空内容')

            content = content.strip()

            # 判断AI是否成功处理
            is_handled = content.startswith('【已处理】') or not content.startswith('【待人工处理】')
            # 默认如果AI没有明确表示无法处理，就认为已处理
            if content.startswith('【待人工处理】'):
                is_handled = False
                # 去掉标记前缀
                ai_result = content[len('【待人工处理】'):].strip()
            else:
                ai_result = content[len('【已处理】'):].strip() if content.startswith('【已处理】') else content

            ticket.ai_result = ai_result

            if is_handled:
                # AI处理成功 → 已处理
                ticket.status = STATUS_PROCESSED
                ticket.processed_at = datetime.utcnow()
                _add_comment(ticket, None, ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, f'AI已完成处理，等待提交人核实', 'status_change', is_ai=True)
            else:
                # AI处理失败 → 待指派
                ticket.status = STATUS_PENDING_ASSIGNMENT
                _add_comment(ticket, None, ai_result, 'ai_process', is_ai=True)
                _add_comment(ticket, None, f'AI无法直接处理此工单，状态已转为「待指派」，请提交人重新指派给具体的人来人工介入', 'status_change', is_ai=True)

            db.session.commit()
            logger.info(f'工单 {ticket.ticket_no} AI处理完成，结果状态: {ticket.status}')

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


def _trigger_ai_processing(ticket):
    """触发AI后台处理工单"""
    app = current_app._get_current_object()
    t = threading.Thread(target=_process_ticket_with_ai_async, args=(ticket.id, app), daemon=True)
    _ticket_ai_threads[ticket.id] = t
    t.start()


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
      receive   指派人接收          submitted → received
      process   指派人开始处理       received → processing
      complete  指派人完成处理       processing → processed
      reject    指派人拒绝（需reason） submitted/received → rejected
      confirm   提交人核实通过       processed → closed
      reopen    提交人重新发起       processed → submitted
      appeal    提交人申诉重启（需reason） rejected → submitted
      reassign  提交人重新指派       pending_assignment → submitted（需 assignee_id 或 assignee_type='ai'）
      close     管理员关闭           any → closed

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
        'reassign': ([STATUS_PENDING_ASSIGNMENT], STATUS_SUBMITTED, 'creator', False, 'status_change'),
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

    # 重新指派特殊处理
    if action == 'reassign':
        new_assignee_type = (data.get('assignee_type') or 'user').strip()
        new_assignee_id = data.get('assignee_id')
        new_assignee_agent_id = data.get('assignee_agent_id')

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

        _add_comment(ticket, current_user.id, comment_text or '提交人重新指派了工单', 'status_change')

        db.session.commit()

        # 如果重新指派给AI，触发AI处理
        if new_assignee_type == 'ai':
            _trigger_ai_processing(ticket)

        return jsonify({
            'success': True,
            'data': ticket.to_dict(include_comments=True),
            'message': '工单已重新指派' + ('，AI正在处理中' if new_assignee_type == 'ai' else '')
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
    elif to_status == STATUS_SUBMITTED and action in ('reopen', 'appeal'):
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

    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'success': False, 'message': '评论内容不能为空'}), 400

    comment = _add_comment(ticket, current_user.id, content, 'comment')
    db.session.commit()

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

    if ticket.status != STATUS_PENDING_ASSIGNMENT:
        return jsonify({'success': False, 'message': '仅待指派状态的工单可重新触发AI处理'}), 400

    if ticket.assignee_type != 'ai':
        return jsonify({'success': False, 'message': '仅指派给AI的工单可重新触发AI处理'}), 400

    # 重新触发
    ticket.status = STATUS_SUBMITTED
    ticket.submitted_at = datetime.utcnow()
    db.session.commit()
    _trigger_ai_processing(ticket)

    return jsonify({'success': True, 'message': 'AI正在重新处理中'})


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
