"""统一任务监控接口

聚合查询任务、导出任务、系统任务执行记录中"进行中"的任务，
供前端右上角红点 + 悬停面板 + 完成通知使用。

任务来源：
- QueryTask（type='query' 查询 / type='export' 导出/分润导出）
- SystemTaskExecution（系统任务执行记录）

注意：信息查询（lookup）为同步接口，无任务/进度概念，不纳入监控。
"""
from flask import Blueprint, jsonify, request
from app import db
from app.models.query_task import QueryTask
from app.models.system_task import SystemTask, SystemTaskExecution
from app.models.script import Script
from app.utils.auth import login_required, get_current_user

task_bp = Blueprint('task', __name__, url_prefix='/api/tasks')

# 视为"进行中"的状态
ACTIVE_STATUSES = ('pending', 'running')
# 视为"已完成"的终态
TERMINAL_STATUSES = ('completed', 'failed', 'cancelled', 'manual_cancelled', 'timeout')


def _query_task_title(task):
    """根据 QueryTask 推断展示标题"""
    # 优先取关联脚本名
    script_ids = task.get_script_ids_json()
    if script_ids:
        scripts = Script.query.filter(Script.id.in_(script_ids)).all()
        if scripts:
            names = [s.name for s in scripts]
            if len(names) == 1:
                return names[0]
            return f"{names[0]} 等{len(names)}个脚本"
    # 其次根据类型给默认名
    type_label = {'query': '查询任务', 'export': '导出任务'}.get(task.type, '任务')
    return f"{type_label}({task.task_id[:8]})"


def _query_task_type_label(task):
    """QueryTask 类型标签"""
    if task.type == 'query':
        return '查询任务'
    if task.type == 'export':
        return '导出任务'
    return '任务'


def _query_task_url(task):
    """QueryTask 跳转地址"""
    return '/history'


def _execution_title(execution):
    """SystemTaskExecution 标题"""
    sys_task = SystemTask.query.get(execution.system_task_id) if execution.system_task_id else None
    return sys_task.name if sys_task else f"系统任务({execution.execution_id[:8]})"


def _execution_type_label(execution):
    return '系统任务'


def _execution_url(execution):
    return '/system-tasks'


def _normalize_query_task(task):
    return {
        'id': f"qt_{task.id}",
        'task_id': task.task_id,
        'kind': 'query_task',
        'category': _query_task_type_label(task),
        'title': _query_task_title(task),
        'status': task.status,
        'progress': task.progress or 0,
        'total_rows': task.total_rows or 0,
        'success_count': task.success_count or 0,
        'failure_count': task.failure_count or 0,
        'error_message': task.error_message,
        'started_at': task.started_at.isoformat() if task.started_at else None,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'created_at': task.created_at.isoformat() if task.created_at else None,
        'url': _query_task_url(task),
    }


def _normalize_execution(execution):
    return {
        'id': f"ste_{execution.id}",
        'task_id': execution.execution_id,
        'kind': 'system_task',
        'category': _execution_type_label(execution),
        'title': _execution_title(execution),
        'status': execution.status,
        'progress': execution.progress or 0,
        'total_rows': 0,
        'success_count': 0,
        'failure_count': 0,
        'error_message': execution.error_message,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'created_at': execution.created_at.isoformat() if execution.created_at else None,
        'url': _execution_url(execution),
    }


# 工单状态映射到任务监控的伪状态（便于前端复用 statusMeta）
TICKET_STATUS_MAP = {
    'submitted': 'pending',
    'received': 'running',
    'processing': 'running',
    'rejected': 'failed',
    'processed': 'pending',
    'closed': 'completed',
}

TICKET_STATUS_PROGRESS = {
    'submitted': 20,
    'received': 45,
    'processing': 65,
    'rejected': 30,
    'processed': 85,
    'closed': 100,
}


def _normalize_ticket(ticket):
    """工单归一化为任务监控条目"""
    from app.routes.ticket_routes import STATUS_LABELS
    return {
        'id': f"tk_{ticket.id}",
        'task_id': ticket.ticket_no,
        'kind': 'ticket',
        'category': '工单',
        'title': ticket.title,
        'status': TICKET_STATUS_MAP.get(ticket.status, ticket.status),
        'raw_status': ticket.status,
        'raw_status_label': STATUS_LABELS.get(ticket.status, ticket.status),
        'progress': TICKET_STATUS_PROGRESS.get(ticket.status, 0),
        'total_rows': 0,
        'success_count': 0,
        'failure_count': 0,
        'error_message': ticket.reject_reason,
        'started_at': ticket.submitted_at.isoformat() if ticket.submitted_at else None,
        'completed_at': ticket.closed_at.isoformat() if ticket.closed_at else None,
        'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
        'url': '/tickets',
    }


@task_bp.route('/active', methods=['GET'])
@login_required
def get_active_tasks():
    """获取当前用户进行中的任务列表（pending/running）

    管理员可见所有用户的任务；普通用户仅见自己创建的任务。
    返回按 created_at 降序排列。
    """
    current_user = get_current_user()
    is_admin = bool(current_user and current_user.is_admin())

    result = []

    # QueryTask
    qt_query = QueryTask.query.filter(QueryTask.status.in_(ACTIVE_STATUSES))
    if not is_admin and current_user:
        qt_query = qt_query.filter_by(created_by=current_user.id)
    qt_tasks = qt_query.order_by(QueryTask.created_at.desc()).all()
    for t in qt_tasks:
        result.append(_normalize_query_task(t))

    # SystemTaskExecution
    ste_query = SystemTaskExecution.query.filter(SystemTaskExecution.status.in_(ACTIVE_STATUSES))
    if not is_admin and current_user:
        ste_query = ste_query.filter_by(created_by=current_user.id)
    ste_list = ste_query.order_by(SystemTaskExecution.created_at.desc()).all()
    for e in ste_list:
        result.append(_normalize_execution(e))

    # Ticket（未结束的工单视为进行中，提交人和指派人可见）
    from app.models.ticket import Ticket
    ticket_active_statuses = ('submitted', 'received', 'processing', 'rejected', 'processed')
    tk_query = Ticket.query.filter(Ticket.status.in_(ticket_active_statuses))
    if not is_admin and current_user:
        tk_query = tk_query.filter(
            db.or_(Ticket.created_by == current_user.id, Ticket.assignee_id == current_user.id)
        )
    tk_list = tk_query.order_by(Ticket.created_at.desc()).limit(50).all()
    for t in tk_list:
        result.append(_normalize_ticket(t))

    # 合并后按 created_at 降序
    result.sort(key=lambda x: x.get('created_at') or '', reverse=True)

    return jsonify({'success': True, 'data': result})


@task_bp.route('/recent', methods=['GET'])
@login_required
def get_recent_tasks():
    """获取最近完成的任务（用于完成通知）

    查询最近 N 分钟内完成的任务，前端用于检测"刚完成"并弹窗提醒。
    默认返回最近 5 分钟内完成的、最多 20 条。
    """
    from datetime import datetime, timedelta
    minutes = request.args.get('minutes', 5, type=int)
    limit = request.args.get('limit', 20, type=int)
    since = datetime.utcnow() - timedelta(minutes=max(1, minutes))

    current_user = get_current_user()
    is_admin = bool(current_user and current_user.is_admin())

    result = []

    qt_query = QueryTask.query.filter(
        QueryTask.status.in_(TERMINAL_STATUSES),
        QueryTask.completed_at >= since
    )
    if not is_admin and current_user:
        qt_query = qt_query.filter_by(created_by=current_user.id)
    qt_tasks = qt_query.order_by(QueryTask.completed_at.desc()).limit(limit).all()
    for t in qt_tasks:
        result.append(_normalize_query_task(t))

    ste_query = SystemTaskExecution.query.filter(
        SystemTaskExecution.status.in_(TERMINAL_STATUSES),
        SystemTaskExecution.completed_at >= since
    )
    if not is_admin and current_user:
        ste_query = ste_query.filter_by(created_by=current_user.id)
    ste_list = ste_query.order_by(SystemTaskExecution.completed_at.desc()).limit(limit).all()
    for e in ste_list:
        result.append(_normalize_execution(e))

    # Ticket（最近结束的工单）
    from app.models.ticket import Ticket
    tk_query = Ticket.query.filter(
        Ticket.status == 'closed',
        Ticket.closed_at >= since
    )
    if not is_admin and current_user:
        tk_query = tk_query.filter(
            db.or_(Ticket.created_by == current_user.id, Ticket.assignee_id == current_user.id)
        )
    tk_list = tk_query.order_by(Ticket.closed_at.desc()).limit(limit).all()
    for t in tk_list:
        result.append(_normalize_ticket(t))

    result.sort(key=lambda x: x.get('completed_at') or '', reverse=True)

    return jsonify({'success': True, 'data': result[:limit]})
