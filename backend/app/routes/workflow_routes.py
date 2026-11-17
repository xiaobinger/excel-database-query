"""混合工作流路由

- 工作流 CRUD
- 能力清单（脚本/数据库/系统任务/审批人）
- 一键启动
- 执行记录与详情
- 人工审批（通过/拒绝）
- 取消执行
"""
from flask import Blueprint, request, jsonify, g

from app.utils.auth import login_required
import app.services.workflow_service as workflow_service

workflow_bp = Blueprint('workflow', __name__, url_prefix='/api/workflows')


def _current_user():
    user = getattr(g, 'user', None)
    user_id = getattr(g, 'user_id', None)
    username = getattr(user, 'username', '') if user else ''
    display_name = getattr(user, 'display_name', '') if user else ''
    return user_id, username, display_name or username


@workflow_bp.route('', methods=['GET'])
@login_required
def list_workflows():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    keyword = request.args.get('keyword')
    data = workflow_service.get_workflows(page=page, per_page=per_page, keyword=keyword)
    return jsonify({'success': True, 'data': data})


@workflow_bp.route('/capabilities', methods=['GET'])
@login_required
def capabilities():
    return jsonify({'success': True, 'data': workflow_service.get_capabilities()})


@workflow_bp.route('/runs', methods=['GET'])
@login_required
def list_runs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    workflow_id = request.args.get('workflow_id', type=int)
    status = request.args.get('status')
    data = workflow_service.get_runs(page=page, per_page=per_page,
                                     workflow_id=workflow_id, status=status)
    return jsonify({'success': True, 'data': data})


@workflow_bp.route('/runs/<run_id>', methods=['GET'])
@login_required
def get_run(run_id):
    data = workflow_service.get_run_detail(run_id)
    if not data:
        return jsonify({'success': False, 'message': '执行记录不存在'}), 404
    return jsonify({'success': True, 'data': data})


@workflow_bp.route('/runs/<run_id>/approve', methods=['POST'])
@login_required
def approve_run(run_id):
    data = request.get_json() or {}
    if 'approved' not in data:
        return jsonify({'success': False, 'message': '请提供审批结果 approved'}), 400
    user_id, username, display_name = _current_user()
    ok, message = workflow_service.approve_run(
        run_id,
        approved=bool(data.get('approved')),
        comment=data.get('comment') or '',
        approver_name=display_name or username,
        approver_id=user_id,
    )
    if not ok:
        return jsonify({'success': False, 'message': message}), 400
    return jsonify({'success': True, 'message': message,
                    'data': workflow_service.get_run_detail(run_id)})


@workflow_bp.route('/runs/<run_id>/cancel', methods=['POST'])
@login_required
def cancel_run(run_id):
    ok, message = workflow_service.cancel_run(run_id)
    if not ok:
        return jsonify({'success': False, 'message': message}), 400
    return jsonify({'success': True, 'message': message})


@workflow_bp.route('', methods=['POST'])
@login_required
def create_workflow():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'success': False, 'message': '请填写工作流名称'}), 400
    user_id, _, _ = _current_user()
    result = workflow_service.create_workflow(data, created_by=user_id)
    return jsonify({'success': True, 'data': result})


@workflow_bp.route('/<int:workflow_id>', methods=['GET'])
@login_required
def get_workflow(workflow_id):
    data = workflow_service.get_workflow(workflow_id)
    if not data:
        return jsonify({'success': False, 'message': '工作流不存在'}), 404
    return jsonify({'success': True, 'data': data})


@workflow_bp.route('/<int:workflow_id>', methods=['PUT'])
@login_required
def update_workflow(workflow_id):
    data = request.get_json() or {}
    result = workflow_service.update_workflow(workflow_id, data)
    if not result:
        return jsonify({'success': False, 'message': '工作流不存在'}), 404
    return jsonify({'success': True, 'data': result})


@workflow_bp.route('/<int:workflow_id>', methods=['DELETE'])
@login_required
def delete_workflow(workflow_id):
    ok = workflow_service.delete_workflow(workflow_id)
    if not ok:
        return jsonify({'success': False, 'message': '工作流不存在'}), 404
    return jsonify({'success': True, 'message': '已删除'})


@workflow_bp.route('/<int:workflow_id>/run', methods=['POST'])
@login_required
def run_workflow(workflow_id):
    data = request.get_json() or {}
    user_id, _, _ = _current_user()
    try:
        result = workflow_service.start_run(workflow_id, inputs=data.get('inputs') or {},
                                            created_by=user_id)
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    return jsonify({'success': True, 'data': result})