"""工单路由

权限规则：
  - 管理员：可见所有工单，可执行任意操作（含关闭）
  - 普通用户：仅可见自己提交的工单 或 指派给自己的工单
  - 状态流转操作按角色限制（见各接口注释）
"""
import os
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, g

from app import db
from app.models.ticket import Ticket, TicketComment
from app.models.user import User
from app.models.business_system import BusinessSystem
from app.utils.auth import login_required, admin_required, get_current_user
from app.utils.helpers import beijing_isoformat

ticket_bp = Blueprint('ticket', __name__, url_prefix='/api/tickets')

# 状态常量
STATUS_SUBMITTED = 'submitted'
STATUS_RECEIVED = 'received'
STATUS_PROCESSING = 'processing'
STATUS_REJECTED = 'rejected'
STATUS_PROCESSED = 'processed'
STATUS_CLOSED = 'closed'

ACTIVE_STATUSES = (STATUS_SUBMITTED, STATUS_RECEIVED, STATUS_PROCESSING, STATUS_PROCESSED, STATUS_REJECTED)

# 状态标签映射
STATUS_LABELS = {
    STATUS_SUBMITTED: '已提交',
    STATUS_RECEIVED: '已接收',
    STATUS_PROCESSING: '处理中',
    STATUS_REJECTED: '拒绝',
    STATUS_PROCESSED: '已处理',
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
    STATUS_CLOSED: 100,
}


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
    return ticket.created_by == user.id or ticket.assignee_id == user.id


def _is_assignee(ticket, user):
    return user and ticket.assignee_id == user.id


def _is_creator(ticket, user):
    return user and ticket.created_by == user.id


def _add_comment(ticket, user_id, content, action='comment'):
    """添加评论记录"""
    if not content:
        return None
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=user_id,
        content=content,
        action=action,
    )
    db.session.add(comment)
    return comment


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
    必填：title, content, assignee_id
    可选：business_system_id
    """
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    assignee_id = data.get('assignee_id', type=int)

    if not title:
        return jsonify({'success': False, 'message': '标题不能为空'}), 400
    if not content:
        return jsonify({'success': False, 'message': '工单内容不能为空'}), 400
    if not assignee_id:
        return jsonify({'success': False, 'message': '请选择指派人'}), 400

    assignee = User.query.get(assignee_id)
    if not assignee or not assignee.is_active:
        return jsonify({'success': False, 'message': '指派人不存在或已禁用'}), 400

    current_user = get_current_user()
    now = datetime.utcnow()

    ticket = Ticket(
        ticket_no=_generate_ticket_no(),
        title=title,
        content=content,
        business_system_id=data.get('business_system_id', type=int),
        assignee_id=assignee_id,
        created_by=current_user.id,
        status=STATUS_SUBMITTED,
        submitted_at=now,
    )
    db.session.add(ticket)
    db.session.commit()

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
      close     管理员关闭           any → closed

    请求体：{ action: str, reason?: str, comment?: str }
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
        'close': (list(STATUS_LABELS.keys()), STATUS_CLOSED, 'admin', False, 'status_change'),
    }

    if action not in transitions:
        return jsonify({'success': False, 'message': f'未知操作: {action}'}), 400

    from_statuses, to_status, role, requires_reason, comment_action = transitions[action]

    # 角色校验
    if role == 'assignee' and not _is_assignee(ticket, current_user):
        return jsonify({'success': False, 'message': '仅指派人可执行此操作'}), 403
    if role == 'creator' and not _is_creator(ticket, current_user):
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

    active_count = sum(by_status.get(s, 0) for s in [STATUS_SUBMITTED, STATUS_RECEIVED, STATUS_PROCESSING, STATUS_PROCESSED])

    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'active': active_count,
            'by_status': by_status,
            'status_labels': STATUS_LABELS,
        }
    })
