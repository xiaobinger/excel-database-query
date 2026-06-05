from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class BusinessSystem(db.Model):
    __tablename__ = 'business_systems'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='系统名称')
    description = db.Column(db.String(500), comment='系统描述')
    logo_url = db.Column(db.String(500), comment='Logo URL或图标class')
    website_url = db.Column(db.String(500), nullable=False, comment='系统网址')
    category = db.Column(db.String(50), comment='分类')
    sort_order = db.Column(db.Integer, default=0, comment='排序')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')

    # SSO配置
    sso_enabled = db.Column(db.Boolean, default=False, comment='是否启用SSO')
    sso_url = db.Column(db.String(500), comment='SSO登录地址')
    sso_method = db.Column(db.String(10), default='POST', comment='SSO请求方式 GET/POST')
    sso_phone_field = db.Column(db.String(50), default='phone', comment='手机号字段名')
    sso_token_field = db.Column(db.String(50), default='token', comment='Token字段名')
    sso_extra_params = db.Column(db.Text, comment='额外参数(JSON)')
    sso_token_key = db.Column(db.String(100), comment='SSO签名密钥(加密)')
    sso_response_token_key = db.Column(db.String(100), default='token', comment='SSO响应中token的路径(如data.token)')
    sso_token_pass_key = db.Column(db.String(50), default='token', comment='跳转网站时传递token的参数名')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_extra_params(self):
        if self.sso_extra_params:
            try:
                import json
                return json.loads(self.sso_extra_params)
            except:
                return {}
        return {}

    def set_extra_params(self, params):
        import json
        self.sso_extra_params = json.dumps(params) if params else None

    def get_sso_token_key(self):
        if not self.sso_token_key:
            return ''
        from cryptography.fernet import Fernet
        import base64, hashlib
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        key = base64.urlsafe_b64encode(key)
        f = Fernet(key)
        return f.decrypt(self.sso_token_key.encode('utf-8')).decode('utf-8')

    def set_sso_token_key(self, val):
        if not val:
            self.sso_token_key = None
            return
        from cryptography.fernet import Fernet
        import base64, hashlib
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        key = base64.urlsafe_b64encode(key)
        f = Fernet(key)
        self.sso_token_key = f.encrypt(val.encode('utf-8')).decode('utf-8')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'logo_url': self.logo_url,
            'website_url': self.website_url,
            'category': self.category,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
            'sso_enabled': self.sso_enabled,
            'sso_url': self.sso_url,
            'sso_method': self.sso_method,
            'sso_phone_field': self.sso_phone_field,
            'sso_token_field': self.sso_token_field,
            'sso_extra_params': self.get_extra_params(),
            'has_token_key': bool(self.sso_token_key),
            'sso_response_token_key': self.sso_response_token_key or 'token',
            'sso_token_pass_key': self.sso_token_pass_key or 'token',
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
