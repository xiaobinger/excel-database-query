from flask import Blueprint, request, jsonify, g
from app import db
from app.models.user import User
from app.models.role import Role
from app.utils.auth import admin_required

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

        db.session.add(user)
        db.session.commit()

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

        db.session.commit()

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
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


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
