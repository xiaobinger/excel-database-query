from flask import request, g
from app import db
from app.models.operation_log import OperationLog


def _get_client_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    xri = request.headers.get('X-Real-IP', '')
    if xri:
        return xri.strip()
    return request.remote_addr or '127.0.0.1'


def log_operation(action, target_type=None, target_id=None, detail=None):
    """记录操作日志，自动获取当前用户和IP"""
    try:
        user = getattr(g, 'user', None)
        log = OperationLog(
            user_id=user.id if user else None,
            username=user.username if user else 'anonymous',
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=_get_client_ip(),
            user_agent=request.headers.get('User-Agent', '')[:500],
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
