from flask import Blueprint, request, jsonify
from app.services.ssh_service import SshService

ssh_bp = Blueprint('ssh', __name__, url_prefix='/api/ssh')


@ssh_bp.route('', methods=['GET'])
def get_ssh_configs():
    configs = SshService.get_all()
    return jsonify({
        'success': True,
        'data': [c.to_dict() for c in configs],
        'total': len(configs),
    })


@ssh_bp.route('/<int:ssh_id>', methods=['GET'])
def get_ssh_config(ssh_id):
    config = SshService.get_by_id(ssh_id)
    if not config:
        return jsonify({'success': False, 'message': 'SSH配置不存在'}), 404
    return jsonify({'success': True, 'data': config.to_dict()})


@ssh_bp.route('', methods=['POST'])
def create_ssh_config():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    required = ['name', 'host', 'username']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'message': f'缺少必填字段: {field}'}), 400

    try:
        config = SshService.create(data)
        return jsonify({'success': True, 'data': config.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@ssh_bp.route('/<int:ssh_id>', methods=['PUT'])
def update_ssh_config(ssh_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    config = SshService.update(ssh_id, data)
    if not config:
        return jsonify({'success': False, 'message': 'SSH配置不存在'}), 404
    return jsonify({'success': True, 'data': config.to_dict()})


@ssh_bp.route('/<int:ssh_id>', methods=['DELETE'])
def delete_ssh_config(ssh_id):
    result = SshService.delete(ssh_id)
    if not result:
        return jsonify({'success': False, 'message': 'SSH配置不存在或已被数据库连接引用，无法删除'}), 400
    return jsonify({'success': True, 'message': '删除成功'})


@ssh_bp.route('/<int:ssh_id>/test', methods=['POST'])
def test_ssh_config(ssh_id):
    result = SshService.test_connection(ssh_id)
    return jsonify(result)
