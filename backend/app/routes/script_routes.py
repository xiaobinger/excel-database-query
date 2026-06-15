import json
from flask import Blueprint, request, jsonify
from app import db
from app.models.script import Script
from app.utils.sql_validator import SQLValidator
from app.utils.auth import login_required, get_current_user
from app.utils.behavior_tracker import track_behavior
from app.utils.sql_template import render_sql_template, get_template_preview

script_bp = Blueprint('script', __name__, url_prefix='/api/scripts')


@script_bp.route('', methods=['GET'])
@login_required
def get_scripts():
    tag = request.args.get('tag')
    script_type = request.args.get('type')
    query = Script.query.filter_by(is_active=True)
    if tag:
        query = query.filter_by(tag=tag)
    if script_type:
        query = query.filter_by(type=script_type)
    scripts = query.order_by(Script.created_at.desc()).all()

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_script_ids()
        scripts = [s for s in scripts if s.id in allowed_ids]

    return jsonify({
        'success': True,
        'data': [s.to_dict() for s in scripts],
        'total': len(scripts),
    })


@script_bp.route('/<int:script_id>', methods=['GET'])
def get_script(script_id):
    script = Script.query.get(script_id)
    if not script:
        return jsonify({'success': False, 'message': '脚本不存在'}), 404
    return jsonify({'success': True, 'data': script.to_dict()})


@script_bp.route('', methods=['POST'])
def create_script():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    required = ['name', 'sql_text']
    for field in required:
        if field not in data:
            return jsonify({'success': False, 'message': f'缺少必填字段: {field}'}), 400

    try:
        script = Script(
            name=data['name'],
            description=data.get('description', ''),
            sql_text=data['sql_text'],
            tag=data.get('tag'),
            result_sheet_name=data.get('result_sheet_name', '查询结果'),
            batch_size=data.get('batch_size', 100),
            timeout=data.get('timeout', 30),
            query_mode=data.get('query_mode', 'batch'),
            param_column=data.get('param_column'),
            database_connection_id=data.get('database_connection_id'),
            merge_strategy=data.get('merge_strategy', 'concat'),
            new_sheet=data.get('new_sheet', True),
            primary_key=data.get('primary_key', ''),
            type=data.get('type', 'query'),
            is_template=data.get('is_template', False),
            sql_template=data.get('sql_template', ''),
        )

        if 'database_ids' in data:
            script.set_database_ids(data['database_ids'])
        if 'column_mapping' in data:
            script.set_column_mapping(data['column_mapping'])
        if 'params_config' in data:
            script.set_params_config(data['params_config'])
        if 'template_config' in data:
            script.set_template_config(data['template_config'])

        db.session.add(script)
        db.session.flush()  # 获取script.id

        # 自动将新脚本授权给创建者（非管理员需要显式授权才能看到）
        current_user = get_current_user()
        if current_user and not current_user.is_admin():
            allowed_ids = current_user.get_script_ids()
            if script.id not in allowed_ids:
                allowed_ids.append(script.id)
                current_user.set_script_ids(allowed_ids)

        db.session.commit()

        # 记录用户行为
        if current_user:
            track_behavior(current_user.id, 'create', 'script', script.id, {
                'name': script.name,
                'type': script.type,
                'tag': script.tag,
            })

        return jsonify({'success': True, 'data': script.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@script_bp.route('/<int:script_id>', methods=['PUT'])
def update_script(script_id):
    script = Script.query.get(script_id)
    if not script:
        return jsonify({'success': False, 'message': '脚本不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    try:
        simple_fields = ['name', 'description', 'sql_text', 'tag', 'result_sheet_name',
                         'batch_size', 'timeout', 'query_mode', 'param_column',
                         'database_connection_id', 'merge_strategy', 'new_sheet', 'is_active',
                         'primary_key', 'type', 'is_template', 'sql_template']
        for key in simple_fields:
            if key in data:
                setattr(script, key, data[key])

        if 'database_ids' in data:
            script.set_database_ids(data['database_ids'])
        if 'column_mapping' in data:
            script.set_column_mapping(data['column_mapping'])
        if 'params_config' in data:
            script.set_params_config(data['params_config'])
        if 'template_config' in data:
            script.set_template_config(data['template_config'])

        db.session.commit()

        # 记录用户行为
        current_user = get_current_user()
        if current_user:
            track_behavior(current_user.id, 'edit', 'script', script.id, {
                'name': script.name,
                'type': script.type,
            })

        return jsonify({'success': True, 'data': script.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@script_bp.route('/<int:script_id>', methods=['DELETE'])
def delete_script(script_id):
    script = Script.query.get(script_id)
    if not script:
        return jsonify({'success': False, 'message': '脚本不存在'}), 404

    script.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@script_bp.route('/batch-delete', methods=['POST'])
def batch_delete_scripts():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    deleted_count = 0
    for script_id in ids:
        script = Script.query.get(script_id)
        if script:
            script.is_active = False
            deleted_count += 1

    db.session.commit()
    return jsonify({'success': True, 'message': f'成功删除{deleted_count}个脚本', 'deleted_count': deleted_count})


@script_bp.route('/all', methods=['DELETE'])
def delete_all_scripts():
    try:
        deleted_count = Script.query.filter_by(is_active=True).update({'is_active': False})
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个脚本', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@script_bp.route('/<int:script_id>/validate', methods=['POST'])
def validate_script(script_id):
    script = Script.query.get(script_id)
    if not script:
        return jsonify({'success': False, 'message': '脚本不存在'}), 404

    validator = SQLValidator()
    allow_dml = script.type == 'system'
    result = validator.validate(script.sql_text, allow_dml=allow_dml)
    suggestions = validator.suggest_improvements(script.sql_text)
    return jsonify({
        'success': True,
        'is_valid': result.is_valid,
        'message': result.message,
        'warnings': result.warnings,
        'suggestions': suggestions,
    })


@script_bp.route('/validate', methods=['POST'])
def validate_sql():
    data = request.get_json()
    if not data or 'sql' not in data:
        return jsonify({'success': False, 'message': '缺少SQL语句'}), 400

    validator = SQLValidator()
    allow_dml = data.get('allow_dml', False)
    result = validator.validate(data['sql'], allow_dml=allow_dml)
    suggestions = validator.suggest_improvements(data['sql'])
    return jsonify({
        'success': True,
        'is_valid': result.is_valid,
        'message': result.message,
        'warnings': result.warnings,
        'suggestions': suggestions,
    })


@script_bp.route('/format', methods=['POST'])
def format_sql():
    data = request.get_json()
    if not data or 'sql' not in data:
        return jsonify({'success': False, 'message': '缺少SQL语句'}), 400

    validator = SQLValidator()
    formatted = validator.format_sql(data['sql'])
    return jsonify({
        'success': True,
        'formatted_sql': formatted,
    })


@script_bp.route('/extract-columns', methods=['POST'])
def extract_columns():
    data = request.get_json()
    if not data or 'sql' not in data:
        return jsonify({'success': False, 'message': '缺少SQL语句'}), 400

    validator = SQLValidator()
    columns = validator.extract_column_names(data['sql'])
    return jsonify({
        'success': True,
        'columns': columns,
    })


@script_bp.route('/simplify', methods=['POST'])
def simplify_sql():
    data = request.get_json()
    if not data or 'sql' not in data:
        return jsonify({'success': False, 'message': '缺少SQL语句'}), 400

    import re
    sql = data['sql']
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    sql = re.sub(r'\s+', ' ', sql).strip()
    sql = re.sub(r'\s*,\s*', ', ', sql)
    sql = re.sub(r'\s*=\s*', ' = ', sql)
    return jsonify({
        'success': True,
        'simplified_sql': sql,
    })


@script_bp.route('/tags', methods=['GET'])
def get_tags():
    tags = db.session.query(Script.tag).filter(
        Script.is_active == True,
        Script.tag.isnot(None),
        Script.tag != ''
    ).distinct().all()
    tag_list = [t[0] for t in tags if t[0]]
    return jsonify({'success': True, 'data': tag_list})


@script_bp.route('/render-template', methods=['POST'])
@login_required
def render_template():
    """预览SQL模板渲染结果"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    template = data.get('template', '')
    template_config = data.get('template_config', [])
    params = data.get('params', {})

    if not template:
        return jsonify({'success': False, 'message': '模板内容为空'}), 400

    result = get_template_preview(template, template_config)
    if result['success']:
        return jsonify({'success': True, 'rendered_sql': result['rendered_sql']})
    else:
        return jsonify({'success': False, 'message': result['error']}), 400


@script_bp.route('/<int:script_id>/render-template', methods=['POST'])
@login_required
def render_script_template(script_id):
    """根据已保存的查询选项渲染SQL模板"""
    script = Script.query.get(script_id)
    if not script:
        return jsonify({'success': False, 'message': '脚本不存在'}), 404

    if not script.is_template:
        return jsonify({'success': True, 'rendered_sql': script.sql_text})

    data = request.get_json() or {}
    params = data.get('params', {})

    template_config = script.get_template_config()
    result = get_template_preview(script.sql_template or script.sql_text, template_config)
    if result['success']:
        return jsonify({'success': True, 'rendered_sql': result['rendered_sql']})
    else:
        return jsonify({'success': False, 'message': result['error']}), 400
