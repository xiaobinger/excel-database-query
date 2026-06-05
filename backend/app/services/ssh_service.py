import logging
from typing import List, Optional
from app import db
from app.models.ssh_config import SshConfig
from app.utils.db_connector import DatabaseConnector
from app.models.database import DatabaseConnection

logger = logging.getLogger(__name__)


class SshService:

    @staticmethod
    def get_all() -> List[SshConfig]:
        return SshConfig.query.filter_by(is_active=True).order_by(SshConfig.created_at.desc()).all()

    @staticmethod
    def get_by_id(ssh_id: int) -> Optional[SshConfig]:
        return SshConfig.query.get(ssh_id)

    @staticmethod
    def create(data: dict) -> SshConfig:
        ssh_config = SshConfig(
            name=data['name'],
            host=data['host'],
            port=int(data.get('port', 22)),
            username=data['username'],
            pkey_path=data.get('pkey_path'),
            local_bind_port=int(data['local_bind_port']) if data.get('local_bind_port') is not None else None,
        )
        if data.get('password'):
            ssh_config.set_password(data['password'])
        db.session.add(ssh_config)
        db.session.commit()
        logger.info(f"创建SSH配置: {ssh_config.name}")
        return ssh_config

    @staticmethod
    def update(ssh_id: int, data: dict) -> Optional[SshConfig]:
        ssh_config = SshConfig.query.get(ssh_id)
        if not ssh_config:
            return None
        int_fields = ['port', 'local_bind_port']
        for key in ['name', 'host', 'port', 'username', 'pkey_path', 'local_bind_port', 'is_active']:
            if key in data:
                val = data[key]
                if key in int_fields and val is not None:
                    val = int(val)
                setattr(ssh_config, key, val)
        if 'password' in data and data['password']:
            ssh_config.set_password(data['password'])
        db.session.commit()
        logger.info(f"更新SSH配置: {ssh_config.name}")
        return ssh_config

    @staticmethod
    def delete(ssh_id: int) -> bool:
        ssh_config = SshConfig.query.get(ssh_id)
        if not ssh_config:
            return False
        conn_count = DatabaseConnection.query.filter_by(ssh_config_id=ssh_id, is_active=True).count()
        if conn_count > 0:
            return False
        ssh_config.is_active = False
        db.session.commit()
        logger.info(f"删除SSH配置: {ssh_config.name}")
        return True

    @staticmethod
    def test_connection(ssh_id: int) -> dict:
        ssh_config = SshConfig.query.get(ssh_id)
        if not ssh_config:
            return {'success': False, 'message': 'SSH配置不存在'}
        try:
            from sshtunnel import SSHTunnelForwarder
            ssh_port = int(ssh_config.port)
            local_bind_port = ssh_config.local_bind_port or DatabaseConnector._get_available_local_port_static()
            tunnel_kwargs = {
                'ssh_address_or_host': (ssh_config.host, ssh_port),
                'ssh_username': ssh_config.username,
                'remote_bind_address': ('127.0.0.1', 22),
                'local_bind_address': ('127.0.0.1', local_bind_port)
            }
            ssh_password = ssh_config.get_password()
            if ssh_password:
                tunnel_kwargs['ssh_password'] = ssh_password
            if ssh_config.pkey_path:
                tunnel_kwargs['ssh_pkey'] = ssh_config.pkey_path
            tunnel = SSHTunnelForwarder(**tunnel_kwargs)
            tunnel.start()
            tunnel.stop()
            return {'success': True, 'message': 'SSH连接测试成功'}
        except Exception as e:
            return {'success': False, 'message': f'SSH连接测试失败: {str(e)}'}
