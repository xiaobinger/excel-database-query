import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.auto_export_task import AutoExportTask
from app.models.script import Script
from app.models.query_task import QueryTask
from app.utils.auth import login_required, get_current_user

auto_export_bp = Blueprint('auto_export', __name__, url_prefix='/api/auto-export')


@auto_export_bp.route('', methods=['GET'])
@login_required
def get_auto_tasks():
    current_user = get_current_user()
    tasks = AutoExportTask.query.order_by(AutoExportTask.created_at.desc()).all()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_auto_task_ids()
        if allowed_ids:
            tasks = [t for t in tasks if t.id in allowed_ids]
        else:
            tasks = []
    result = []
    for task in tasks:
        d = task.to_dict()
        script_names = []
        for sid in task.get_script_ids():
            s = Script.query.get(sid)
            if s:
                script_names.append(s.name)
        d['script_names'] = script_names
        result.append(d)
    return jsonify({'success': True, 'data': result})


@auto_export_bp.route('/<int:task_id>', methods=['GET'])
@login_required
def get_auto_task(task_id):
    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_auto_task_ids()
        if task_id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权访问此任务'}), 403
    task = AutoExportTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    d = task.to_dict()
    script_names = []
    for sid in task.get_script_ids():
        s = Script.query.get(sid)
        if s:
            script_names.append(s.name)
    d['script_names'] = script_names

    recent_runs = QueryTask.query.filter_by(auto_task_id=task_id).order_by(
        QueryTask.created_at.desc()).limit(5).all()
    d['recent_runs'] = [r.to_dict() for r in recent_runs]
    return jsonify({'success': True, 'data': d})


@auto_export_bp.route('', methods=['POST'])
@login_required
def create_auto_task():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    name = data.get('name')
    if not name:
        return jsonify({'success': False, 'message': '请输入任务名称'}), 400

    cron_expr = data.get('cron_expression')
    if not cron_expr:
        return jsonify({'success': False, 'message': '请输入Cron表达式'}), 400

    try:
        from croniter import croniter
        croniter(cron_expr)
    except Exception as e:
        return jsonify({'success': False, 'message': f'Cron表达式无效: {str(e)}'}), 400

    script_ids = data.get('script_ids', [])
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
        from croniter import croniter
        next_run = croniter(cron_expr).get_next(datetime)
    except Exception:
        next_run = None

    task = AutoExportTask(
        name=name,
        description=data.get('description', ''),
        output_format=data.get('output_format', 'sheets'),
        is_enabled=data.get('is_enabled', True),
        created_by=current_user.id if current_user else None,
        next_run_at=next_run,
        notify_enabled=data.get('notify_enabled', False),
        notify_attach_file=data.get('notify_attach_file', False),
    )
    task.set_script_ids(script_ids)
    task.set_auto_params(data.get('auto_params', {}))
    task.cron_expression = cron_expr
    if data.get('notify_emails'):
        task.set_notify_emails(data['notify_emails'])

    db.session.add(task)
    db.session.commit()

    return jsonify({'success': True, 'data': task.to_dict(), 'message': '自动导出任务已创建'})


@auto_export_bp.route('/<int:task_id>', methods=['PUT'])
@login_required
def update_auto_task(task_id):
    task = AutoExportTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    simple_fields = ['name', 'description', 'output_format', 'cron_expression', 'is_enabled', 'notify_enabled', 'notify_attach_file']
    for key in simple_fields:
        if key in data:
            setattr(task, key, data[key])

    if 'script_ids' in data:
        task.set_script_ids(data['script_ids'])

    if 'auto_params' in data:
        task.set_auto_params(data['auto_params'])

    if 'notify_emails' in data:
        task.set_notify_emails(data['notify_emails'])

    if 'cron_expression' in data:
        try:
            from croniter import croniter
            croniter(data['cron_expression'])
            task.next_run_at = croniter(data['cron_expression']).get_next(datetime)
        except Exception as e:
            return jsonify({'success': False, 'message': f'Cron表达式无效: {str(e)}'}), 400

    db.session.commit()
    return jsonify({'success': True, 'data': task.to_dict()})


@auto_export_bp.route('/<int:task_id>', methods=['DELETE'])
@login_required
def delete_auto_task(task_id):
    task = AutoExportTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True, 'message': '已删除'})


@auto_export_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete_auto_tasks():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    current_user = get_current_user()
    deleted_count = 0
    for task_id in ids:
        task = AutoExportTask.query.get(task_id)
        if not task:
            continue
        if current_user and not current_user.is_admin():
            allowed_ids = current_user.get_auto_task_ids()
            if task_id not in (allowed_ids or []):
                continue
        db.session.delete(task)
        deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个任务', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@auto_export_bp.route('/all', methods=['DELETE'])
@login_required
def delete_all_auto_tasks():
    current_user = get_current_user()
    try:
        if current_user and current_user.is_admin():
            deleted_count = AutoExportTask.query.delete()
        else:
            allowed_ids = current_user.get_auto_task_ids() if current_user else []
            if allowed_ids:
                deleted_count = AutoExportTask.query.filter(AutoExportTask.id.in_(allowed_ids)).delete(synchronize_session=False)
            else:
                deleted_count = 0
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个任务', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@auto_export_bp.route('/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_auto_task(task_id):
    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_auto_task_ids()
        if task_id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权操作此任务'}), 403
    task = AutoExportTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    task.is_enabled = not task.is_enabled
    db.session.commit()
    status = '启用' if task.is_enabled else '禁用'
    return jsonify({'success': True, 'message': f'已{status}', 'is_enabled': task.is_enabled})


@auto_export_bp.route('/<int:task_id>/run-now', methods=['POST'])
@login_required
def run_now(task_id):
    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_auto_task_ids()
        if task_id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权操作此任务'}), 403
    task = AutoExportTask.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    try:
        from app.services.auto_export_scheduler import _execute_auto_task
        _execute_auto_task(current_app._get_current_object(), task)
        return jsonify({'success': True, 'message': '手动触发成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'触发失败: {str(e)}'}), 500


@auto_export_bp.route('/param-options', methods=['GET'])
def get_param_options():
    time_options = [
        {'value': 'current_year', 'label': '当年', 'type': 'year'},
        {'value': 'last_year', 'label': '去年', 'type': 'year'},
        {'value': 'current_month', 'label': '当月', 'type': 'month'},
        {'value': 'last_month', 'label': '上月', 'type': 'month'},
        {'value': 'current_day', 'label': '当天', 'type': 'day'},
        {'value': 'last_day', 'label': '昨天', 'type': 'day'},
        {'value': 'current_datetime', 'label': '当前时刻', 'type': 'datetime'},
        {'value': 'current_month_start', 'label': '当月第一天', 'type': 'day'},
        {'value': 'last_month_start', 'label': '上月第一天', 'type': 'day'},
        {'value': 'last_month_end', 'label': '上月最后一天', 'type': 'day'},
    ]
    range_options = [
        {'value': 'range_current_month', 'label': '当月范围', 'type': 'range'},
        {'value': 'range_last_month', 'label': '上月范围', 'type': 'range'},
        {'value': 'range_current_year', 'label': '当年范围', 'type': 'range'},
        {'value': 'range_last_year', 'label': '去年范围', 'type': 'range'},
        {'value': 'range_current_quarter', 'label': '当季范围', 'type': 'range'},
        {'value': 'range_last_quarter', 'label': '上季范围', 'type': 'range'},
        {'value': 'range_last_7_days', 'label': '近7天范围', 'type': 'range'},
        {'value': 'range_last_30_days', 'label': '近30天范围', 'type': 'range'},
    ]
    fixed_options = [
        {'value': '__custom__', 'label': '自定义固定值', 'type': 'custom'},
    ]
    return jsonify({'success': True, 'data': {'time': time_options, 'range': range_options, 'fixed': fixed_options}})
