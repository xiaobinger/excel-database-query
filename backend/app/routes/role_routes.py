from flask import Blueprint, request, jsonify
from app import db
from app.models.role import Role
from app.models.user import User
from app.utils.auth import admin_required

role_bp = Blueprint('roles', __name__, url_prefix='/api/roles')


@role_bp.route('', methods=['GET'])
@admin_required
def get_roles():
    roles = Role.query.order_by(Role.created_at.desc()).all()
    return jsonify({
        'success': True,
        'data': [r.to_dict() for r in roles],
        'total': len(roles),
    })


@role_bp.route('', methods=['POST'])
@admin_required
def create_role():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    name = data.get('name', '')
    if not name:
        return jsonify({'success': False, 'message': 'Role name is required'}), 400

    existing = Role.query.filter_by(name=name).first()
    if existing:
        return jsonify({'success': False, 'message': 'Role name already exists'}), 400

    try:
        role = Role(
            name=name,
            description=data.get('description', ''),
            is_admin=data.get('is_admin', False),
        )

        if 'menu_permissions' in data:
            role.set_menu_permissions(data['menu_permissions'])
        if 'button_permissions' in data:
            role.set_button_permissions(data['button_permissions'])

        db.session.add(role)
        db.session.commit()

        return jsonify({'success': True, 'data': role.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@role_bp.route('/<int:role_id>', methods=['PUT'])
@admin_required
def update_role(role_id):
    role = Role.query.get(role_id)
    if not role:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Request data is empty'}), 400

    try:
        if 'name' in data:
            new_name = data['name']
            existing = Role.query.filter(Role.name == new_name, Role.id != role_id).first()
            if existing:
                return jsonify({'success': False, 'message': 'Role name already exists'}), 400
            role.name = new_name

        if 'description' in data:
            role.description = data['description']

        if 'is_admin' in data:
            role.is_admin = data['is_admin']

        if 'menu_permissions' in data:
            role.set_menu_permissions(data['menu_permissions'])

        if 'button_permissions' in data:
            role.set_button_permissions(data['button_permissions'])

        db.session.commit()

        return jsonify({'success': True, 'data': role.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@role_bp.route('/<int:role_id>', methods=['DELETE'])
@admin_required
def delete_role(role_id):
    role = Role.query.get(role_id)
    if not role:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    user_count = User.query.filter_by(role_id=role_id).count()
    if user_count > 0:
        return jsonify({
            'success': False,
            'message': f'Cannot delete role with {user_count} associated user(s). Please reassign users first.'
        }), 400

    try:
        db.session.delete(role)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Role deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
