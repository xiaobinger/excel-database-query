"""运营数据看板路由

- 快捷查询 CRUD
- 查询执行（维度参数、自定义时间范围、钻取、多数据源合并、缓存）
- SQL 参数与列名解析
- 看板配置（存 SystemConfig，由系统配置页维护）

看板脚本的增删改统一在脚本管理页（/api/scripts）维护，本模块只提供
只读的脚本列表供看板页下拉选择，不再单独维护一套脚本 CRUD。
"""
import logging
import traceback

from flask import Blueprint, request, jsonify

from app import db
from app.models.dashboard import DashboardQuickQuery
from app.models.script import Script
from app.models.database import DatabaseConnection
from app.utils.auth import permission_required
from app.services import dashboard_service as svc

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('data_dashboard', __name__, url_prefix='/api/dashboard')


# ── 看板脚本（只读列表，CRUD 在脚本管理页）──────────────────

def _script_to_dashboard_dict(s):
    d = s.to_dict()
    # 保持前端期望的 sql 字段（兼容旧字段名）
    d['sql'] = d.pop('sql_text', '')
    return d


@dashboard_bp.route('/scripts', methods=['GET'])
@permission_required('data_dashboard')
def list_scripts():
    scripts = Script.query.filter_by(type='dashboard', is_active=True).order_by(Script.created_at).all()
    return jsonify({'success': True, 'data': [_script_to_dashboard_dict(s) for s in scripts]})


# ── 快捷查询 ──────────────────────────────────────────


@dashboard_bp.route('/quick-queries', methods=['GET'])
@permission_required('data_dashboard')
def list_quick_queries():
    queries = DashboardQuickQuery.query.order_by(DashboardQuickQuery.id).all()
    return jsonify({'success': True, 'data': [q.to_dict() for q in queries]})


def _fill_quick_query(q: DashboardQuickQuery, data: dict):
    q.name = (data.get('name') or '').strip()
    q.script_name = data.get('script_name', '')
    q.conn_name = data.get('conn_name', '')
    q.merge_mode = data.get('merge_mode', 'separate')
    q.merge_key = data.get('merge_key', '')
    q.dimension = data.get('dimension', 'day')
    q.dp_year = data.get('dp_year')
    q.dp_month = data.get('dp_month')
    q.dp_year_start = data.get('dp_year_start')
    q.dp_year_end = data.get('dp_year_end')
    q.dp_start_date = data.get('dp_start_date') or None
    q.dp_end_date = data.get('dp_end_date') or None
    q.layout_count = int(data.get('layout_count') or 1)
    import json as _json
    q.merge_names = _json.dumps(data.get('merge_names') or [], ensure_ascii=False)
    q.hide_fields = _json.dumps(data.get('hide_fields') or [], ensure_ascii=False)
    q.custom_params = _json.dumps(data.get('custom_params') or {}, ensure_ascii=False)
    q.chart_configs = _json.dumps(data.get('chart_configs') or [], ensure_ascii=False)


@dashboard_bp.route('/quick-queries', methods=['POST'])
@permission_required('data_dashboard')
def add_quick_query():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '请输入名称'}), 400
    if DashboardQuickQuery.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': f"名称 '{name}' 已存在"}), 400
    q = DashboardQuickQuery(name=name)
    _fill_quick_query(q, data)
    db.session.add(q)
    db.session.commit()
    return jsonify({'success': True, 'data': q.to_dict()})


@dashboard_bp.route('/quick-queries/<int:query_id>', methods=['PUT'])
@permission_required('data_dashboard')
def update_quick_query(query_id):
    q = DashboardQuickQuery.query.get(query_id)
    if not q:
        return jsonify({'success': False, 'message': '不存在'}), 404
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '请输入名称'}), 400
    dup = DashboardQuickQuery.query.filter(DashboardQuickQuery.name == name, DashboardQuickQuery.id != query_id).first()
    if dup:
        return jsonify({'success': False, 'message': f"名称 '{name}' 已存在"}), 400
    _fill_quick_query(q, data)
    db.session.commit()
    return jsonify({'success': True, 'data': q.to_dict()})


@dashboard_bp.route('/quick-queries/<int:query_id>', methods=['DELETE'])
@permission_required('data_dashboard')
def delete_quick_query(query_id):
    q = DashboardQuickQuery.query.get(query_id)
    if not q:
        return jsonify({'success': False, 'message': '不存在'}), 404
    db.session.delete(q)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


# ── 数据源（复用本系统数据库连接） ────────────────────


@dashboard_bp.route('/connections', methods=['GET'])
@permission_required('data_dashboard')
def list_connections():
    conns = DatabaseConnection.query.filter_by(is_active=True).order_by(DatabaseConnection.name).all()
    return jsonify({'success': True, 'data': [{
        'name': c.name,
        'db_type': c.db_type,
        'host': c.host,
        'database': c.database_name,
        'ssh_enabled': bool(c.ssh_enabled),
    } for c in conns]})


# ── 查询执行 ──────────────────────────────────────────


@dashboard_bp.route('/execute', methods=['POST'])
@permission_required('data_dashboard')
def execute_query():
    data = request.json or {}
    try:
        result = svc.execute_dashboard_query(data)
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        logger.error(f'看板查询失败:\n{traceback.format_exc()}')
        return jsonify({'success': False, 'message': str(e)}), 500


@dashboard_bp.route('/parse-params', methods=['POST'])
@permission_required('data_dashboard')
def parse_params():
    sql = (request.json or {}).get('sql', '')
    return jsonify({'success': True, 'data': svc.parse_params(sql)})


@dashboard_bp.route('/parse-columns', methods=['POST'])
@permission_required('data_dashboard')
def parse_columns():
    sql = (request.json or {}).get('sql', '')
    return jsonify({'success': True, 'data': {'columns': svc.parse_columns(sql)}})


@dashboard_bp.route('/config', methods=['GET'])
@permission_required('data_dashboard')
def get_meta_config():
    return jsonify({'success': True, 'data': {
        'chart_types': svc.CHART_TYPES,
        'dimensions': svc.DIMENSIONS,
        'builtin_params': sorted(svc.BUILTIN_PARAMS),
        'settings': svc.get_dashboard_config(),
    }})


# ── 看板配置（系统配置页调用） ────────────────────────


@dashboard_bp.route('/settings', methods=['GET'])
@permission_required('system')
def get_settings():
    return jsonify({'success': True, 'data': svc.get_dashboard_config()})


@dashboard_bp.route('/settings', methods=['POST'])
@permission_required('system')
def save_settings():
    data = request.json or {}
    cfg = svc.save_dashboard_config(data)
    return jsonify({'success': True, 'data': cfg, 'message': '配置已保存'})


@dashboard_bp.route('/cache/clear', methods=['POST'])
@permission_required('system')
def clear_cache():
    count = svc.clear_dashboard_cache()
    return jsonify({'success': True, 'message': f'已清空 {count} 条查询缓存'})
