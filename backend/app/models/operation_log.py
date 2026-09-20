from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='操作用户ID')
    username = db.Column(db.String(80), nullable=False, comment='操作用户名')
    action = db.Column(db.String(100), nullable=False, comment='操作类型: create/update/delete/login/logout/upload/export等')
    target_type = db.Column(db.String(50), comment='目标类型: user/role/script/database/query/task等')
    target_id = db.Column(db.Integer, comment='目标ID')
    detail = db.Column(db.Text, comment='操作详情')
    ip_address = db.Column(db.String(45), comment='操作IP地址')
    user_agent = db.Column(db.String(500), comment='浏览器UA')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'detail': self.detail,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': beijing_isoformat(self.created_at),
        }
