from flask import Blueprint, request, jsonify, g
from app import db
from app.models.user import User
from app.models.role import Role
from app.utils.auth import admin_required
from app.utils.operation_logger import log_operation

user_bp = Blueprint('users', __name__, url_prefix='/api/users')


@user_bp.route('', methods=['GET'])
@admin_required
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '')

    query = User.query
    if keyword:
        query = query.filter(
            db.or_(
                User.username.contains(keyword),
                User.display_name.contains(keyword),
            )
        )
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    users = []
    for user in pagination.items:
        user_dict = user.to_dict_with_role()
        users.append(user_dict)

    return jsonify({
        'success': True,
        'data': users,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@user_bp.route('', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required'}), 400

    existing = User.query.filter_by(username=username).first()
    if existing:
        return jsonify({'success': False, 'message': 'Username already exists'}), 400

    try:
        user = User(
            username=username,
            display_name=data.get('display_name', ''),
            gender=data.get('gender', 'male'),
            phone=data.get('phone', ''),
            role_id=data.get('role_id'),
            is_active=data.get('is_active', True),
        )
        user.set_password(password)

        if 'script_ids' in data:
            user.set_script_ids(data['script_ids'])

        if 'auto_task_ids' in data:
            user.set_auto_task_ids(data['auto_task_ids'])

        if 'system_task_ids' in data:
            user.set_system_task_ids(data['system_task_ids'])

        db.session.add(user)
        db.session.commit()

        log_operation('create', 'user', user.id, f'创建用户: {user.username}')
        return jsonify({'success': True, 'data': user.to_dict_with_role()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@user_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    try:
        if 'username' in data:
            new_username = data['username']
            existing = User.query.filter(User.username == new_username, User.id != user_id).first()
            if existing:
                return jsonify({'success': False, 'message': 'Username already exists'}), 400
            user.username = new_username

        if 'display_name' in data:
            user.display_name = data['display_name']

        if 'gender' in data:
            user.gender = data['gender']

        if 'phone' in data:
            user.phone = data['phone']

        if 'role_id' in data:
            user.role_id = data['role_id']

        if 'is_active' in data:
            user.is_active = data['is_active']

        if 'password' in data and data['password']:
            user.set_password(data['password'])

        if 'script_ids' in data:
            user.set_script_ids(data['script_ids'])

        if 'auto_task_ids' in data:
            user.set_auto_task_ids(data['auto_task_ids'])

        if 'system_task_ids' in data:
            user.set_system_task_ids(data['system_task_ids'])

        db.session.commit()

        log_operation('update', 'user', user.id, f'更新用户信息: {user.username}')
        return jsonify({'success': True, 'data': user.to_dict_with_role()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@user_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    current_user = g.user
    if current_user and current_user.id == user_id:
        return jsonify({'success': False, 'message': 'Cannot delete yourself'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        log_operation('delete', 'user', user_id, f'删除用户: {username}')
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@user_bp.route('/batch-delete', methods=['POST'])
@admin_required
def batch_delete_users():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    current_user = g.user
    deleted_count = 0
    for uid in ids:
        if current_user and current_user.id == uid:
            continue
        user = User.query.get(uid)
        if user:
            db.session.delete(user)
            deleted_count += 1

    try:
        db.session.commit()
        log_operation('batch_delete', 'user', None, f'批量删除用户: {deleted_count}个 (IDs: {ids})')
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个用户', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@user_bp.route('/all', methods=['DELETE'])
@admin_required
def delete_all_users():
    current_user = g.user
    try:
        query = User.query
        if current_user:
            query = query.filter(User.id != current_user.id)
        deleted_count = query.delete()
        db.session.commit()
        log_operation('delete_all', 'user', None, f'删除全部用户: {deleted_count}个')
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个用户', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@user_bp.route('/<int:user_id>/avatar', methods=['POST'])
@admin_required
def set_user_avatar(user_id):
    """管理员为用户设置头像"""
    from flask import current_app
    from werkzeug.utils import secure_filename
    import os
    import uuid

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '请选择图片文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400

    allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_ext:
        return jsonify({'success': False, 'message': '仅支持 PNG/JPG/GIF/WEBP/BMP 格式'}), 400

    base_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'))
    avatar_dir = os.path.join(base_dir, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)

    ext = file.filename.rsplit('.', 1)[1].lower()
    new_filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(avatar_dir, new_filename)
    file.save(filepath)

    if user.avatar:
        old_path = os.path.join(avatar_dir, os.path.basename(user.avatar))
        if os.path.exists(old_path):
            os.remove(old_path)

    user.avatar = new_filename
    db.session.commit()

    log_operation('update', 'user', user.id, f'管理员设置用户头像: {user.username}')
    return jsonify({
        'success': True,
        'message': '头像设置成功',
        'data': {'avatar': user.avatar},
    })


@user_bp.route('/<int:user_id>/avatar', methods=['DELETE'])
@admin_required
def delete_user_avatar(user_id):
    """管理员删除用户头像"""
    import os
    from flask import current_app

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if user.avatar:
        base_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'))
        avatar_dir = os.path.join(base_dir, 'avatars')
        filepath = os.path.join(avatar_dir, os.path.basename(user.avatar))
        if os.path.exists(filepath):
            os.remove(filepath)
        user.avatar = None
        db.session.commit()
        log_operation('delete', 'user', user.id, f'管理员删除用户头像: {user.username}')

    return jsonify({'success': True, 'message': '头像已删除'})


@user_bp.route('/<int:user_id>/scripts', methods=['PUT'])
@admin_required
def set_user_scripts(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    script_ids = data.get('script_ids', [])
    if not isinstance(script_ids, list):
        return jsonify({'success': False, 'message': 'script_ids must be an array'}), 400

    try:
        user.set_script_ids(script_ids)
        db.session.commit()
        log_operation('update', 'user', user.id, f'设置用户查询选项: {user.username} -> {script_ids}')

        return jsonify({
            'success': True,
            'data': {
                'user_id': user.id,
                'script_ids': user.get_script_ids(),
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
