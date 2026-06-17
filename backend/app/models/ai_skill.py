from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class AiSkill(db.Model):
    __tablename__ = 'ai_skills'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='技能名称')
    skill_type = db.Column(db.String(50), nullable=False, default='system', comment='技能类型: system/user/auto')
    category = db.Column(db.String(50), comment='分类: query/export/ui/behavior/workflow')
    description = db.Column(db.String(500), comment='描述')
    content = db.Column(db.Text, comment='技能内容JSON')
    trigger_conditions = db.Column(db.Text, comment='触发条件JSON')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='所属用户ID(system类型为空)')
    agent_id = db.Column(db.Integer, db.ForeignKey('ai_agents.id'), comment='关联Agent ID')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    version = db.Column(db.Integer, default=1, comment='版本号')
    usage_count = db.Column(db.Integer, default=0, comment='使用次数')
    source = db.Column(db.String(50), default='manual', comment='来源: manual/auto_learn/ai_generated')
    parent_id = db.Column(db.Integer, db.ForeignKey('ai_skills.id'), comment='父技能ID(用于版本继承)')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        import json
        content_data = None
        if self.content:
            try:
                content_data = json.loads(self.content)
            except:
                content_data = self.content
        trigger_data = None
        if self.trigger_conditions:
            try:
                trigger_data = json.loads(self.trigger_conditions)
            except:
                trigger_data = self.trigger_conditions
        return {
            'id': self.id,
            'name': self.name,
            'skill_type': self.skill_type,
            'category': self.category,
            'description': self.description,
            'content': content_data,
            'trigger_conditions': trigger_data,
            'user_id': self.user_id,
            'agent_id': self.agent_id,
            'is_active': self.is_active,
            'version': self.version,
            'usage_count': self.usage_count,
            'source': self.source,
            'parent_id': self.parent_id,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
