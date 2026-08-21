from datetime import datetime
import hashlib
import json
import secrets
from app import db
from app.utils.helpers import beijing_isoformat


def _fernet():
    from cryptography.fernet import Fernet
    import base64
    from flask import current_app
    secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
    key = hashlib.sha256(secret.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class ApiKey(db.Model):
    """开放API令牌 - 对外提供AI对话能力的认证凭证"""
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='名称/备注')
    api_key = db.Column(db.Text, comment='key明文(Fernet加密存储，管理页回显用)')
    api_key_hash = db.Column(db.String(64), unique=True, index=True, comment='key的sha256(查询用)')
    model_mapping = db.Column(db.Text, comment='模型映射JSON: [{"external": "gpt-4o", "config_id": 3}]')
    ip_whitelist = db.Column(db.Text, comment='IP白名单JSON: ["1.2.3.4", "10.0.0.0/8"]，空表示不限')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    last_used_at = db.Column(db.DateTime, comment='最近使用时间')
    created_by = db.Column(db.Integer, comment='创建者ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def generate_key_string() -> str:
        return 'sk-' + secrets.token_urlsafe(32)

    def set_api_key(self, val: str):
        """加密存储key明文并记录哈希"""
        self.api_key = _fernet().encrypt((val or '').encode('utf-8')).decode('utf-8')
        self.api_key_hash = hashlib.sha256((val or '').encode('utf-8')).hexdigest()

    def get_api_key(self) -> str:
        if not self.api_key:
            return ''
        try:
            return _fernet().decrypt(self.api_key.encode('utf-8')).decode('utf-8')
        except Exception:
            return ''

    def get_model_mapping(self) -> list:
        """获取模型映射 [{'external': 外部名, 'config_id': 内部AiConfig ID}]"""
        if not self.model_mapping:
            return []
        try:
            data = json.loads(self.model_mapping)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_model_mapping(self, mapping: list):
        if not mapping:
            self.model_mapping = None
        else:
            self.model_mapping = json.dumps(mapping, ensure_ascii=False)

    def get_ip_whitelist(self) -> list:
        if not self.ip_whitelist:
            return []
        try:
            data = json.loads(self.ip_whitelist)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_ip_whitelist(self, ips: list):
        if not ips:
            self.ip_whitelist = None
        else:
            self.ip_whitelist = json.dumps([str(i).strip() for i in ips if str(i).strip()], ensure_ascii=False)

    def to_dict(self, include_key: bool = False) -> dict:
        result = {
            'id': self.id,
            'name': self.name,
            'model_mapping': self.get_model_mapping(),
            'ip_whitelist': self.get_ip_whitelist(),
            'is_active': self.is_active,
            'last_used_at': beijing_isoformat(self.last_used_at),
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
        if include_key:
            result['api_key'] = self.get_api_key()
        return result
