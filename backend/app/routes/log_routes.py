from flask import Blueprint, request, jsonify
from app import db
from app.models.login_log import LoginLog
from app.models.operation_log import OperationLog
from app.utils.auth import admin_required

log_bp = Blueprint('log', __name__, url_prefix='/api/logs')


@log_bp.route('/login', methods=['GET'])
@admin_required
def get_login_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = LoginLog.query
    if keyword:
        query = query.filter(
            db.or_(
                LoginLog.username.contains(keyword),
                LoginLog.ip_address.contains(keyword),
            )
        )
    if status:
        query = query.filter(LoginLog.status == status)
    if start_date:
        from datetime import datetime
        try:
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(LoginLog.created_at >= dt)
        except ValueError:
            pass
    if end_date:
        from datetime import datetime
        try:
            dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(LoginLog.created_at <= dt)
        except ValueError:
            pass

    pagination = query.order_by(LoginLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@log_bp.route('/operation', methods=['GET'])
@admin_required
def get_operation_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '')
    action = request.args.get('action', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = OperationLog.query
    if keyword:
        query = query.filter(
            db.or_(
                OperationLog.username.contains(keyword),
                OperationLog.ip_address.contains(keyword),
                OperationLog.detail.contains(keyword),
            )
        )
    if action:
        query = query.filter(OperationLog.action == action)
    if start_date:
        from datetime import datetime
        try:
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(OperationLog.created_at >= dt)
        except ValueError:
            pass
    if end_date:
        from datetime import datetime
        try:
            dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(OperationLog.created_at <= dt)
        except ValueError:
            pass

    pagination = query.order_by(OperationLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'success': True,
        'data': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@log_bp.route('/login', methods=['DELETE'])
@admin_required
def clear_login_logs():
    """清空登录日志"""
    try:
        count = LoginLog.query.delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'已清空{count}条登录日志', 'deleted_count': count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@log_bp.route('/operation', methods=['DELETE'])
@admin_required
def clear_operation_logs():
    """清空操作日志"""
    try:
        count = OperationLog.query.delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'已清空{count}条操作日志', 'deleted_count': count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
