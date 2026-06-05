import os
from flask import Blueprint, send_file, current_app, jsonify
from app.models.query_task import QueryTask

download_bp = Blueprint('download', __name__, url_prefix='/api/download')


@download_bp.route('/<file_id>', methods=['GET'])
def download_file(file_id):
    task = QueryTask.query.filter_by(task_id=file_id).first()
    if not task or not task.output_file:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

    if not os.path.exists(task.output_file):
        return jsonify({'success': False, 'message': '文件已被删除'}), 404

    filename = os.path.basename(task.output_file)
    return send_file(
        task.output_file,
        as_attachment=True,
        download_name=filename,
    )
