from datetime import datetime
from app import db
from cryptography.fernet import Fernet
import base64
import hashlib
from app.utils.helpers import beijing_isoformat


class DatabaseConnection(db.Model):
    __tablename__ = 'database_connections'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='连接名称')
    description = db.Column(db.String(500), comment='连接描述')
    db_type = db.Column(db.String(50), nullable=False, default='mysql', comment='数据库类型')
    host = db.Column(db.String(255), nullable=False, comment='主机地址')
    port = db.Column(db.Integer, nullable=False, default=3306, comment='端口号')
    database_name = db.Column(db.String(255), nullable=False, comment='数据库名')
    username = db.Column(db.String(100), nullable=False, comment='用户名')
    encrypted_password = db.Column(db.Text, nullable=False, comment='加密后的密码')
    pool_size = db.Column(db.Integer, default=5, comment='连接池大小')
    max_overflow = db.Column(db.Integer, default=10, comment='最大溢出连接数')
    ssh_enabled = db.Column(db.Boolean, default=False, comment='是否启用SSH隧道')
    ssh_config_id = db.Column(db.Integer, db.ForeignKey('ssh_configs.id'), nullable=True, comment='关联SSH配置')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    scripts = db.relationship('Script', backref='database_connection', lazy='dynamic')

    def set_password(self, password: str):
        key = self._get_encryption_key()
        f = Fernet(key)
        self.encrypted_password = f.encrypt(password.encode('utf-8')).decode('utf-8')

    def get_password(self) -> str:
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.decrypt(self.encrypted_password.encode('utf-8')).decode('utf-8')

    @staticmethod
    def _get_encryption_key() -> bytes:
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(key)

    def to_config_dict(self) -> dict:
        config = {
            'conn_id': self.id,
            'type': self.db_type,
            'host': self.host,
            'port': self.port,
            'database': self.database_name,
            'username': self.username,
            'password': self.get_password(),
            'pool_size': self.pool_size,
            'max_overflow': self.max_overflow,
        }
        if self.ssh_enabled and self.ssh_config:
            tunnel_config = self.ssh_config.to_tunnel_config()
            tunnel_config['enabled'] = True
            config['ssh_tunnel'] = tunnel_config
        return config

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'db_type': self.db_type,
            'host': self.host,
            'port': self.port,
            'database_name': self.database_name,
            'username': self.username,
            'pool_size': self.pool_size,
            'max_overflow': self.max_overflow,
            'ssh_enabled': self.ssh_enabled,
            'ssh_config_id': self.ssh_config_id,
            'ssh_config_name': self.ssh_config.name if self.ssh_config else None,
            'is_active': self.is_active,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }

    def __repr__(self):
        return f'<DatabaseConnection {self.name}>'
