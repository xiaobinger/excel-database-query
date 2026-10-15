import os
from flask import Blueprint, send_file, current_app, jsonify
from app.models.query_task import QueryTask

download_bp = Blueprint('download', __name__, url_prefix='/api/download')

# 未匹配到任何数据时，任务虽然完成但不会生成结果文件，统一提示文案
NO_DATA_MESSAGE = '该任务未查询到匹配的数据，未生成结果文件'


@download_bp.route('/<file_id>', methods=['GET'])
def download_file(file_id):
    task = QueryTask.query.filter_by(task_id=file_id).first()
    if not task:
        return jsonify({'success': False, 'message': '任务不存在或已被删除，无法下载'}), 404

    # 未生成结果文件：区分「未查询到数据」与其他失败原因，避免统一笼统提示
    if not task.output_file:
        if task.status == 'completed' and not (task.total_rows or 0):
            return jsonify({'success': False, 'message': NO_DATA_MESSAGE}), 404
        if task.status == 'completed':
            return jsonify({'success': False, 'message': '该任务未生成结果文件'}), 404
        if task.status in ('failed', 'cancelled', 'manual_cancelled'):
            if task.status == 'failed':
                reason = task.error_message or '任务执行失败'
            else:
                reason = task.error_message or '任务已取消'
            return jsonify({'success': False, 'message': f'任务未成功完成，无法下载：{reason}'}), 404
        # pending / running 等未结束状态
        return jsonify({'success': False, 'message': '任务尚未完成，暂无结果文件可下载'}), 404

    if not os.path.exists(task.output_file):
        return jsonify({'success': False, 'message': '结果文件已被清理或不存在，请重新执行任务'}), 404

    filename = os.path.basename(task.output_file)
    return send_file(
        task.output_file,
        as_attachment=True,
        download_name=filename,
    )