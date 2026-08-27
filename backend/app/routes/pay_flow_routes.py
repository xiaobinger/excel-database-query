"""代付流程编排路由

- 流程模板 CRUD
- 发起代付流程
- 执行记录查询
- 流程走势
- 取消/重试
"""
from flask import Blueprint, request, jsonify
from app.utils.auth import login_required
import app.services.pay_flow_service as flow_service

pay_flow_bp = Blueprint('pay_flow', __name__, url_prefix='/api/pay-flow')


# ---------------------------------------------------------------------------
# 模板管理
# ---------------------------------------------------------------------------

@pay_flow_bp.route('/templates', methods=['GET'])
@login_required
def list_templates():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword')
    result = flow_service.get_templates(page=page, per_page=per_page, keyword=keyword)
    return jsonify({'success': True, 'data': result})


@pay_flow_bp.route('/templates/<int:template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    t = flow_service.get_template(template_id)
    if not t:
        return jsonify({'success': False, 'message': '模板不存在'}), 404
    return jsonify({'success': True, 'data': t})


@pay_flow_bp.route('/templates', methods=['POST'])
@login_required
def create_template():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'message': '请填写模板名称'}), 400
    from flask import g
    user_id = g.get('user_id') if hasattr(g, 'user_id') else None
    result = flow_service.create_template(data, created_by=user_id)
    return jsonify({'success': True, 'data': result})


@pay_flow_bp.route('/templates/<int:template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    data = request.get_json()
    result = flow_service.update_template(template_id, data)
    if not result:
        return jsonify({'success': False, 'message': '模板不存在'}), 404
    return jsonify({'success': True, 'data': result})


@pay_flow_bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    ok = flow_service.delete_template(template_id)
    if not ok:
        return jsonify({'success': False, 'message': '模板不存在'}), 404
    return jsonify({'success': True, 'message': '已删除'})


@pay_flow_bp.route('/node-fields', methods=['GET'])
@login_required
def node_fields():
    """返回节点字段定义，供前端编排页面使用"""
    from app.services.pay_flow_service import NODE_FIELDS, OPERATORS
    return jsonify({'success': True, 'data': {'node_fields': NODE_FIELDS, 'operators': OPERATORS}})


# ---------------------------------------------------------------------------
# 通知模板管理
# ---------------------------------------------------------------------------

@pay_flow_bp.route('/notify-templates', methods=['GET'])
@login_required
def list_notify_templates():
    from app.models.pay_flow import PayFlowNotifyTemplate
    keyword = request.args.get('keyword')
    query = PayFlowNotifyTemplate.query
    if keyword:
        query = query.filter(PayFlowNotifyTemplate.name.contains(keyword))
    items = query.order_by(PayFlowNotifyTemplate.id.desc()).all()
    return jsonify({'success': True, 'data': [t.to_dict() for t in items]})


@pay_flow_bp.route('/notify-templates/<int:tpl_id>', methods=['GET'])
@login_required
def get_notify_template(tpl_id):
    from app.models.pay_flow import PayFlowNotifyTemplate
    t = PayFlowNotifyTemplate.query.get(tpl_id)
    if not t:
        return jsonify({'success': False, 'message': '通知模板不存在'}), 404
    return jsonify({'success': True, 'data': t.to_dict()})


@pay_flow_bp.route('/notify-templates', methods=['POST'])
@login_required
def create_notify_template():
    from flask import g
    from app.models.pay_flow import PayFlowNotifyTemplate
    from app import db
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'message': '请填写模板名称'}), 400
    user_id = g.get('user_id') if hasattr(g, 'user_id') else None
    t = PayFlowNotifyTemplate(
        name=data['name'],
        description=data.get('description', ''),
        title=data.get('title', ''),
        content=data.get('content', ''),
        webhook_url=data.get('webhook_url', ''),
        receivers=data.get('receivers', ''),
        is_enabled=data.get('is_enabled', True),
        created_by=user_id,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({'success': True, 'data': t.to_dict()})


@pay_flow_bp.route('/notify-templates/<int:tpl_id>', methods=['PUT'])
@login_required
def update_notify_template(tpl_id):
    from app.models.pay_flow import PayFlowNotifyTemplate
    from app import db
    data = request.get_json()
    t = PayFlowNotifyTemplate.query.get(tpl_id)
    if not t:
        return jsonify({'success': False, 'message': '通知模板不存在'}), 404
    for field in ('name', 'description', 'title', 'content', 'webhook_url', 'receivers', 'is_enabled'):
        if field in data:
            setattr(t, field, data[field])
    db.session.commit()
    return jsonify({'success': True, 'data': t.to_dict()})


@pay_flow_bp.route('/notify-templates/<int:tpl_id>', methods=['DELETE'])
@login_required
def delete_notify_template(tpl_id):
    from app.models.pay_flow import PayFlowNotifyTemplate
    from app import db
    t = PayFlowNotifyTemplate.query.get(tpl_id)
    if not t:
        return jsonify({'success': False, 'message': '通知模板不存在'}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({'success': True, 'message': '已删除'})


# ---------------------------------------------------------------------------
# 发起流程
# ---------------------------------------------------------------------------

@pay_flow_bp.route('/start', methods=['POST'])
@login_required
def start_flow():
    """发起代付流程

    请求体:
    {
        "template_id": 1,
        "file_path": "uploads/pay/xxx.xlsx",
        "sheet_index": 0,
        "params": {"channel": "helipay", "interface_type": "代付", "environment": "test"}
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求体不能为空'}), 400

    template_id = data.get('template_id')
    file_path = data.get('file_path', '')
    sheet_index = data.get('sheet_index', 0)
    params = data.get('params', {})

    if not template_id:
        return jsonify({'success': False, 'message': '请选择流程模板'}), 400
    if not file_path:
        return jsonify({'success': False, 'message': '文件路径不能为空'}), 400

    from flask import g
    user_id = g.get('user_id') if hasattr(g, 'user_id') else None

    import os
    from app.services import pay_service

    if not os.path.exists(file_path):
        return jsonify({'success': False, 'message': '上传文件不存在，请重新上传'}), 400

    try:
        rows = pay_service._load_rows(file_path, sheet_index=sheet_index)
        if not rows:
            return jsonify({'success': False, 'message': '工作表无数据行'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取文件失败: {e}'}), 400

    try:
        batch_id, execution_ids = flow_service.start_flow(template_id, rows, params, created_by=user_id)
        return jsonify({
            'success': True,
            'data': {
                'batch_id': batch_id,
                'execution_ids': execution_ids,
                'total': len(execution_ids),
                'summary_notify_enabled': bool(params.get('summary_notify_enabled')),
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'发起流程失败: {e}'}), 500


# ---------------------------------------------------------------------------
# 执行记录
# ---------------------------------------------------------------------------

@pay_flow_bp.route('/executions', methods=['GET'])
@login_required
def list_executions():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    batch_id = request.args.get('batch_id')
    status = request.args.get('status')
    result = flow_service.get_executions(batch_id=batch_id, status=status, page=page, per_page=per_page)
    return jsonify({'success': True, 'data': result})


@pay_flow_bp.route('/executions/<execution_id>', methods=['GET'])
@login_required
def get_execution(execution_id):
    detail = flow_service.get_execution_detail(execution_id)
    if not detail:
        return jsonify({'success': False, 'message': '执行记录不存在'}), 404
    return jsonify({'success': True, 'data': detail})


@pay_flow_bp.route('/executions/<execution_id>/cancel', methods=['POST'])
@login_required
def cancel_execution(execution_id):
    ok = flow_service.cancel_execution(execution_id)
    if not ok:
        return jsonify({'success': False, 'message': '取消失败，流程可能已完成'}), 400
    return jsonify({'success': True, 'message': '已取消'})


@pay_flow_bp.route('/executions/<execution_id>/retry', methods=['POST'])
@login_required
def retry_execution(execution_id):
    ok = flow_service.retry_execution(execution_id)
    if not ok:
        return jsonify({'success': False, 'message': '重试失败，流程状态不允许'}), 400
    return jsonify({'success': True, 'message': '已重试'})


@pay_flow_bp.route('/executions/<execution_id>', methods=['DELETE'])
@login_required
def delete_execution(execution_id):
    ok = flow_service.delete_execution(execution_id)
    if not ok:
        return jsonify({'success': False, 'message': '删除失败，执行记录不存在或正在运行中'}), 400
    return jsonify({'success': True, 'message': '已删除'})


@pay_flow_bp.route('/executions/batch-delete', methods=['POST'])
@login_required
def batch_delete_executions():
    data = request.get_json()
    if not data or not isinstance(data.get('ids'), list):
        return jsonify({'success': False, 'message': '请提供要删除的执行ID列表'}), 400
    ids = data['ids']
    deleted, skipped = flow_service.batch_delete_executions(ids)
    if deleted == 0:
        return jsonify({'success': False, 'message': '未删除任何记录，可能记录不存在或正在运行中', 'skipped': skipped}), 400
    return jsonify({'success': True, 'message': f'已删除 {deleted} 条记录', 'deleted': deleted, 'skipped': skipped})


# ---------------------------------------------------------------------------
# 批次
# ---------------------------------------------------------------------------

@pay_flow_bp.route('/batches', methods=['GET'])
@login_required
def list_batches():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword')
    result = flow_service.get_batches(page=page, per_page=per_page, keyword=keyword)
    return jsonify({'success': True, 'data': result})


@pay_flow_bp.route('/batches/<batch_id>/summary', methods=['GET'])
@login_required
def batch_summary(batch_id):
    summary = flow_service.get_batch_summary(batch_id)
    return jsonify({'success': True, 'data': summary})


@pay_flow_bp.route('/batches/<batch_id>/detail', methods=['GET'])
@login_required
def batch_detail(batch_id):
    detail = flow_service.get_batch_detail(batch_id)
    if not detail:
        return jsonify({'success': False, 'message': '批次不存在或无执行记录'}), 404
    return jsonify({'success': True, 'data': detail})


@pay_flow_bp.route('/batches/<batch_id>/retry', methods=['POST'])
@login_required
def retry_batch(batch_id):
    success, message = flow_service.retry_batch(batch_id)
    if not success:
        return jsonify({'success': False, 'message': message}), 400
    return jsonify({'success': True, 'message': message})


@pay_flow_bp.route('/batches/<batch_id>/executions', methods=['GET'])
@login_required
def batch_executions(batch_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    result = flow_service.get_executions(batch_id=batch_id, page=page, per_page=per_page)
    return jsonify({'success': True, 'data': result})
