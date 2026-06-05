import logging
from typing import List, Optional
from app import db
from app.models.database import DatabaseConnection
from app.models.ssh_config import SshConfig
from app.utils.db_connector import DatabaseConnector

logger = logging.getLogger(__name__)


class DatabaseService:

    @staticmethod
    def get_all() -> List[DatabaseConnection]:
        return DatabaseConnection.query.filter_by(is_active=True).order_by(DatabaseConnection.created_at.desc()).all()

    @staticmethod
    def get_by_id(conn_id: int) -> Optional[DatabaseConnection]:
        return DatabaseConnection.query.get(conn_id)

    @staticmethod
    def create(data: dict) -> DatabaseConnection:
        ssh_config_id = data.get('ssh_config_id')
        if ssh_config_id:
            ssh_config_id = int(ssh_config_id)
        conn = DatabaseConnection(
            name=data['name'],
            description=data.get('description', ''),
            db_type=data.get('db_type', 'mysql'),
            host=data['host'],
            port=int(data.get('port', 3306)),
            database_name=data['database_name'],
            username=data['username'],
            pool_size=int(data.get('pool_size', 5)),
            max_overflow=int(data.get('max_overflow', 10)),
            ssh_enabled=data.get('ssh_enabled', False),
            ssh_config_id=ssh_config_id,
        )
        conn.set_password(data['password'])
        db.session.add(conn)
        db.session.commit()
        logger.info(f"创建数据库连接: {conn.name}")
        return conn

    @staticmethod
    def update(conn_id: int, data: dict) -> Optional[DatabaseConnection]:
        conn = DatabaseConnection.query.get(conn_id)
        if not conn:
            return None
        int_fields = ['port', 'pool_size', 'max_overflow']
        for key in ['name', 'description', 'db_type', 'host', 'port', 'database_name',
                     'username', 'pool_size', 'max_overflow', 'ssh_enabled',
                     'ssh_config_id', 'is_active']:
            if key in data:
                val = data[key]
                if key in int_fields and val is not None:
                    val = int(val)
                if key == 'ssh_config_id' and val is not None:
                    val = int(val)
                setattr(conn, key, val)
        if 'password' in data and data['password']:
            conn.set_password(data['password'])
        db.session.commit()
        logger.info(f"更新数据库连接: {conn.name}")
        return conn

    @staticmethod
    def delete(conn_id: int) -> bool:
        conn = DatabaseConnection.query.get(conn_id)
        if not conn:
            return False
        conn.is_active = False
        db.session.commit()
        logger.info(f"删除数据库连接: {conn.name}")
        return True

    @staticmethod
    def test_connection(conn_id: int) -> dict:
        conn = DatabaseConnection.query.get(conn_id)
        if not conn:
            return {'success': False, 'message': '连接不存在'}
        try:
            connector = DatabaseConnector(conn.to_config_dict())
            result = connector.test_connection()
            connector.close()
            return {'success': result, 'message': '连接测试成功' if result else '连接测试失败'}
        except Exception as e:
            return {'success': False, 'message': f'连接测试失败: {str(e)}'}

    @staticmethod
    def get_connector(conn_id: int) -> Optional[DatabaseConnector]:
        conn = DatabaseConnection.query.get(conn_id)
        if not conn:
            return None
        return DatabaseConnector(conn.to_config_dict())
