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

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_admin': self.is_admin,
            'menu_permissions': self.get_menu_permissions(),
            'button_permissions': self.get_button_permissions(),
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<Role {self.name}>'
