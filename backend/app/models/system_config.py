from datetime import datetime
from app import db
from cryptography.fernet import Fernet
import base64
import hashlib
from app.utils.helpers import beijing_isoformat


class SystemConfig(db.Model):
    __tablename__ = 'system_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(100), nullable=False, unique=True)
    config_value = db.Column(db.Text)
    encrypted_value = db.Column(db.Text)
    description = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    EMAIL_SMTP_HOST = 'email_smtp_host'
    EMAIL_SMTP_PORT = 'email_smtp_port'
    EMAIL_SMTP_USER = 'email_smtp_user'
    EMAIL_SMTP_PASSWORD = 'email_smtp_password'
    EMAIL_SMTP_SSL = 'email_smtp_ssl'
    EMAIL_FROM_NAME = 'email_from_name'
    EMAIL_FROM_ADDRESS = 'email_from_address'

    COLUMN_SYNONYM_GROUPS = 'column_synonym_groups'

    def set_encrypted_value(self, val: str):
        if not val:
            self.encrypted_value = None
            return
        key = self._get_encryption_key()
        f = Fernet(key)
        self.encrypted_value = f.encrypt(val.encode('utf-8')).decode('utf-8')

    def get_encrypted_value(self) -> str:
        if not self.encrypted_value:
            return ''
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.decrypt(self.encrypted_value.encode('utf-8')).decode('utf-8')

    @staticmethod
    def _get_encryption_key() -> bytes:
        from flask import current_app
        secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
        key = hashlib.sha256(secret.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(key)

    def to_dict(self) -> dict:
        return {
            'config_key': self.config_key,
            'config_value': self.config_value,
            'description': self.description,
            'updated_at': beijing_isoformat(self.updated_at),
        }
