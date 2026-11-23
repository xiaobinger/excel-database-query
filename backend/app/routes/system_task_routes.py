import json
import logging
import os
import time
import uuid
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app, send_file
from sqlalchemy import or_
from app import db
from app.models.system_task import SystemTask, SystemTaskExecution, SystemTaskBatch
from app.models.system_config import SystemConfig
from app.models.script import Script
from app.models.database import DatabaseConnection
from app.models.user import User
from app.services.system_task_service import SystemTaskService
from app.services.system_task_batch_service import SystemTaskBatchService
from app.utils.auth import login_required, get_current_user, admin_required
from app.utils.behavior_tracker import track_behavior

logger = logging.getLogger(__name__)

system_task_bp = Blueprint('system_task', __name__, url_prefix='/api/system-tasks')


def _normalize_ssh_config_id(value, require_jump_host=True):
    """校验并转换API任务使用的SSH配置ID（跳板机必须是跳板机，目标机必须不是跳板机）"""
    if value in (None, '', 0, '0'):
        return None
    try:
        ssh_id = int(value)
    except (TypeError, ValueError):
        return False
    from app.models.ssh_config import SshConfig
    ssh_config = SshConfig.query.get(ssh_id)
    if not ssh_config or not ssh_config.is_active:
        return False
    if bool(ssh_config.is_jump_host) != bool(require_jump_host):
        return False
    return ssh_id


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
        if task.param_source_script_id:
            ps_script = Script.query.get(task.param_source_script_id)
            d['param_source_script_name'] = ps_script.name if ps_script else '未知'
        if task.param_source_db_id:
            ps_conn = DatabaseConnection.query.get(task.param_source_db_id)
            d['param_source_db_name'] = ps_conn.name if ps_conn else '未知'
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
    if task.param_source_script_id:
        ps_script = Script.query.get(task.param_source_script_id)
        d['param_source_script_name'] = ps_script.name if ps_script else '未知'
    if task.param_source_db_id:
        ps_conn = DatabaseConnection.query.get(task.param_source_db_id)
        d['param_source_db_name'] = ps_conn.name if ps_conn else '未知'
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

    ssh_config_id = _normalize_ssh_config_id(data.get('ssh_config_id'), require_jump_host=True)
    target_ssh_config_id = _normalize_ssh_config_id(data.get('target_ssh_config_id'), require_jump_host=False)
    if ssh_config_id is False or target_ssh_config_id is False:
        return jsonify({'success': False, 'message': 'SSH配置不存在、已停用或类型不匹配（跳板机/目标机）'}), 400
    if ssh_config_id and not target_ssh_config_id:
        return jsonify({'success': False, 'message': '请选择目标机器SSH配置'}), 400
    if target_ssh_config_id and not ssh_config_id:
        return jsonify({'success': False, 'message': '请先选择SSH跳板机'}), 400

    task = SystemTask(
        name=name,
        description=data.get('description', ''),
        task_type=task_type,
        script_id=data.get('script_id'),
        database_connection_id=data.get('database_connection_id'),
        api_method=data.get('api_method', 'POST'),
        api_url=data.get('api_url', ''),
        api_body=data.get('api_body', ''),
        api_body_type=data.get('api_body_type', 'json'),
        api_timeout=data.get('api_timeout', 30),
        ssh_config_id=ssh_config_id,
        target_ssh_config_id=target_ssh_config_id,
        script_type=data.get('script_type', 'python'),
        script_path=data.get('script_path', ''),
        script_timeout=data.get('script_timeout', 60),
        param_source_enabled=data.get('param_source_enabled', False),
        param_source_script_id=data.get('param_source_script_id'),
        param_source_db_id=data.get('param_source_db_id'),
        ai_notes=data.get('ai_notes', ''),
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
    if 'api_body_params' in data:
        task.set_api_body_params(data['api_body_params'])
    if data.get('params_config'):
        task.set_params_config(data['params_config'])
    if data.get('response_mapping'):
        task.set_response_mapping(data['response_mapping'])
    if data.get('script_env'):
        task.set_script_env(data['script_env'])
    if 'param_source_param_mapping' in data:
        task.set_param_source_param_mapping(data['param_source_param_mapping'])

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

    if 'ssh_config_id' in data or 'target_ssh_config_id' in data:
        jump_value = data.get('ssh_config_id') if 'ssh_config_id' in data else task.ssh_config_id
        target_value = data.get('target_ssh_config_id') if 'target_ssh_config_id' in data else task.target_ssh_config_id
        ssh_config_id = _normalize_ssh_config_id(jump_value, require_jump_host=True)
        target_ssh_config_id = _normalize_ssh_config_id(target_value, require_jump_host=False)
        if ssh_config_id is False or target_ssh_config_id is False:
            return jsonify({'success': False, 'message': 'SSH配置不存在、已停用或类型不匹配（跳板机/目标机）'}), 400
        if ssh_config_id and not target_ssh_config_id:
            return jsonify({'success': False, 'message': '请选择目标机器SSH配置'}), 400
        if target_ssh_config_id and not ssh_config_id:
            return jsonify({'success': False, 'message': '请先选择SSH跳板机'}), 400
        data['ssh_config_id'] = ssh_config_id
        data['target_ssh_config_id'] = target_ssh_config_id

    simple_fields = [
        'name', 'description', 'task_type', 'script_id', 'database_connection_id',
        'api_method', 'api_url', 'api_body', 'api_body_type', 'api_timeout', 'ssh_config_id', 'target_ssh_config_id',
        'script_type', 'script_path', 'script_timeout',
        'param_source_enabled', 'param_source_script_id', 'param_source_db_id',
        'ai_notes',
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
    if 'api_body_params' in data:
        task.set_api_body_params(data['api_body_params'])
    if 'params_config' in data:
        task.set_params_config(data['params_config'])
    if 'response_mapping' in data:
        task.set_response_mapping(data['response_mapping'])
    if 'script_env' in data:
        task.set_script_env(data['script_env'])
    if 'param_source_param_mapping' in data:
        task.set_param_source_param_mapping(data['param_source_param_mapping'])

    db.session.commit()
    return jsonify({'success': True, 'data': task.to_dict(), 'message': '更新成功'})


@system_task_bp.route('/upload-script', methods=['POST'])
@login_required
def upload_script():
    """上传本地脚本文件到服务器指定路径（用于本地脚本类型的系统任务）

    参数:
        file: 脚本文件（multipart/form-data）
        script_path: 服务器上的存放路径（绝对路径，含文件名）
        create_dirs: 是否在目录不存在时自动创建（'true'/'1'，默认否）
    """
    current_user = get_current_user()
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '仅管理员可上传脚本'}), 403

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'message': '请选择要上传的脚本文件'}), 400

    script_path = (request.form.get('script_path') or '').strip()
    if not script_path:
        return jsonify({'success': False, 'message': '请填写脚本存放路径'}), 400

    # 规范化为绝对路径并校验
    script_path = os.path.abspath(script_path.replace('\\', '/'))
    create_dirs = (request.form.get('create_dirs') or '').lower() in ('true', '1', 'yes', 'on')

    # 脚本类型白名单校验（防止上传任意文件到服务器）
    allowed_exts = {'.py', '.sh', '.bat', '.ps1'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_exts:
        return jsonify({'success': False, 'message': f'不支持的脚本类型 {ext}，仅支持 {"、".join(sorted(allowed_exts))}'}), 400

    parent_dir = os.path.dirname(script_path)
    if not os.path.isdir(parent_dir):
        if not create_dirs:
            return jsonify({'success': False, 'message': f'目录不存在: {parent_dir}，可勾选「自动创建文件夹」后重试'}), 400
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError as e:
            return jsonify({'success': False, 'message': f'创建目录失败: {e}'}), 400

    # 路径已存在且是目录
    if os.path.isdir(script_path):
        return jsonify({'success': False, 'message': f'目标路径是一个已存在的目录: {script_path}'}), 400

    try:
        file.save(script_path)
        # Linux 下脚本加执行权限（.sh）
        if ext == '.sh':
            try:
                os.chmod(script_path, 0o755)
            except OSError:
                pass
    except OSError as e:
        return jsonify({'success': False, 'message': f'保存脚本失败: {e}'}), 500

    size = os.path.getsize(script_path)
    logger.info(f'用户 {current_user.username} 上传脚本到 {script_path} ({size} bytes)')
    return jsonify({
        'success': True,
        'data': {
            'script_path': script_path,
            'file_name': file.filename,
            'size': size,
            'dir_created': create_dirs and not os.path.exists(parent_dir),
        },
        'message': f'脚本已上传到 {script_path}',
    })


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


@system_task_bp.route('/batch/upload', methods=['POST'])
@login_required
def upload_batch_param_file():
    """上传批量执行参数文件，返回列名与行数用于字段映射"""
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': '请选择要上传的参数文件'}), 400

    allowed_ext = current_app.config.get('ALLOWED_UPLOAD_EXTENSIONS', {'xlsx', 'xls', 'csv'})
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_ext:
        return jsonify({'success': False, 'message': f'仅支持 {", ".join(sorted(allowed_ext))} 格式'}), 400

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"system_task_batch_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(upload_dir, stored_name)
    file.save(file_path)

    try:
        columns, rows = SystemTaskBatchService.read_table(file_path)
        return jsonify({
            'success': True,
            'data': {
                'file_path': file_path,
                'file_name': file.filename,
                'columns': columns,
                'row_count': len(rows),
            }
        })
    except Exception as e:
        logger.error(f'解析批量参数文件失败: {e}', exc_info=True)
        return jsonify({'success': False, 'message': f'文件解析失败: {str(e)}'}), 400


@system_task_bp.route('/<int:task_id>/batch-execute', methods=['POST'])
@login_required
def batch_execute_system_task(task_id):
    """按上传文件的字段映射批量执行系统任务，结果汇总输出到 Excel"""
    task = SystemTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        if task.id not in current_user.get_system_task_ids():
            return jsonify({'success': False, 'message': '无权执行此任务'}), 403

    if not task.is_enabled:
        return jsonify({'success': False, 'message': '任务已禁用'}), 400

    data = request.get_json() or {}
    file_path = data.get('file_path')
    param_mapping = data.get('param_mapping') or {}
    params_defaults = data.get('params_defaults') or {}
    database_id = data.get('database_id')
    sheet_name = data.get('sheet_name') or None

    if not file_path or not os.path.isfile(file_path):
        return jsonify({'success': False, 'message': '参数文件不存在，请重新上传'}), 400

    upload_root = os.path.realpath(current_app.config['UPLOAD_FOLDER'])
    if not os.path.realpath(file_path).startswith(upload_root):
        return jsonify({'success': False, 'message': '参数文件路径非法'}), 400

    if not isinstance(param_mapping, dict) or not isinstance(params_defaults, dict):
        return jsonify({'success': False, 'message': '字段映射参数格式不正确'}), 400

    if not param_mapping and not params_defaults:
        return jsonify({'success': False, 'message': '请至少配置一个字段映射或固定参数值'}), 400

    try:
        columns, _ = SystemTaskBatchService.read_table(file_path, sheet_name=sheet_name, limit=0)
        invalid_columns = [col for col in param_mapping.values() if col not in columns]
        if invalid_columns:
            return jsonify({
                'success': False,
                'message': f'字段映射的文件列不存在: {", ".join(invalid_columns)}'
            }), 400

        # 校验必填参数已配置映射或固定值
        missing_params = []
        if not task.param_source_enabled:
            for config in SystemTaskBatchService.get_param_configs(task):
                name = config.get('name')
                if not name:
                    continue
                if name in param_mapping or name in params_defaults:
                    continue
                if config.get('enum_ref') or config.get('enum_source_param'):
                    continue
                required = task.task_type in ('sql', 'script') or config.get('required')
                if required:
                    missing_params.append(config.get('label') or name)
        if missing_params:
            return jsonify({
                'success': False,
                'message': f'以下参数未映射文件列或设置固定值: {", ".join(missing_params)}'
            }), 400

        batch = SystemTaskBatchService.create_batch(
            system_task=task,
            file_path=file_path,
            file_name=data.get('file_name') or os.path.basename(file_path),
            param_mapping=param_mapping,
            params_defaults=params_defaults,
            database_id=database_id,
            sheet_name=sheet_name,
            created_by=current_user.id if current_user else None,
        )

        app = current_app._get_current_object()
        SystemTaskBatchService.execute_async(app, batch.batch_id)

        if current_user:
            track_behavior(current_user.id, 'execute', 'system_task', task.id, {
                'batch_id': batch.batch_id,
                'type': task.task_type,
                'mode': 'batch'
            })

        return jsonify({
            'success': True,
            'batch_id': batch.batch_id,
            'message': '批量执行已提交'
        })
    except Exception as e:
        logger.error(f'提交批量执行失败: {e}', exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@system_task_bp.route('/batches', methods=['GET'])
@login_required
def list_batches():
    """分页查询批量执行记录（非管理员仅能查看自己创建的批次）"""
    current_user = get_current_user()
    try:
        page = max(int(request.args.get('page', 1) or 1), 1)
        page_size = min(max(int(request.args.get('page_size', 20) or 20), 1), 100)
    except (TypeError, ValueError):
        page, page_size = 1, 20
    status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()
    system_task_id = request.args.get('system_task_id')

    query = SystemTaskBatch.query
    if current_user and not current_user.is_admin():
        query = query.filter(SystemTaskBatch.created_by == current_user.id)
    if status:
        query = query.filter(SystemTaskBatch.status == status)
    if system_task_id:
        try:
            query = query.filter(SystemTaskBatch.system_task_id == int(system_task_id))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'system_task_id 参数无效'}), 400
    if keyword:
        like = f'%{keyword}%'
        query = query.filter(or_(
            SystemTaskBatch.batch_id.ilike(like),
            SystemTaskBatch.input_file_name.ilike(like),
        ))

    total = query.count()
    batches = query.order_by(SystemTaskBatch.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    task_ids = {b.system_task_id for b in batches if b.system_task_id}
    user_ids = {b.created_by for b in batches if b.created_by}
    task_map = {}
    if task_ids:
        task_map = {t.id: t.name for t in SystemTask.query.filter(SystemTask.id.in_(task_ids)).all()}
    user_map = {}
    if user_ids:
        for user in User.query.filter(User.id.in_(user_ids)).all():
            user_map[user.id] = user.display_name or user.username

    items = []
    for batch in batches:
        data = batch.to_dict()
        data['system_task_name'] = task_map.get(batch.system_task_id) or '-'
        data['created_by_name'] = user_map.get(batch.created_by) or '-'
        data['output_file_name'] = os.path.basename(batch.output_file) if batch.output_file else None
        data['output_exists'] = bool(batch.output_file and os.path.exists(batch.output_file))
        data.pop('logs', None)  # 列表不返回完整日志，详情接口再取
        items.append(data)

    return jsonify({
        'success': True,
        'data': {'items': items, 'total': total, 'page': page, 'page_size': page_size}
    })


@system_task_bp.route('/batches/delete', methods=['POST'])
@login_required
def delete_batches():
    """删除批量执行记录（执行中的批次不可删除）"""
    payload = request.get_json(silent=True) or {}
    batch_ids = payload.get('batch_ids') or []
    if not isinstance(batch_ids, list) or not batch_ids:
        return jsonify({'success': False, 'message': '请选择要删除的批量记录'}), 400

    current_user = get_current_user()
    batches = SystemTaskBatch.query.filter(SystemTaskBatch.batch_id.in_(batch_ids)).all()
    deleted, skipped = 0, []
    for batch in batches:
        if current_user and not current_user.is_admin() and batch.created_by != current_user.id:
            skipped.append(f'{batch.batch_id}：无权删除')
            continue
        if batch.status in ('pending', 'running'):
            skipped.append(f'{batch.batch_id}：执行中不可删除')
            continue
        # 同步清理结果文件，避免留下孤儿文件
        if batch.output_file and os.path.exists(batch.output_file):
            try:
                os.remove(batch.output_file)
            except OSError as exc:
                logger.warning(f'删除批量结果文件失败: {batch.output_file} - {exc}')
        db.session.delete(batch)
        deleted += 1

    db.session.commit()
    return jsonify({'success': True, 'deleted': deleted, 'skipped': skipped})


@system_task_bp.route('/batch/<batch_id>', methods=['GET'])
@login_required
def get_batch_status(batch_id):
    batch = SystemTaskBatch.query.filter_by(batch_id=batch_id).first()
    if not batch:
        return jsonify({'success': False, 'message': '批量执行记录不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin() and batch.created_by != current_user.id:
        return jsonify({'success': False, 'message': '无权查看此批量执行记录'}), 403

    return jsonify({'success': True, 'data': batch.to_dict()})


@system_task_bp.route('/batch/<batch_id>/stream', methods=['GET'])
@login_required
def stream_batch_status(batch_id):
    def generate():
        last_progress = -1
        last_log_count = 0
        idle_seconds = 0

        while True:
            # MySQL 默认事务隔离级别为 REPEATABLE READ：若不在每次轮询前结束上一轮只读事务，
            # 整个流会一直读到开始时的快照，导致进度/状态永不更新（进度条卡住、完成后弹窗不结束）
            try:
                db.session.rollback()
            except Exception:
                pass

            batch = SystemTaskBatch.query.filter_by(batch_id=batch_id).first()
            if not batch:
                yield f"data: {json.dumps({'error': '批量执行记录不存在'})}\n\n"
                break

            current_progress = batch.progress or 0
            current_logs = batch.get_logs()
            current_log_count = len(current_logs)

            if current_progress != last_progress or current_log_count != last_log_count:
                new_logs = current_logs[last_log_count:] if current_log_count > last_log_count else []
                event_data = {
                    'type': 'update',
                    'progress': current_progress,
                    'status': batch.status,
                    'processed_rows': batch.processed_rows or 0,
                    'total_rows': batch.total_rows or 0,
                    'success_count': batch.success_count or 0,
                    'failure_count': batch.failure_count or 0,
                    'error_message': batch.error_message,
                    'new_logs': new_logs,
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                last_progress = current_progress
                last_log_count = current_log_count
                idle_seconds = 0
            else:
                idle_seconds += 1

            if batch.status in ('completed', 'failed', 'cancelled'):
                final_data = {
                    'type': 'done',
                    'progress': 100,
                    'status': batch.status,
                    'total_rows': batch.total_rows or 0,
                    'processed_rows': batch.processed_rows or 0,
                    'success_count': batch.success_count or 0,
                    'failure_count': batch.failure_count or 0,
                    'error_message': batch.error_message,
                    'output_file': batch.output_file,
                    'no_data': not bool(batch.output_file),
                    'done': True,
                }
                yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                break

            # 长任务心跳：不再因长时间无进度变化强制中断，仅每 10 秒发一次心跳，
            # 既避免代理/网关断开空闲连接，也让前端能识别连接是否存活
            if idle_seconds > 0 and idle_seconds % 10 == 0:
                heartbeat = {
                    'type': 'ping',
                    'status': batch.status,
                    'progress': current_progress,
                    'processed_rows': batch.processed_rows or 0,
                    'total_rows': batch.total_rows or 0,
                    'success_count': batch.success_count or 0,
                    'failure_count': batch.failure_count or 0,
                }
                yield f"data: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"

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


@system_task_bp.route('/batch/<batch_id>/download', methods=['GET'])
@login_required
def download_batch_result(batch_id):
    batch = SystemTaskBatch.query.filter_by(batch_id=batch_id).first()
    if not batch:
        return jsonify({'success': False, 'message': '批量执行记录不存在'}), 404

    current_user = get_current_user()
    if current_user and not current_user.is_admin() and batch.created_by != current_user.id:
        return jsonify({'success': False, 'message': '无权下载此批量执行结果'}), 403

    if not batch.output_file or not os.path.isfile(batch.output_file):
        return jsonify({'success': False, 'message': '结果文件不存在或尚未生成'}), 404

    return send_file(
        batch.output_file,
        as_attachment=True,
        download_name=os.path.basename(batch.output_file)
    )


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
    try:
        result = SystemTaskService.cancel_execution(execution_id)
        if result:
            return jsonify({'success': True, 'message': '任务已取消'})
        return jsonify({'success': False, 'message': '无法取消任务（任务可能已完成或不存在）'}), 400
    except Exception as e:
        logger.error(f'取消任务异常: {e}', exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'message': f'取消任务失败: {str(e)}'}), 500


@system_task_bp.route('/executions/<execution_id>/stream', methods=['GET'])
@login_required
def stream_execution_status(execution_id):
    def generate():
        last_progress = -1
        last_log_count = 0
        idle_seconds = 0

        while True:
            # 结束上一轮只读事务，避免 REPEATABLE READ 快照导致进度/状态不更新
            try:
                db.session.rollback()
            except Exception:
                pass

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
                    'type': 'update',
                    'progress': current_progress,
                    'status': status.get('status'),
                    'error_message': status.get('error_message'),
                    'new_logs': new_logs,
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                last_progress = current_progress
                last_log_count = current_log_count
                idle_seconds = 0
            else:
                idle_seconds += 1

            if status.get('status') in ('completed', 'failed', 'cancelled'):
                final_data = {
                    'type': 'done',
                    'progress': 100,
                    'status': status.get('status'),
                    'error_message': status.get('error_message'),
                    'result_data': status.get('result_data'),
                    'done': True
                }
                yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                break

            # 长任务心跳：不做强制超时，仅定期发送心跳保持连接
            if idle_seconds > 0 and idle_seconds % 10 == 0:
                heartbeat = {
                    'type': 'ping',
                    'status': status.get('status'),
                    'progress': current_progress,
                }
                yield f"data: {json.dumps(heartbeat, ensure_ascii=False)}\n\n"

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


@system_task_bp.route('/executions/batch-delete', methods=['POST'])
@login_required
def batch_delete_executions():
    """批量删除执行记录

    权限：管理员可删除所有；普通用户只能删除自己创建的记录。
    """
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的执行记录ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    current_user = get_current_user()
    deleted_count = 0
    for exec_id in ids:
        execution = SystemTaskExecution.query.filter_by(execution_id=exec_id).first()
        if not execution:
            continue
        if current_user and not current_user.is_admin() and execution.created_by != current_user.id:
            continue
        db.session.delete(execution)
        deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}条记录', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@system_task_bp.route('/executions/all', methods=['DELETE'])
@login_required
def delete_all_executions():
    """清空执行记录

    权限：管理员可清空所有；普通用户只能清空自己创建的记录。
    """
    current_user = get_current_user()
    try:
        if current_user and current_user.is_admin():
            deleted_count = SystemTaskExecution.query.delete()
        else:
            deleted_count = SystemTaskExecution.query.filter_by(created_by=current_user.id).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}条记录', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


# ── 全局枚举参数管理（可在任意API类型系统任务中复用） ──────────────

ENUMS_CONFIG_KEY = 'system_task_enums'


def _get_enums_config():
    """读取全局枚举参数列表"""
    config = SystemConfig.query.filter_by(config_key=ENUMS_CONFIG_KEY).first()
    if config and config.config_value:
        try:
            data = json.loads(config.config_value)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
    return []


@system_task_bp.route('/enums', methods=['GET'])
@login_required
def get_enums():
    """获取全局枚举参数列表（登录用户可读，供任务参数配置引用）"""
    return jsonify({'success': True, 'data': _get_enums_config()})


@system_task_bp.route('/enums', methods=['PUT'])
@admin_required
def update_enums():
    """保存全局枚举参数列表（仅管理员）"""
    data = request.get_json()
    if not data or 'enums' not in data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    enums = data.get('enums')
    if not isinstance(enums, list):
        return jsonify({'success': False, 'message': '枚举列表必须是数组'}), 400

    # 校验每项：name 唯一，label 必填，options 非空
    normalized = []
    seen_names = set()
    for item in enums:
        if not isinstance(item, dict):
            continue
        name = (item.get('name') or '').strip()
        label = (item.get('label') or '').strip()
        options = item.get('options') or []
        if not name or not label or not options:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        # 规整 options
        opts = []
        for o in options:
            if not isinstance(o, dict):
                continue
            o_label = (o.get('label') or '').strip()
            o_value = (o.get('value') or '').strip()
            if o_label and o_value:
                opts.append({'label': o_label, 'value': o_value})
        if not opts:
            continue
        normalized.append({'name': name, 'label': label, 'options': opts})

    config = SystemConfig.query.filter_by(config_key=ENUMS_CONFIG_KEY).first()
    if not config:
        config = SystemConfig(config_key=ENUMS_CONFIG_KEY, description='系统任务全局枚举参数')
        db.session.add(config)
    config.config_value = json.dumps(normalized, ensure_ascii=False)
    db.session.commit()

    return jsonify({'success': True, 'message': '枚举参数已保存', 'data': normalized})
