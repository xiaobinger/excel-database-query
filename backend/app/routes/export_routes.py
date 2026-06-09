import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from app import db
from app.services.export_service import ExportService
from app.models.query_task import QueryTask
from app.models.script import Script
from app.models.database import DatabaseConnection
from app.utils.auth import login_required, get_current_user
from app.utils.behavior_tracker import track_behavior
import time

export_bp = Blueprint('export', __name__, url_prefix='/api/export')


@export_bp.route('/execute', methods=['POST'])
@login_required
def execute_export():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    script_ids = data.get('script_ids', [])
    params_values = data.get('params_values', {})
    all_checked = data.get('all_checked', {})
    output_format = data.get('output_format', 'sheets')

    if not script_ids:
        return jsonify({'success': False, 'message': '请选择至少一个导出选项'}), 400

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_script_ids()
        script_ids = [sid for sid in script_ids if sid in allowed_ids]
        if not script_ids:
            return jsonify({'success': False, 'message': '没有权限使用所选导出选项'}), 403

    for sid in script_ids:
        script = Script.query.get(sid)
        if not script or script.type != 'export':
            return jsonify({'success': False, 'message': f'导出选项不存在或类型不正确: {sid}'}), 400

    try:
        output_dir = current_app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        task = ExportService.create_export_task(
            script_ids=script_ids,
            params_values=params_values,
            output_format=output_format,
            created_by=current_user.id if current_user else None,
        )

        ExportService.execute_export_async(
            task_id=task.task_id,
            script_ids=script_ids,
            params_values=params_values,
            output_dir=output_dir,
            output_format=output_format,
            all_checked=all_checked,
        )

        # 记录用户行为
        current_user = get_current_user()
        if current_user:
            track_behavior(current_user.id, 'export', 'export_task', task.id, {
                'script_ids': script_ids,
                'output_format': output_format,
            })

        return jsonify({'success': True, 'task_id': task.task_id, 'message': '导出任务已提交'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@export_bp.route('/status/<task_id>', methods=['GET'])
def get_export_status(task_id):
    status = ExportService.get_task_status(task_id)
    if not status:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    return jsonify({'success': True, 'data': status})


@export_bp.route('/stream/<task_id>', methods=['GET'])
def stream_export_status(task_id):
    def generate():
        last_progress = -1
        last_log_count = 0
        idle_count = 0

        while True:
            status = ExportService.get_task_status(task_id)
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


@export_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_export(task_id):
    task = QueryTask.query.filter_by(task_id=task_id, type='export').first()
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    if task.status in ('pending', 'running'):
        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        task.add_log('任务已取消', 'warning')
        db.session.commit()
        return jsonify({'success': True, 'message': '任务已取消'})
    return jsonify({'success': False, 'message': '无法取消任务'}), 400


@export_bp.route('/tasks', methods=['GET'])
@login_required
def get_export_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status')

    query = QueryTask.query.filter_by(type='export')
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
        script_ids = task.get_script_ids_json()
        script_names = []
        script_tags = []
        for sid in script_ids:
            script = Script.query.get(sid)
            if script:
                script_names.append(script.name)
                if script.tag:
                    script_tags.append(script.tag)
        task_dict['script_names'] = script_names
        task_dict['script_tags'] = script_tags
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


@export_bp.route('/tasks/<task_identifier>', methods=['DELETE'])
def delete_export_task(task_identifier):
    task = QueryTask.query.filter(
        (QueryTask.id == task_identifier) | (QueryTask.task_id == task_identifier),
        QueryTask.type == 'export'
    ).first()
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True, 'message': '任务已删除'})


@export_bp.route('/retry/<task_id>', methods=['POST'])
def retry_export(task_id):
    task = QueryTask.query.filter_by(task_id=task_id, type='export').first()
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    if task.status not in ('failed', 'cancelled'):
        return jsonify({'success': False, 'message': '只能重试失败或已取消的任务'}), 400

    script_ids = task.get_script_ids_json()
    params_values = task.get_params_values()

    try:
        if task.output_file and os.path.exists(task.output_file):
            try:
                os.remove(task.output_file)
            except Exception:
                pass
        task.status = 'pending'
        task.progress = 0
        task.success_count = 0
        task.failure_count = 0
        task.total_rows = 0
        task.error_message = None
        task.output_file = None
        task.logs = None
        task.started_at = None
        task.completed_at = None
        db.session.commit()

        output_dir = current_app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        ExportService.execute_export_async(
            task_id=task.task_id,
            script_ids=script_ids,
            params_values=params_values,
            output_dir=output_dir,
            output_format=task.output_format or 'sheets',
        )

        # 记录用户行为
        current_user = get_current_user()
        if current_user:
            track_behavior(current_user.id, 'retry', 'export_task', task.id, {'type': 'export'})

        return jsonify({'success': True, 'task_id': task.task_id, 'message': '任务已重新执行'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
