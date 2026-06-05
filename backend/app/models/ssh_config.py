from datetime import datetime
from app import db
from cryptography.fernet import Fernet
import base64
import hashlib
from app.utils.helpers import beijing_isoformat


class SshConfig(db.Model):
    __tablename__ = 'ssh_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='配置名称')
    host = db.Column(db.String(255), nullable=False, comment='SSH主机地址')
    port = db.Column(db.Integer, nullable=False, default=22, comment='SSH端口')
    username = db.Column(db.String(100), nullable=False, comment='SSH用户名')
    encrypted_password = db.Column(db.Text, comment='加密后的SSH密码')
    pkey_path = db.Column(db.String(500), comment='SSH私钥路径')
    local_bind_port = db.Column(db.Integer, comment='SSH本地绑定端口')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    database_connections = db.relationship('DatabaseConnection', backref='ssh_config', lazy='dynamic')

    def set_password(self, password: str):
        if not password:
            self.encrypted_password = None
            return
        key = self._get_encryption_key()
        f = Fernet(key)
        self.encrypted_password = f.encrypt(password.encode('utf-8')).decode('utf-8')

    def get_password(self) -> str:
        if not self.encrypted_password:
            return ''
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.decrypt(self.encrypted_password.encode('utf-8')).decode('utf-8')

    @staticmethod
    def _get_encryption_key() -> bytes:
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(key)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'pkey_path': self.pkey_path,
            'local_bind_port': self.local_bind_port,
            'is_active': self.is_active,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }

    def to_tunnel_config(self) -> dict:
        config = {
            'host': self.host,
            'port': self.port,
            'username': self.username,
        }
        password = self.get_password()
        if password:
            config['password'] = password
        if self.pkey_path:
            config['pkey_path'] = self.pkey_path
        if self.local_bind_port:
            config['local_bind_port'] = self.local_bind_port
        return config

    def __repr__(self):
        return f'<SshConfig {self.name}>'
