from datetime import datetime
from app import db
import json
from app.utils.helpers import beijing_isoformat


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    description = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False, comment='super admin flag')
    menu_permissions = db.Column(db.Text, comment='menu permissions (JSON array)')
    button_permissions = db.Column(db.Text, comment='button permissions (JSON array)')
    agent_permissions = db.Column(db.Text, comment='agent permissions (JSON array)')
    can_switch_agent = db.Column(db.Boolean, default=False, comment='是否允许切换Agent')
    can_switch_model = db.Column(db.Boolean, default=False, comment='是否允许切换模型')
    model_permissions = db.Column(db.Text, comment='model permissions (JSON array, 存储可用的AI配置ID)')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_menu_permissions(self):
        if self.menu_permissions:
            try:
                return json.loads(self.menu_permissions)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_menu_permissions(self, perms):
        self.menu_permissions = json.dumps(perms) if perms else None

    def get_button_permissions(self):
        if self.button_permissions:
            try:
                return json.loads(self.button_permissions)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_button_permissions(self, perms):
        self.button_permissions = json.dumps(perms) if perms else None

    def get_agent_permissions(self):
        if self.agent_permissions:
            try:
                return json.loads(self.agent_permissions)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_agent_permissions(self, perms):
        self.agent_permissions = json.dumps(perms) if perms else None

    def get_model_permissions(self):
        if self.model_permissions:
            try:
                return json.loads(self.model_permissions)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_model_permissions(self, perms):
        self.model_permissions = json.dumps(perms) if perms else None

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_admin': self.is_admin,
            'menu_permissions': self.get_menu_permissions(),
            'button_permissions': self.get_button_permissions(),
            'agent_permissions': self.get_agent_permissions(),
            'can_switch_agent': self.can_switch_agent or False,
            'can_switch_model': self.can_switch_model or False,
            'model_permissions': self.get_model_permissions(),
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<Role {self.name}>'
