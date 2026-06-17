import json
import time
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app import db
from app.models.system_task import SystemTask, SystemTaskExecution
from app.models.script import Script
from app.models.database import DatabaseConnection
from app.services.system_task_service import SystemTaskService
from app.utils.auth import login_required, get_current_user
from app.utils.behavior_tracker import track_behavior

system_task_bp = Blueprint('system_task', __name__, url_prefix='/api/system-tasks')


@system_task_bp.route('', methods=['GET'])
@login_required
def get_system_tasks():
    current_user = get_current_user()
    tasks = SystemTask.query.order_by(SystemTask.created_at.desc()).all()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_system_task_ids()
        tasks = [t for t in tasks if t.id in allowed_ids]
    result = []
    for task in tasks:
        d = task.to_dict()
        if task.script_id:
            script = Script.query.get(task.script_id)
            d['script_name'] = script.name if script else '未知'
            # Include script's params_config so frontend can read params without separate lookup
            if script and script.get_params_config():
                d['script_params_config'] = script.get_params_config()
            # Include script's database_ids as fallback for execution DB selection
            if script and not d.get('database_ids'):
                script_db_ids = script.get_database_ids()
                if script_db_ids:
                    d['database_ids'] = script_db_ids
        if task.database_connection_id:
            conn = DatabaseConnection.query.get(task.database_connection_id)
            d['database_name'] = conn.name if conn else '未知'
        result.append(d)
    return jsonify({'success': True, 'data': result})


@system_task_bp.route('/<int:task_id>', methods=['GET'])
@login_required
def get_system_task(task_id):
    current_user = get_current_user()
    task = SystemTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_system_task_ids()
        if task.id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权访问此任务'}), 403
    d = task.to_dict()
    if task.script_id:
        script = Script.query.get(task.script_id)
        d['script_name'] = script.name if script else '未知'
        if script and script.get_params_config():
            d['script_params_config'] = script.get_params_config()
    if task.database_connection_id:
        conn = DatabaseConnection.query.get(task.database_connection_id)
        d['database_name'] = conn.name if conn else '未知'
    return jsonify({'success': True, 'data': d})


@system_task_bp.route('', methods=['POST'])
@login_required
def create_system_task():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    name = data.get('name')
    if not name:
        return jsonify({'success': False, 'message': '请输入任务名称'}), 400

    task_type = data.get('task_type', 'sql')
    current_user = get_current_user()

    task = SystemTask(
        name=name,
        description=data.get('description', ''),
        task_type=task_type,
        script_id=data.get('script_id'),
        database_connection_id=data.get('database_connection_id'),
        api_method=data.get('api_method', 'POST'),
        api_url=data.get('api_url', ''),
        api_body=data.get('api_body', ''),
        api_timeout=data.get('api_timeout', 30),
        script_type=data.get('script_type', 'python'),
        script_path=data.get('script_path', ''),
        script_timeout=data.get('script_timeout', 60),
        sign_enabled=data.get('sign_enabled', False),
        sign_key=data.get('sign_key', ''),
        sign_method=data.get('sign_method', 'md5'),
        sign_param_name=data.get('sign_param_name', 'sign'),
        sign_append_type=data.get('sign_append_type', 'query'),
        is_enabled=data.get('is_enabled', True),
        created_by=current_user.id if current_user else None,
    )
    if data.get('database_ids'):
        task.set_database_ids(data['database_ids'])
    if data.get('api_headers'):
        task.set_api_headers(data['api_headers'])
    if data.get('params_config'):
        task.set_params_config(data['params_config'])
    if data.get('response_mapping'):
        task.set_response_mapping(data['response_mapping'])
    if data.get('script_env'):
        task.set_script_env(data['script_env'])

    db.session.add(task)
    db.session.commit()

    # 自动授权：非admin用户创建的系统任务自动加入其权限列表
    if current_user and not current_user.is_admin():
        existing_ids = current_user.get_system_task_ids() or []
        if task.id not in existing_ids:
            existing_ids.append(task.id)
            current_user.set_system_task_ids(existing_ids)
            db.session.commit()

    # 记录用户行为
    if current_user:
        track_behavior(current_user.id, 'create', 'system_task', task.id, {'type': task_type})

    return jsonify({'success': True, 'data': task.to_dict(), 'message': '系统任务已创建'})


@system_task_bp.route('/<int:task_id>', methods=['PUT'])
@login_required
def update_system_task(task_id):
    task = SystemTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_system_task_ids()
        if task.id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权修改此任务'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    simple_fields = [
        'name', 'description', 'task_type', 'script_id', 'database_connection_id',
        'api_method', 'api_url', 'api_body', 'api_timeout',
        'script_type', 'script_path', 'script_timeout',
        'sign_enabled', 'sign_key', 'sign_method', 'sign_param_name', 'sign_append_type',
        'is_enabled'
    ]
    for key in simple_fields:
        if key in data:
            setattr(task, key, data[key])

    if 'database_ids' in data:
        task.set_database_ids(data['database_ids'])
    if 'api_headers' in data:
        task.set_api_headers(data['api_headers'])
    if 'params_config' in data:
        task.set_params_config(data['params_config'])
    if 'response_mapping' in data:
        task.set_response_mapping(data['response_mapping'])

    db.session.commit()
    return jsonify({'success': True, 'data': task.to_dict(), 'message': '更新成功'})


@system_task_bp.route('/<int:task_id>', methods=['DELETE'])
@login_required
def delete_system_task(task_id):
    task = SystemTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_system_task_ids()
        if task.id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权删除此任务'}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True, 'message': '已删除'})


@system_task_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete_system_tasks():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    current_user = get_current_user()
    deleted_count = 0
    for task_id in ids:
        task = SystemTask.query.get(task_id)
        if not task:
            continue
        if current_user and not current_user.is_admin():
            allowed_ids = current_user.get_system_task_ids()
            if task.id not in allowed_ids:
                continue
        db.session.delete(task)
        deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个任务', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@system_task_bp.route('/all', methods=['DELETE'])
@login_required
def delete_all_system_tasks():
    current_user = get_current_user()
    try:
        if current_user and current_user.is_admin():
            deleted_count = SystemTask.query.delete()
        else:
            allowed_ids = current_user.get_system_task_ids() if current_user else []
            if allowed_ids:
                deleted_count = SystemTask.query.filter(SystemTask.id.in_(allowed_ids)).delete(synchronize_session=False)
            else:
                deleted_count = 0
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个任务', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@system_task_bp.route('/<int:task_id>/execute', methods=['POST'])
@login_required
def execute_system_task(task_id):
    task = SystemTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_system_task_ids()
        if task.id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权执行此任务'}), 403

    if not task.is_enabled:
        return jsonify({'success': False, 'message': '任务已禁用'}), 400

    data = request.get_json() or {}
    params_values = data.get('params_values', {})
    database_id = data.get('database_id')  # 指定数据库连接ID（可选）

    try:
        execution = SystemTaskService.create_execution(
            system_task_id=task.id,
            params_values=params_values,
            created_by=current_user.id if current_user else None,
        )

        SystemTaskService.execute_async(
            execution_id=execution.execution_id,
            system_task_id=task.id,
            params_values=params_values,
            database_id=database_id,
        )

        # 记录用户行为
        if current_user:
            track_behavior(current_user.id, 'execute', 'system_task', task.id, {
                'execution_id': execution.execution_id,
                'type': task.task_type
            })

        return jsonify({
            'success': True,
            'execution_id': execution.execution_id,
            'message': '系统任务已提交执行'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@system_task_bp.route('/executions', methods=['GET'])
@login_required
def get_executions():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    task_id = request.args.get('task_id', type=int)
    status_filter = request.args.get('status')

    query = SystemTaskExecution.query
    if task_id:
        query = query.filter_by(system_task_id=task_id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        query = query.filter_by(created_by=current_user.id)

    pagination = query.order_by(SystemTaskExecution.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = []
    for execution in pagination.items:
        d = execution.to_dict()
        system_task = SystemTask.query.get(execution.system_task_id) if execution.system_task_id else None
        d['system_task_name'] = system_task.name if system_task else '未知'
        d['system_task_type'] = system_task.task_type if system_task else ''
        items.append(d)

    return jsonify({
        'success': True,
        'data': items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@system_task_bp.route('/executions/<execution_id>', methods=['GET'])
@login_required
def get_execution(execution_id):
    status = SystemTaskService.get_execution_status(execution_id)
    if not status:
        return jsonify({'success': False, 'message': '执行记录不存在'}), 404
    return jsonify({'success': True, 'data': status})


@system_task_bp.route('/executions/<execution_id>/cancel', methods=['POST'])
@login_required
def cancel_execution(execution_id):
    result = SystemTaskService.cancel_execution(execution_id)
    if result:
        return jsonify({'success': True, 'message': '任务已取消'})
    return jsonify({'success': False, 'message': '无法取消任务'}), 400


@system_task_bp.route('/executions/<execution_id>/stream', methods=['GET'])
def stream_execution_status(execution_id):
    def generate():
        last_progress = -1
        last_log_count = 0
        idle_count = 0

        while True:
            status = SystemTaskService.get_execution_status(execution_id)
            if not status:
                yield f"data: {json.dumps({'error': '执行记录不存在'})}\n\n"
                break

            current_progress = status.get('progress', 0)
            current_logs = status.get('logs', [])
            current_log_count = len(current_logs)

            if current_progress != last_progress or current_log_count != last_log_count:
                new_logs = current_logs[last_log_count:] if current_log_count > last_log_count else []
                event_data = {
                    'progress': current_progress,
                    'status': status.get('status'),
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
                    'error_message': status.get('error_message'),
                    'result_data': status.get('result_data'),
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


@system_task_bp.route('/executions/<execution_id>', methods=['DELETE'])
@login_required
def delete_execution(execution_id):
    execution = SystemTaskExecution.query.filter_by(execution_id=execution_id).first()
    if not execution:
        return jsonify({'success': False, 'message': '执行记录不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin() and execution.created_by != current_user.id:
        return jsonify({'success': False, 'message': '无权删除此记录'}), 403

    db.session.delete(execution)
    db.session.commit()
    return jsonify({'success': True, 'message': '已删除'})
