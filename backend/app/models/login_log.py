from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class LoginLog(db.Model):
    __tablename__ = 'login_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='用户ID')
    username = db.Column(db.String(80), nullable=False, comment='登录用户名')
    ip_address = db.Column(db.String(45), comment='登录IP地址')
    user_agent = db.Column(db.String(500), comment='浏览器UA')
    status = db.Column(db.String(20), nullable=False, comment='登录状态: success/failed')
    fail_reason = db.Column(db.String(200), comment='失败原因')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'status': self.status,
            'fail_reason': self.fail_reason,
            'created_at': beijing_isoformat(self.created_at),
        }
