from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class AiConfig(db.Model):
    __tablename__ = 'ai_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='配置名称')
    provider = db.Column(db.String(50), nullable=False, default='openai', comment='AI提供商: openai/zhipu/deepseek/custom')
    api_key = db.Column(db.Text, comment='API密钥(加密存储)')
    api_base = db.Column(db.String(500), comment='API基础URL')
    model_name = db.Column(db.String(100), comment='模型名称')
    is_default = db.Column(db.Boolean, default=False, comment='是否默认配置')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    max_tokens = db.Column(db.Integer, default=4096, comment='最大token数')
    temperature = db.Column(db.Float, default=0.7, comment='温度参数')
    system_prompt = db.Column(db.Text, comment='系统提示词')
    description = db.Column(db.String(500), comment='描述')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_api_key(self, val: str):
        if not val:
            self.api_key = None
            return
        from cryptography.fernet import Fernet
        import base64, hashlib
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        f = Fernet(base64.urlsafe_b64encode(key))
        self.api_key = f.encrypt(val.encode('utf-8')).decode('utf-8')

    def get_api_key(self) -> str:
        if not self.api_key:
            return ''
        from cryptography.fernet import Fernet
        import base64, hashlib
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        f = Fernet(base64.urlsafe_b64encode(key))
        return f.decrypt(self.api_key.encode('utf-8')).decode('utf-8')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'provider': self.provider,
            'api_base': self.api_base,
            'model_name': self.model_name,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'system_prompt': self.system_prompt,
            'description': self.description,
            'has_api_key': bool(self.api_key),
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
