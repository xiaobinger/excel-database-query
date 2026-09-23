import re

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
    """记录操作日志，自动获取当前用户和IP

    显式埋点调用后会在当前请求上下文中打上 g._op_logged 标记，
    全局自动埋点中间件据此避免重复记录。
    """
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
        try:
            g._op_logged = True
        except Exception:
            pass
    except Exception:
        db.session.rollback()


# ---------------------------------------------------------------------------
# 全局自动埋点
# ---------------------------------------------------------------------------

# 只记录会产生副作用的写操作；GET/HEAD/OPTIONS 视为只读，不埋点
_WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

# 纯工具类接口（SQL 校验/格式化/列匹配等），不构成有意义的操作，跳过
_SKIP_PATH_PATTERNS = (
    re.compile(r'^/api/query/(validate-sql|format-sql|fuzzy-match-columns|smart-match)/?$'),
    re.compile(r'^/api/dashboard/(parse-params|parse-columns)/?$'),
    re.compile(r'^/api/ai/match-query/?$'),
    re.compile(r'^/api/health'),
    re.compile(r'^/api/notifications/heartbeat/?$'),
)

# 资源段 -> 目标类型
_RESOURCE_TARGET_MAP = {
    'query': 'query',
    'export': 'export',
    'auto-export': 'auto_export',
    'ai': 'ai_chat',
    'tickets': 'ticket',
    'system-tasks': 'system_task',
    'users': 'user',
    'roles': 'role',
    'databases': 'database',
    'scripts': 'script',
    'business': 'business_system',
    'agents': 'agent',
    'mcp': 'mcp_server',
    'pay': 'pay',
    'pay-flow': 'pay_flow',
    'payment': 'payment',
    'profit-share': 'profit_share',
    'dashboard': 'dashboard',
    'lookup': 'lookup',
    'ssh': 'ssh_config',
    'logs': 'log',
    'scheduler': 'scheduler',
    'strategies': 'ai_strategy',
    'api-keys': 'api_key',
}

# 路径后缀 -> 动作（按顺序匹配，命中即返回）
_ACTION_PATH_RULES = (
    (re.compile(r'/execute/?$'), 'execute'),
    (re.compile(r'/run-now/?$'), 'execute'),
    (re.compile(r'/send-stream/?$'), 'chat'),
    (re.compile(r'/send/?$'), 'chat'),
    (re.compile(r'/test/?$'), 'test'),
    (re.compile(r'/toggle/?$'), 'toggle'),
    (re.compile(r'/status/?$'), 'status_change'),
    (re.compile(r'/submit/?$'), 'submit'),
    (re.compile(r'/cancel'), 'cancel'),
    (re.compile(r'/retry'), 'retry'),
    (re.compile(r'/abort/?$'), 'abort'),
    (re.compile(r'/interrupt/?$'), 'interrupt'),
    (re.compile(r'/resend-email/?$'), 'send_email'),
    (re.compile(r'/confirm-action/?$'), 'confirm_action'),
    (re.compile(r'/batch-hard-delete/?$'), 'batch_delete'),
    (re.compile(r'/batch-delete/?$'), 'batch_delete'),
    (re.compile(r'/all/?$'), 'delete_all'),
    (re.compile(r'/upload'), 'upload'),
    (re.compile(r'/comments/?$'), 'comment'),
    (re.compile(r'/clear/?$'), 'clear'),
    (re.compile(r'/compress/?$'), 'compress'),
    (re.compile(r'/refresh'), 'refresh'),
)

_METHOD_BASE_ACTION = {
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
}

_TARGET_ID_RE = re.compile(r'/(\d+)(?:/|$)')


def _resolve_action(method, path):
    for pattern, action in _ACTION_PATH_RULES:
        if pattern.search(path):
            return action
    return _METHOD_BASE_ACTION.get(method, 'operation')


def _resolve_target_type(path):
    parts = [p for p in path.split('/') if p]
    # parts[0] == 'api'
    resource = parts[1] if len(parts) > 1 else ''
    return _RESOURCE_TARGET_MAP.get(resource, resource or None)


def _resolve_target_id(path):
    match = _TARGET_ID_RE.search(path)
    return int(match.group(1)) if match else None


def auto_log_operation(response):
    """全局 after_request 钩子：为未被显式埋点的写操作自动记录操作日志"""
    try:
        if request.method not in _WRITE_METHODS:
            return response
        path = request.path or ''
        if not path.startswith('/api/'):
            return response
        if getattr(g, '_op_logged', False):
            return response
        for pattern in _SKIP_PATH_PATTERNS:
            if pattern.search(path):
                return response
        # 仅记录成功的操作；校验失败/被限流等不计入操作日志
        if response.status_code >= 400:
            return response

        action = _resolve_action(request.method, path)
        target_type = _resolve_target_type(path)
        target_id = _resolve_target_id(path)
        detail = f'请求 {request.method} {path}（HTTP {response.status_code}）'
        log_operation(action, target_type, target_id, detail)
    except Exception:
        pass
    return response