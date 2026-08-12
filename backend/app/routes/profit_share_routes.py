"""代理商分润导出路由"""

import os
import json
import time
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from app.services.profit_share_service import ProfitShareService
from app.models.database import DatabaseConnection
from app.utils.auth import login_required, get_current_user
from app.utils.behavior_tracker import track_behavior
from app.utils.error_sanitizer import sanitize_error_for_user

profit_share_bp = Blueprint('profit_share', __name__, url_prefix='/api/profit-share')


@profit_share_bp.route('/export', methods=['POST'])
@login_required
def execute_profit_share_export():
    """触发代理商分润导出任务

    请求参数:
        org_no: 一级代理商编号 (必填)
        start_time: 交易开始时间 (必填, 格式: YYYY-MM-DD HH:MM:SS)
        end_time: 交易结束时间 (必填, 格式: YYYY-MM-DD HH:MM:SS)
        database_connection_id: 数据库连接ID (可选, 不传则自动查找"融聚商户通(海科)")
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    org_no = data.get('org_no', '').strip()
    if not org_no:
        return jsonify({'success': False, 'message': '请提供代理商编号(org_no)'}), 400

    start_time = data.get('start_time', '').strip()
    end_time = data.get('end_time', '').strip()
    if not start_time or not end_time:
        return jsonify({'success': False, 'message': '请提供交易时间范围(start_time, end_time)'}), 400

    database_connection_id = data.get('database_connection_id')

    # 如果未指定数据库连接，尝试自动查找
    if not database_connection_id:
        conn = ProfitShareService.find_database_connection()
        if not conn:
            return jsonify({
                'success': False,
                'message': '未找到"融聚商户通(海科)"数据库连接，请先在系统中配置该数据库连接，或通过 database_connection_id 参数指定'
            }), 400
        database_connection_id = conn.id

    # 验证数据库连接存在
    conn = DatabaseConnection.query.get(database_connection_id)
    if not conn:
        return jsonify({'success': False, 'message': '数据库连接不存在'}), 400
    if not conn.is_active:
        return jsonify({'success': False, 'message': f'数据库连接 [{conn.name}] 已禁用'}), 400

    try:
        output_dir = current_app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        current_user = get_current_user()
        is_admin = current_user.is_admin() if current_user else False
        task = ProfitShareService.create_task(
            org_no=org_no,
            start_time=start_time,
            end_time=end_time,
            database_connection_id=database_connection_id,
            created_by=current_user.id if current_user else None,
        )

        ProfitShareService.execute_async(
            task_id=task.task_id,
            org_no=org_no,
            start_time=start_time,
            end_time=end_time,
            database_connection_id=database_connection_id,
            output_dir=output_dir,
            is_admin=is_admin,
        )

        # 记录用户行为
        if current_user:
            track_behavior(current_user.id, 'export', 'profit_share_task', task.id, {
                'org_no': org_no,
                'start_time': start_time,
                'end_time': end_time,
                'database_connection_id': database_connection_id,
            })

        return jsonify({
            'success': True,
            'task_id': task.task_id,
            'message': '代理分润导出任务已提交',
            'database_name': conn.name,
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@profit_share_bp.route('/status/<task_id>', methods=['GET'])
@login_required
def get_profit_share_status(task_id):
    """查询分润导出任务状态"""
    status = ProfitShareService.get_task_status(task_id)
    if not status:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    current_user = get_current_user()
    is_admin = current_user.is_admin() if current_user else False
    sanitized = sanitize_error_for_user(status.get('error_message'), is_admin)
    status['error_message'] = sanitized['error_message']
    status['raw_error_message'] = sanitized['raw_error_message']
    status['ai_suggestion'] = sanitized['ai_suggestion']
    status['is_admin'] = is_admin

    return jsonify({'success': True, 'data': status})


@profit_share_bp.route('/stream/<task_id>', methods=['GET'])
def stream_profit_share_status(task_id):
    """SSE 流式获取任务状态"""
    def generate():
        last_progress = -1
        last_log_count = 0
        idle_count = 0

        while True:
            status = ProfitShareService.get_task_status(task_id)
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

            if status.get('status') in ('completed', 'failed', 'cancelled', 'manual_cancelled'):
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


@profit_share_bp.route('/cancel/<task_id>', methods=['POST'])
@login_required
def cancel_profit_share(task_id):
    """取消分润导出任务"""
    if ProfitShareService.cancel_task(task_id):
        return jsonify({'success': True, 'message': '任务已终止'})
    return jsonify({'success': False, 'message': '无法终止任务'}), 400


@profit_share_bp.route('/databases', methods=['GET'])
@login_required
def list_available_databases():
    """列出可用的数据库连接（用于前端选择）"""
    connections = DatabaseConnection.query.filter_by(is_active=True).all()
    result = []
    for conn in connections:
        result.append({
            'id': conn.id,
            'name': conn.name,
            'description': conn.description,
            'db_type': conn.db_type,
        })
    return jsonify({'success': True, 'data': result})
