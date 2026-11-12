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
            is_jump_host=bool(data.get('is_jump_host', False)),
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
        for key in ['name', 'host', 'port', 'username', 'pkey_path', 'local_bind_port', 'is_jump_host', 'is_active']:
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
    def probe_targets(ssh_id: int, timeout: int = 8) -> dict:
        """通过指定跳板机探测当前可登录的目标机列表（非跳板机配置）"""
        jump = SshConfig.query.get(ssh_id)
        if not jump or not jump.is_active:
            return {'success': False, 'message': 'SSH配置不存在或已停用'}
        if not jump.is_jump_host:
            return {'success': False, 'message': '所选配置未标记为跳板机'}

        targets = SshConfig.query.filter(
            SshConfig.is_active.is_(True),
            SshConfig.is_jump_host.is_(False),
            SshConfig.id != ssh_id,
        ).order_by(SshConfig.name.asc()).all()
        if not targets:
            return {'success': True, 'data': [], 'unreachable': []}

        from concurrent.futures import ThreadPoolExecutor
        from flask import current_app
        from app.services.system_task_service import SystemTaskService

        app = current_app._get_current_object()

        def _probe(target: SshConfig):
            with app.app_context():
                try:
                    out, err, code = SystemTaskService._run_ssh_command_via_jump(
                        jump, target, 'echo __SSH_OK__', timeout
                    )
                    if code == 0 and '__SSH_OK__' in (out or ''):
                        return {
                            'id': target.id,
                            'name': target.name,
                            'host': target.host,
                            'port': target.port,
                            'username': target.username,
                        }, None
                    detail = (err or out or '').strip()[:200] or f'退出码 {code}'
                    return None, {'id': target.id, 'name': target.name, 'host': target.host, 'reason': detail}
                except Exception as exc:
                    logger.warning(f"跳板机探测目标机失败: {target.name} - {exc}")
                    return None, {'id': target.id, 'name': target.name, 'host': target.host, 'reason': str(exc)[:200]}
                finally:
                    db.session.remove()

        reachable, unreachable = [], []
        with ThreadPoolExecutor(max_workers=min(6, len(targets))) as pool:
            for ok_item, fail_item in pool.map(_probe, targets):
                if ok_item:
                    reachable.append(ok_item)
                if fail_item:
                    unreachable.append(fail_item)
        return {'success': True, 'data': reachable, 'unreachable': unreachable}

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
