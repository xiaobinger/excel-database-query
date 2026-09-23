from flask import Blueprint, request, jsonify, g
from app import db
from app.models.user import User
from app.models.script import Script
from app.models.login_log import LoginLog
from app.utils.auth import generate_token, login_required, get_current_user
from app.utils.rate_limiter import login_rate_limiter
from app.utils.operation_logger import log_operation

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# AI宠物可选造型白名单
PET_STYLES = ('robot', 'cat', 'bunny', 'panda', 'bear', 'fox', 'pig', 'frog', 'koala', 'chick')


def _get_client_ip():
    """Get real client IP considering proxy headers."""
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    xri = request.headers.get('X-Real-IP', '')
    if xri:
        return xri.strip()
    return request.remote_addr or '127.0.0.1'


def _record_login_log(username, user_id, status, fail_reason=None):
    """记录登录日志"""
    try:
        log = LoginLog(
            user_id=user_id,
            username=username,
            ip_address=_get_client_ip(),
            user_agent=request.headers.get('User-Agent', '')[:500],
            status=status,
            fail_reason=fail_reason,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


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

    # 账号锁定检查（优先于任何数据库查询，锁定后直接返回不校验密码）
    if login_rate_limiter.is_account_locked(username):
        return jsonify({'success': False, 'message': 'Account locked due to too many failed attempts. Please try again later.'}), 429

    # 频率限制检查
    allowed, reason = login_rate_limiter.check_rate_limit(client_ip, username)
    if not allowed:
        return jsonify({'success': False, 'message': reason}), 429

    user = User.query.filter_by(username=username).first()
    if not user:
        login_rate_limiter.record_attempt(client_ip, username, False)
        _record_login_log(username, None, 'failed', '用户不存在')
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    if not user.is_active:
        _record_login_log(username, user.id, 'failed', '账号已禁用')
        return jsonify({'success': False, 'message': 'User is disabled'}), 401

    if not user.check_password(password):
        login_rate_limiter.record_attempt(client_ip, username, False)
        _record_login_log(username, user.id, 'failed', '密码错误')
        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401

    # Successful login - record and continue
    login_rate_limiter.record_attempt(client_ip, username, True)
    _record_login_log(username, user.id, 'success')

    g.user = user
    log_operation('login', 'auth', user.id, f'用户登录：{user.username}')

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


@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """更新个人资料"""
    user = get_current_user()
    data = request.get_json() or {}

    if 'display_name' in data:
        user.display_name = (data['display_name'] or '').strip() or None
    if 'phone' in data:
        user.phone = (data['phone'] or '').strip() or None
    if 'gender' in data and data['gender'] in ('male', 'female', 'other'):
        user.gender = data['gender']
    if 'pet_enabled' in data and isinstance(data['pet_enabled'], bool):
        user.pet_enabled = data['pet_enabled']
    if 'pet_style' in data and data['pet_style'] in PET_STYLES:
        user.pet_style = data['pet_style']

    db.session.commit()
    return jsonify({'success': True, 'message': '资料已更新', 'data': user.to_dict_with_role()})


import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

def _get_avatar_folder():
    """获取头像存储绝对路径"""
    base_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'))
    avatar_dir = os.path.join(base_dir, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)
    return avatar_dir


def _allowed_avatar(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


@auth_bp.route('/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """上传头像"""
    user = get_current_user()
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请选择图片文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400

    if not _allowed_avatar(file.filename):
        return jsonify({'success': False, 'message': '仅支持 PNG/JPG/GIF/WEBP/BMP 格式'}), 400

    # 保存文件
    avatar_dir = _get_avatar_folder()
    ext = file.filename.rsplit('.', 1)[1].lower()
    new_filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(avatar_dir, new_filename)
    file.save(filepath)

    # 删除旧头像
    if user.avatar:
        old_path = os.path.join(avatar_dir, os.path.basename(user.avatar))
        if os.path.exists(old_path):
            os.remove(old_path)

    user.avatar = new_filename
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '头像上传成功',
        'data': {'avatar': user.avatar},
    })


@auth_bp.route('/avatar', methods=['DELETE'])
@login_required
def delete_avatar():
    """删除头像"""
    user = get_current_user()
    if user.avatar:
        avatar_dir = _get_avatar_folder()
        filepath = os.path.join(avatar_dir, os.path.basename(user.avatar))
        if os.path.exists(filepath):
            os.remove(filepath)
        user.avatar = None
        db.session.commit()
    return jsonify({'success': True, 'message': '头像已删除'})


@auth_bp.route('/avatar/<filename>', methods=['GET'])
def serve_avatar(filename):
    """提供头像文件访问"""
    from flask import send_from_directory, current_app
    avatar_dir = _get_avatar_folder()
    return send_from_directory(avatar_dir, filename)
