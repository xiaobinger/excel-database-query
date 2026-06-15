import logging
import threading
import time
from typing import Optional, Dict, Any
from app.utils.db_connector import DatabaseConnector

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """数据库连接池管理器，启动时预建立SSH隧道和数据库连接，后续请求直接复用"""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._connectors: Dict[int, DatabaseConnector] = {}
        self._connector_lock = threading.Lock()
        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'ConnectionPoolManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ConnectionPoolManager()
        return cls._instance

    def initialize(self, app=None):
        """启动时预建立所有活跃数据库连接（含SSH隧道）"""
        if self._initialized:
            return

        logger.info('连接池管理器: 开始预建立数据库连接...')

        try:
            if app:
                with app.app_context():
                    self._init_all_connections()
            else:
                self._init_all_connections()
        except Exception as e:
            logger.error(f'连接池管理器: 预建立连接失败: {e}', exc_info=True)

        self._initialized = True
        logger.info(f'连接池管理器: 初始化完成，已建立 {len(self._connectors)} 个连接')

    def _init_all_connections(self):
        """遍历所有活跃的数据库配置，预建立连接"""
        from app.models.database import DatabaseConnection

        connections = DatabaseConnection.query.filter_by(is_active=True).all()
        for conn in connections:
            try:
                self._create_connector(conn)
            except Exception as e:
                logger.warning(f'连接池管理器: 预建立连接 [{conn.name}] 失败: {e}')

    def _create_connector(self, conn_model) -> Optional[DatabaseConnector]:
        """创建并缓存一个数据库连接"""
        config = conn_model.to_config_dict()
        connector = DatabaseConnector(config)

        # 测试连接是否可用
        if connector.test_connection():
            with self._connector_lock:
                self._connectors[conn_model.id] = connector
            logger.info(f'连接池管理器: 连接 [{conn_model.name}] 建立成功'
                        + (' (SSH隧道)' if config.get('ssh_tunnel', {}).get('enabled') else ''))
            return connector
        else:
            # 连接测试失败，仍然缓存（后续请求时可能恢复）
            with self._connector_lock:
                self._connectors[conn_model.id] = connector
            logger.warning(f'连接池管理器: 连接 [{conn_model.name}] 测试失败，已缓存但可能不可用')
            return connector

    def get_connector(self, conn_id: int) -> Optional[DatabaseConnector]:
        """获取数据库连接，如果缓存中没有则创建新连接"""
        with self._connector_lock:
            connector = self._connectors.get(conn_id)

        if connector:
            # 检查连接是否仍然有效
            if self._check_connector_health(connector):
                return connector
            else:
                # 连接失效，移除旧连接并重建
                logger.info(f'连接池管理器: 连接 [ID={conn_id}] 已失效，正在重建...')
                self._remove_connector(conn_id)

        # 创建新连接
        from app.models.database import DatabaseConnection
        conn_model = DatabaseConnection.query.get(conn_id)
        if not conn_model:
            return None

        try:
            return self._create_connector(conn_model)
        except Exception as e:
            logger.error(f'连接池管理器: 创建连接 [{conn_model.name}] 失败: {e}')
            return None

    def _check_connector_health(self, connector: DatabaseConnector) -> bool:
        """检查连接是否健康"""
        try:
            if not connector.engine:
                return False
            from sqlalchemy import text
            with connector.get_connection() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _remove_connector(self, conn_id: int):
        """移除并关闭指定连接"""
        with self._connector_lock:
            connector = self._connectors.pop(conn_id, None)
        if connector:
            try:
                connector.close()
            except Exception:
                pass

    def reload_connector(self, conn_id: int):
        """重新加载指定数据库连接（配置更新时调用）"""
        logger.info(f'连接池管理器: 重新加载连接 [ID={conn_id}]')
        self._remove_connector(conn_id)

        from app.models.database import DatabaseConnection
        conn_model = DatabaseConnection.query.get(conn_id)
        if conn_model and conn_model.is_active:
            try:
                self._create_connector(conn_model)
            except Exception as e:
                logger.error(f'连接池管理器: 重新加载连接失败: {e}')

    def remove_connector(self, conn_id: int):
        """移除指定连接（数据库配置删除/禁用时调用）"""
        logger.info(f'连接池管理器: 移除连接 [ID={conn_id}]')
        self._remove_connector(conn_id)

    def reload_all(self, app=None):
        """重新加载所有连接"""
        logger.info('连接池管理器: 重新加载所有连接...')

        # 关闭所有现有连接
        with self._connector_lock:
            old_connectors = dict(self._connectors)
            self._connectors.clear()

        for conn_id, connector in old_connectors.items():
            try:
                connector.close()
            except Exception:
                pass

        # 重新建立连接
        if app:
            with app.app_context():
                self._init_all_connections()
        else:
            self._init_all_connections()

        logger.info(f'连接池管理器: 重新加载完成，已建立 {len(self._connectors)} 个连接')

    def get_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        status = {}
        with self._connector_lock:
            for conn_id, connector in self._connectors.items():
                healthy = self._check_connector_health(connector)
                status[conn_id] = {
                    'healthy': healthy,
                    'ssh_enabled': connector.ssh_enabled,
                    'ssh_tunnel_active': connector.ssh_tunnel is not None and connector.ssh_tunnel.is_active if connector.ssh_tunnel else False,
                }
        return status

    def shutdown(self):
        """关闭所有连接（应用退出时调用）"""
        logger.info('连接池管理器: 正在关闭所有连接...')
        with self._connector_lock:
            connectors = dict(self._connectors)
            self._connectors.clear()

        for conn_id, connector in connectors.items():
            try:
                connector.close()
            except Exception:
                pass

        self._initialized = False
        logger.info('连接池管理器: 所有连接已关闭')
