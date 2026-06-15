from flask import Blueprint, request, jsonify
from app import db
from app.services.database_service import DatabaseService
from app.models.database import DatabaseConnection
from app.utils.db_connector import DatabaseConnector

database_bp = Blueprint('database', __name__, url_prefix='/api/databases')


@database_bp.route('', methods=['GET'])
def get_databases():
    connections = DatabaseService.get_all()
    return jsonify({
        'success': True,
        'data': [conn.to_dict() for conn in connections],
        'total': len(connections),
    })


@database_bp.route('/<int:conn_id>', methods=['GET'])
def get_database(conn_id):
    conn = DatabaseService.get_by_id(conn_id)
    if not conn:
        return jsonify({'success': False, 'message': '连接不存在'}), 404
    return jsonify({'success': True, 'data': conn.to_dict()})


@database_bp.route('', methods=['POST'])
def create_database():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    required = ['name', 'host', 'database_name', 'username']
    ssh_enabled = data.get('ssh_enabled', False)
    if not ssh_enabled:
        required.append('password')
    for field in required:
        if field not in data or not str(data[field]).strip():
            return jsonify({'success': False, 'message': f'缺少必填字段: {field}'}), 400

    try:
        conn = DatabaseService.create(data)
        # 通知连接池新建连接
        try:
            from app.utils.connection_pool import ConnectionPoolManager
            ConnectionPoolManager.get_instance().reload_connector(conn.id)
        except Exception:
            pass
        return jsonify({'success': True, 'data': conn.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@database_bp.route('/<int:conn_id>', methods=['PUT'])
def update_database(conn_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    conn = DatabaseService.update(conn_id, data)
    if not conn:
        return jsonify({'success': False, 'message': '连接不存在'}), 404
    # 通知连接池重新加载连接
    try:
        from app.utils.connection_pool import ConnectionPoolManager
        ConnectionPoolManager.get_instance().reload_connector(conn_id)
    except Exception:
        pass
    return jsonify({'success': True, 'data': conn.to_dict()})


@database_bp.route('/<int:conn_id>', methods=['DELETE'])
def delete_database(conn_id):
    if DatabaseService.delete(conn_id):
        # 通知连接池移除连接
        try:
            from app.utils.connection_pool import ConnectionPoolManager
            ConnectionPoolManager.get_instance().remove_connector(conn_id)
        except Exception:
            pass
        return jsonify({'success': True, 'message': '删除成功'})
    return jsonify({'success': False, 'message': '连接不存在'}), 404


@database_bp.route('/<int:conn_id>/test', methods=['POST'])
def test_database_connection(conn_id):
    result = DatabaseService.test_connection(conn_id)
    return jsonify(result)


@database_bp.route('/<int:conn_id>/tables', methods=['GET'])
def get_database_tables(conn_id):
    conn = DatabaseConnection.query.get(conn_id)
    if not conn:
        return jsonify({'success': False, 'message': '连接不存在'}), 404

    try:
        from app.utils.connection_pool import ConnectionPoolManager
        connector = ConnectionPoolManager.get_instance().get_connector(conn_id)
        if not connector:
            connector = DatabaseConnector(conn.to_config_dict())
        db_type = conn.db_type.lower()

        with connector.get_connection() as conn_obj:
            from sqlalchemy import text
            if db_type == 'mysql':
                result = conn_obj.execute(text(
                    "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME"
                ), {'schema': conn.database_name})
                tables = [{'name': row[0], 'comment': row[1] or ''} for row in result.fetchall()]
            elif db_type == 'postgresql':
                result = conn_obj.execute(text(
                    "SELECT tablename, '' FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
                ))
                tables = [{'name': row[0], 'comment': ''} for row in result.fetchall()]
            else:
                result = conn_obj.execute(text(
                    "SELECT TABLE_NAME, '' FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME"
                ), {'schema': conn.database_name})
                tables = [{'name': row[0], 'comment': ''} for row in result.fetchall()]

        return jsonify({'success': True, 'data': tables})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@database_bp.route('/<int:conn_id>/tables/<table_name>/columns', methods=['GET'])
def get_table_columns(conn_id, table_name):
    conn = DatabaseConnection.query.get(conn_id)
    if not conn:
        return jsonify({'success': False, 'message': '连接不存在'}), 404

    try:
        connector = DatabaseService.get_connector(conn_id)
        if not connector:
            return jsonify({'success': False, 'message': '无法创建连接'}), 500

        result = connector.get_table_info(table_name)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@database_bp.route('/types', methods=['GET'])
def get_database_types():
    types = [
        {'value': 'mysql', 'label': 'MySQL', 'default_port': 3306},
        {'value': 'postgresql', 'label': 'PostgreSQL', 'default_port': 5432},
        {'value': 'sqlite', 'label': 'SQLite', 'default_port': 0},
        {'value': 'sqlserver', 'label': 'SQL Server', 'default_port': 1433},
        {'value': 'oracle', 'label': 'Oracle', 'default_port': 1521},
    ]
    return jsonify({'success': True, 'data': types})
