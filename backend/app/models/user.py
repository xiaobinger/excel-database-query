from datetime import datetime
from app import db
import json
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.helpers import beijing_isoformat


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100))
    gender = db.Column(db.String(10), default='male')
    phone = db.Column(db.String(20), comment='手机号')
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    script_ids = db.Column(db.Text, comment='available script id list (JSON)')
    auto_task_ids = db.Column(db.Text, comment='available auto export task id list (JSON)')

    role = db.relationship('Role', backref='users', lazy='joined')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_script_ids(self):
        if self.script_ids:
            try:
                return json.loads(self.script_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_script_ids(self, ids):
        self.script_ids = json.dumps(ids) if ids else None

    def get_auto_task_ids(self):
        if self.auto_task_ids:
            try:
                return json.loads(self.auto_task_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_auto_task_ids(self, ids):
        self.auto_task_ids = json.dumps(ids) if ids else None

    def is_admin(self):
        if self.role and self.role.is_admin:
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'gender': self.gender or 'male',
            'phone': self.phone or '',
            'role_id': self.role_id,
            'is_active': self.is_active,
            'script_ids': self.get_script_ids(),
            'auto_task_ids': self.get_auto_task_ids(),
            'created_at': beijing_isoformat(self.created_at),
        }

    def to_dict_with_role(self):
        data = self.to_dict()
        if self.role:
            data['role'] = self.role.to_dict()
        else:
            data['role'] = None
        return data

    def __repr__(self):
        return f'<User {self.username}>'
