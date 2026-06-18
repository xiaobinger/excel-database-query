from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class AgentMemory(db.Model):
    """Agent记忆 - 记录用户对特定Agent的偏好、规则和特别要求，跨会话持久化"""
    __tablename__ = 'agent_memories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    agent_id = db.Column(db.Integer, db.ForeignKey('ai_agents.id'), nullable=False, comment='关联Agent ID')
    memory_type = db.Column(db.String(20), nullable=False, default='rule', comment='记忆类型: rule(规则)/preference(偏好)/fact(事实)')
    content = db.Column(db.Text, nullable=False, comment='记忆内容')
    source = db.Column(db.String(20), default='auto', comment='来源: auto(AI自动提取)/manual(手动添加)')
    chat_id = db.Column(db.Integer, comment='来源对话ID')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'agent_id': self.agent_id,
            'memory_type': self.memory_type,
            'content': self.content,
            'source': self.source,
            'chat_id': self.chat_id,
            'is_active': self.is_active,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
