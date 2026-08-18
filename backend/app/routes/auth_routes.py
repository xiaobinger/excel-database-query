from flask import Blueprint, request, jsonify
from app import db
from app.models.user import User
from app.models.script import Script
from app.utils.auth import generate_token, login_required, get_current_user
from app.utils.rate_limiter import login_rate_limiter

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _get_client_ip():
    """Get real client IP considering proxy headers."""
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    xri = request.headers.get('X-Real-IP', '')
    if xri:
        return xri.strip()
    return request.remote_addr or '127.0.0.1'


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    username = data.get('username', '')
    password = data.get('password', '')
    client_ip = _get_client_ip()

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required'}), 400

    # Rate limiting check
    allowed, reason = login_rate_limiter.check_rate_limit(client_ip, username)
    if not allowed:
        return jsonify({'success': False, 'message': reason}), 429

    # Check account lockout
    if login_rate_limiter.is_account_locked(username):
        return jsonify({'success': False, 'message': 'Account locked due to too many failed attempts. Please try again later.'}), 429

    user = User.query.filter_by(username=username).first()
    if not user:
        login_rate_limiter.record_attempt(client_ip, username, False)
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    if not user.is_active:
        return jsonify({'success': False, 'message': 'User is disabled'}), 401

    if not user.check_password(password):
        login_rate_limiter.record_attempt(client_ip, username, False)
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    # Successful login - record and continue
    login_rate_limiter.record_attempt(client_ip, username, True)

    token = generate_token(user.id)

    user_data = user.to_dict_with_role()

    allowed_scripts = []
    if user.is_admin():
        allowed_scripts = [s.to_dict() for s in Script.query.filter_by(is_active=True).all()]
    else:
        user_script_ids = user.get_script_ids()
        if user_script_ids:
            scripts = Script.query.filter(
                Script.id.in_(user_script_ids),
                Script.is_active == True
            ).all()
            allowed_scripts = [s.to_dict() for s in scripts]

    user_data['allowed_scripts'] = allowed_scripts

    return jsonify({
        'success': True,
        'data': {
            'token': token,
            'user': user_data,
        }
    })


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_me():
    user = get_current_user()
    if not user:
        return jsonify({'success': True, 'data': None})

    user_data = user.to_dict_with_role()

    allowed_scripts = []
    if user.is_admin():
        allowed_scripts = [s.to_dict() for s in Script.query.filter_by(is_active=True).all()]
    else:
        user_script_ids = user.get_script_ids()
        if user_script_ids:
            scripts = Script.query.filter(
                Script.id.in_(user_script_ids),
                Script.is_active == True
            ).all()
            allowed_scripts = [s.to_dict() for s in scripts]

    user_data['allowed_scripts'] = allowed_scripts

    return jsonify({
        'success': True,
        'data': user_data,
    })


@auth_bp.route('/password', methods=['PUT'])
@login_required
def change_password():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return jsonify({'success': False, 'message': 'Old password and new password are required'}), 400

    if not user.check_password(old_password):
        return jsonify({'success': False, 'message': 'Old password is incorrect'}), 400

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400

    user.set_password(new_password)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Password changed successfully'})
