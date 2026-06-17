from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class UserBehavior(db.Model):
    __tablename__ = 'user_behaviors'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    agent_id = db.Column(db.Integer, comment='关联Agent ID')
    action = db.Column(db.String(100), nullable=False, comment='行为类型: query/export/view/create/edit/delete/chat')
    target_type = db.Column(db.String(50), comment='目标类型: script/task/database/export_script/auto_task')
    target_id = db.Column(db.Integer, comment='目标ID')
    detail = db.Column(db.Text, comment='行为详情JSON')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json
        detail_data = None
        if self.detail:
            try:
                detail_data = json.loads(self.detail)
            except:
                detail_data = self.detail
        return {
            'id': self.id,
            'user_id': self.user_id,
            'agent_id': self.agent_id,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'detail': detail_data,
            'created_at': beijing_isoformat(self.created_at),
        }
