import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app
from app.models.user import User


def generate_token(user_id):
    secret_key = current_app.config.get('JWT_SECRET_KEY', 'excel-query-secret-key-2024')
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow(),
    }
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token


def verify_token(token):
    secret_key = current_app.config.get('JWT_SECRET_KEY', 'excel-query-secret-key-2024')
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        g.user_id = None
        g.user = None

        if token:
            payload = verify_token(token)
            if payload is None:
                return jsonify({'success': False, 'message': 'Token invalid or expired'}), 401
            g.user_id = payload.get('user_id')
            user = User.query.get(g.user_id)
            if user and not user.is_active:
                return jsonify({'success': False, 'message': 'User is disabled'}), 401
            g.user = user

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        if not token:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        payload = verify_token(token)
        if payload is None:
            return jsonify({'success': False, 'message': 'Token invalid or expired'}), 401

        user_id = payload.get('user_id')
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 401

        if not user.is_active:
            return jsonify({'success': False, 'message': 'User is disabled'}), 401

        if not user.is_admin():
            return jsonify({'success': False, 'message': 'Admin permission required'}), 403

        g.user_id = user_id
        g.user = user

        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    user_id = getattr(g, 'user_id', None)
    if user_id:
        return getattr(g, 'user', None) or User.query.get(user_id)
    return None


def permission_required(menu_key: str):
    """Decorator that checks if the user has access to a specific menu.
    Admin users always pass. Non-admin users must have the menu_key in their role's menu_permissions."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]

            if not token:
                return jsonify({'success': False, 'message': 'Authentication required'}), 401

            payload = verify_token(token)
            if payload is None:
                return jsonify({'success': False, 'message': 'Token invalid or expired'}), 401

            user_id = payload.get('user_id')
            user = User.query.get(user_id)
            if not user:
                return jsonify({'success': False, 'message': 'User not found'}), 401

            if not user.is_active:
                return jsonify({'success': False, 'message': 'User is disabled'}), 401

            # Admin users always have access
            if user.is_admin():
                g.user_id = user_id
                g.user = user
                return f(*args, **kwargs)

            # Check menu permission
            role = user.role
            if not role:
                return jsonify({'success': False, 'message': 'No role assigned'}), 403

            menu_perms = role.get_menu_permissions() or []
            if menu_key not in menu_perms:
                return jsonify({'success': False, 'message': f'Permission denied: {menu_key}'}), 403

            g.user_id = user_id
            g.user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator
