from flask import Blueprint, request, jsonify
from app.models.script import Script
from app.services.lookup_service import LookupService
from app.utils.auth import login_required, get_current_user
from app.utils.error_sanitizer import sanitize_error_for_user
import logging

logger = logging.getLogger(__name__)

lookup_bp = Blueprint('lookup', __name__, url_prefix='/api/lookup')


@lookup_bp.route('/execute', methods=['POST'])
@login_required
def execute_lookup():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    script_id = data.get('script_id')
    params_values = data.get('params_values', {})

    if script_id is None:
        return jsonify({'success': False, 'message': '缺少 script_id'}), 400

    current_user = get_current_user()
    if current_user and not current_user.is_admin():
        allowed_ids = current_user.get_script_ids()
        if script_id not in allowed_ids:
            return jsonify({'success': False, 'message': '无权访问该查询选项'}), 403

    try:
        result = LookupService.execute_lookup(script_id, params_values, current_user.id if current_user else None)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f'Lookup执行异常: {str(e)}', exc_info=True)
        is_admin = current_user.is_admin() if current_user else False
        sanitized = sanitize_error_for_user(str(e), is_admin)
        return jsonify({'success': False, 'message': sanitized['error_message']}), 500
