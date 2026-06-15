import os
import json
import uuid
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context, g
from app import db
from app.services.query_service import QueryService
from app.services.excel_service import ExcelService
from app.models.query_task import QueryTask
from app.models.script import Script
from app.models.database import DatabaseConnection
from app.utils.sql_validator import SQLValidator
from app.utils.auth import login_required, get_current_user
from app.utils.behavior_tracker import track_behavior
from app.utils.error_sanitizer import sanitize_error_for_user
import time

query_bp = Blueprint('query', __name__, url_prefix='/api/query')


@query_bp.route('/execute', methods=['POST'])
@login_required
def execute_query():
    script_id = request.form.get('script_id', type=int)
    script_ids_str = request.form.get('script_ids', '')
    param_column = request.form.get('param_column')
    merge_strategy = request.form.get('merge_strategy', 'concat')
    new_sheet = request.form.get('new_sheet', 'true')
    column_mapping_str = request.form.get('column_mapping', '{}')
    primary_key = request.form.get('primary_key', '')

    try:
        column_mapping = json.loads(column_mapping_str) if column_mapping_str else {}
    except (json.JSONDecodeError, TypeError):
        column_mapping = {}

    if script_ids_str:
        try:
            script_ids = json.loads(script_ids_str)
        except (json.JSONDecodeError, TypeError):
            script_ids = [int(x.strip()) for x in script_ids_str.split(',') if x.strip()]
    elif script_id:
        script_ids = [script_id]
    else:
        return jsonify({'success': False, 'message': '缺少查询选项'}), 400

    if not script_ids:
        return jsonify({'success': False, 'message': '缺少查询选项'}), 400

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_script_ids()
        script_ids = [sid for sid in script_ids if sid in allowed_ids]
        if not script_ids:
            return jsonify({'success': False, 'message': 'No permission to use the selected query options'}), 403

    if 'file' not in request.files and not request.form.get('file_path'):
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    # 文件来源：1.新上传的文件 2.已上传到服务器的文件路径
    file_path_param = request.form.get('file_path', '')
    if file_path_param and os.path.isfile(file_path_param):
        input_path = file_path_param
    else:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '未上传文件'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '未选择文件'}), 400

        allowed_ext = current_app.config.get('ALLOWED_UPLOAD_EXTENSIONS', {'xlsx', 'xls', 'csv'})
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_ext:
            return jsonify({'success': False, 'message': f'仅支持 {", ".join(sorted(allowed_ext))} 格式'}), 400

        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        input_path = os.path.join(upload_dir, filename)
        file.save(input_path)

    try:
        output_dir = current_app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        all_db_ids = []
        for sid in script_ids:
            script = Script.query.get(sid)
            if script:
                db_ids = script.get_database_ids()
                all_db_ids.extend(db_ids)
        all_db_ids = list(set(all_db_ids))

        new_sheet_bool = new_sheet.lower() in ('true', '1', 'yes')

        task = QueryService.create_task(
            script_id=script_ids[0] if len(script_ids) == 1 else script_ids[0],
            db_connection_ids=all_db_ids,
            input_file=input_path,
            merge_strategy=merge_strategy
        )
        task.database_ids = json.dumps(all_db_ids)
        if current_user:
            task.created_by = current_user.id
        db.session.commit()

        QueryService.execute_query_async(
            task_id=task.task_id,
            script_id=script_ids[0] if len(script_ids) == 1 else script_ids[0],
            script_ids=script_ids,
            db_connection_ids=all_db_ids,
            input_file=input_path,
            output_dir=output_dir,
            param_column=param_column,
            merge_strategy=merge_strategy,
            new_sheet=new_sheet_bool,
            column_mapping=column_mapping,
            primary_key=primary_key,
        )

        # 记录用户行为
        if current_user:
            track_behavior(current_user.id, 'query', 'task', task.id, {
                'script_ids': script_ids,
                'new_sheet': new_sheet_bool,
                'primary_key': primary_key,
                'column_mapping': column_mapping if not new_sheet_bool else {},
            })

        return jsonify({'success': True, 'task_id': task.task_id, 'message': '查询任务已提交'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@query_bp.route('/status/<task_id>', methods=['GET'])
@login_required
def get_query_status(task_id):
    status = QueryService.get_task_status(task_id)
    if not status:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    # 对普通用户脱敏错误信息
    current_user = get_current_user()
    is_admin = current_user.is_admin() if current_user else False
    sanitized = sanitize_error_for_user(status.get('error_message'), is_admin)
    status['error_message'] = sanitized['error_message']
    status['raw_error_message'] = sanitized['raw_error_message']
    status['ai_suggestion'] = sanitized['ai_suggestion']
    status['is_admin'] = is_admin

    return jsonify({'success': True, 'data': status})


@query_bp.route('/stream/<task_id>', methods=['GET'])
def stream_query_status(task_id):
    def generate():
        last_progress = -1
        last_log_count = 0
        idle_count = 0

        while True:
            status = QueryService.get_task_status(task_id)
            if not status:
                yield f"data: {json.dumps({'error': '任务不存在'})}\n\n"
                break

            current_progress = status.get('progress', 0)
            current_logs = status.get('logs', [])
            current_log_count = len(current_logs)

            if current_progress != last_progress or current_log_count != last_log_count:
                new_logs = current_logs[last_log_count:] if current_log_count > last_log_count else []
                event_data = {
                    'progress': current_progress,
                    'status': status.get('status'),
                    'success_count': status.get('success_count', 0),
                    'failure_count': status.get('failure_count', 0),
                    'total_rows': status.get('total_rows', 0),
                    'error_message': status.get('error_message'),
                    'new_logs': new_logs,
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                last_progress = current_progress
                last_log_count = current_log_count
                idle_count = 0
            else:
                idle_count += 1

            if status.get('status') in ('completed', 'failed', 'cancelled'):
                final_data = {
                    'progress': 100,
                    'status': status.get('status'),
                    'success_count': status.get('success_count', 0),
                    'failure_count': status.get('failure_count', 0),
                    'output_file': status.get('output_file'),
                    'error_message': status.get('error_message'),
                    'done': True
                }
                yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                break

            if idle_count > 300:
                yield f"data: {json.dumps({'status': 'timeout', 'done': True})}\n\n"
                break

            time.sleep(1)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@query_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_query(task_id):
    result = QueryService.cancel_task(task_id)
    if result:
        return jsonify({'success': True, 'message': '任务已取消'})
    return jsonify({'success': False, 'message': '无法取消任务'}), 400


@query_bp.route('/tasks', methods=['GET'])
@login_required
def get_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status')

    task_type = request.args.get('type')
    query = QueryTask.query
    if task_type:
        query = query.filter_by(type=task_type)
    if status_filter:
        query = query.filter_by(status=status_filter)

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        query = query.filter_by(created_by=current_user.id)

    pagination = query.order_by(QueryTask.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    tasks = []
    for task in pagination.items:
        task_dict = task.to_dict()
        script = Script.query.get(task.script_id) if task.script_id else None
        task_dict['script_name'] = script.name if script else '未知'
        task_dict['script_tag'] = script.tag if script else ''
        if task.type == 'export' and task.get_script_ids_json():
            s_names = []
            s_tags = []
            for sid in task.get_script_ids_json():
                s = Script.query.get(sid)
                if s:
                    s_names.append(s.name)
                    if s.tag:
                        s_tags.append(s.tag)
            task_dict['script_names'] = s_names
            task_dict['script_tags'] = s_tags
        db_names = []
        for db_id in task.get_database_ids():
            conn = DatabaseConnection.query.get(db_id)
            if conn:
                db_names.append(conn.name)
        task_dict['database_names'] = db_names
        tasks.append(task_dict)

    return jsonify({
        'success': True,
        'data': tasks,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@query_bp.route('/tasks/<task_identifier>', methods=['DELETE'])
def delete_task(task_identifier):
    task = QueryTask.query.filter(
        (QueryTask.id == task_identifier) | (QueryTask.task_id == task_identifier)
    ).first()
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True, 'message': '任务已删除'})


@query_bp.route('/tasks/batch-delete', methods=['POST'])
@login_required
def batch_delete_tasks():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    current_user = get_current_user()
    deleted_count = 0
    for task_id in ids:
        task = QueryTask.query.get(task_id)
        if not task:
            continue
        if current_user and not current_user.is_admin():
            if task.created_by != current_user.id:
                continue
        db.session.delete(task)
        deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个任务', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@query_bp.route('/tasks/all', methods=['DELETE'])
@login_required
def delete_all_tasks():
    current_user = get_current_user()
    try:
        if current_user and current_user.is_admin():
            deleted_count = QueryTask.query.delete()
        else:
            deleted_count = QueryTask.query.filter_by(created_by=current_user.id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个任务', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@query_bp.route('/retry/<task_id>', methods=['POST'])
def retry_task(task_id):
    task = QueryTask.query.filter_by(task_id=task_id).first()
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    if task.status not in ('failed', 'cancelled'):
        return jsonify({'success': False, 'message': '只能重试失败或已取消的任务'}), 400

    if task.type == 'export':
        return jsonify({'success': False, 'message': '请使用导出任务的重试接口'}), 400

    input_file = task.input_file
    if not input_file or not os.path.exists(input_file):
        return jsonify({'success': False, 'message': '输入文件不存在，文件可能已被定时清理，请重新上传文件执行'}), 400

    script_id = task.script_id
    script = Script.query.get(script_id) if script_id else None
    if not script:
        return jsonify({'success': False, 'message': '关联的查询选项不存在'}), 400

    try:
        task.status = 'pending'
        task.progress = 0
        task.success_count = 0
        task.failure_count = 0
        task.total_rows = 0
        task.error_message = None
        task.logs = None
        task.started_at = None
        task.completed_at = None
        db.session.commit()

        output_dir = current_app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        db_ids = task.get_database_ids()

        QueryService.execute_query_async(
            task_id=task.task_id,
            script_id=script_id,
            script_ids=[script_id],
            db_connection_ids=db_ids,
            input_file=input_file,
            output_dir=output_dir,
            param_column=None,
            merge_strategy=task.merge_strategy,
        )

        # 记录用户行为
        current_user = get_current_user()
        if current_user:
            track_behavior(current_user.id, 'retry', 'task', task.id, {'type': 'query'})

        return jsonify({'success': True, 'task_id': task.task_id, 'message': '任务已重新执行'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@query_bp.route('/upload-info', methods=['POST'])
def get_upload_info():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    file = request.files['file']
    try:
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"preview_{uuid.uuid4().hex[:8]}_{file.filename}"
        input_path = os.path.join(upload_dir, filename)
        file.save(input_path)

        info = ExcelService.get_file_info(input_path)
        columns = info.get('column_names', [])

        return jsonify({
            'success': True,
            'data': info,
            'file_path': input_path,
            'columns': columns
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@query_bp.route('/validate-sql', methods=['POST'])
def validate_sql():
    data = request.get_json()
    if not data or 'sql' not in data:
        return jsonify({'success': False, 'message': '缺少SQL语句'}), 400

    validator = SQLValidator()
    result = validator.validate(data['sql'])
    suggestions = validator.suggest_improvements(data['sql'])
    return jsonify({
        'success': True,
        'is_valid': result.is_valid,
        'message': result.message,
        'warnings': result.warnings,
        'suggestions': suggestions,
    })


@query_bp.route('/format-sql', methods=['POST'])
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


@query_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    current_user = get_current_user()
    user_id = current_user.id if current_user else None
    is_admin = current_user.is_admin() if current_user else False
    stats = QueryService.get_dashboard_stats(user_id=user_id, is_admin=is_admin)
    return jsonify({'success': True, 'data': stats})


@query_bp.route('/config', methods=['GET'])
def get_client_config():
    from flask import current_app
    return jsonify({
        'success': True,
        'data': {
            'file_retention_hours': current_app.config.get('FILE_RETENTION_HOURS', 24)
        }
    })


@query_bp.route('/fuzzy-match-columns', methods=['POST'])
@login_required
def fuzzy_match_columns():
    """模糊匹配SQL字段与Excel列名，返回映射关系"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    sql_fields = data.get('sql_fields', [])
    excel_columns = data.get('excel_columns', [])

    if not sql_fields or not excel_columns:
        return jsonify({'success': True, 'mapping': {}})

    mapping = QueryService._fuzzy_match_columns(sql_fields, excel_columns)
    return jsonify({'success': True, 'mapping': mapping})

@query_bp.route('/smart-match', methods=['POST'])
@login_required
def smart_match():
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({'success': False, 'message': '缺少文件名'}), 400

    filename = data['filename']
    from app.config import _yaml_config
    match_config = _yaml_config.get('smart_match', {})
    if not match_config.get('enabled', False):
        return jsonify({'success': True, 'matched_script_ids': [], 'matched_scripts': []})

    rules = match_config.get('rules', [])
    filename_lower = filename.lower()

    matched_tags = set()
    default_param_column = []
    for rule in rules:
        fk_list = rule.get('filename_keywords', [])
        st_list = rule.get('script_tags', [])
        for kw in fk_list:
            if kw.lower() in filename_lower:
                for tag in st_list:
                    matched_tags.add(tag)
                dpc = rule.get('default_param_column', [])
                if isinstance(dpc, str):
                    dpc = [dpc]
                if dpc:
                    default_param_column.extend(dpc)
                break

    if not matched_tags:
        return jsonify({'success': True, 'matched_script_ids': [], 'matched_scripts': []})

    all_scripts = Script.query.filter_by(is_active=True, type='query').all()

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_script_ids()
        all_scripts = [s for s in all_scripts if s.id in allowed_ids]

    matched_scripts = []
    for s in all_scripts:
        if not s.tag:
            continue
        for tag_kw in matched_tags:
            if tag_kw in s.tag:
                matched_scripts.append(s)
                break

    result_scripts = []
    matched_ids = []
    for s in matched_scripts:
        matched_ids.append(s.id)
        result_scripts.append({
            'id': s.id,
            'name': s.name,
            'tag': s.tag,
            'description': s.description,
            'new_sheet': s.new_sheet,
            'primary_key': s.primary_key or '',
        })

    return jsonify({
        'success': True,
        'matched_script_ids': matched_ids,
        'matched_scripts': result_scripts,
        'default_param_column': default_param_column,
        'direct': match_config.get('direct', False),
    })
