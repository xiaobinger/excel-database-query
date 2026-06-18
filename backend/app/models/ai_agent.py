from datetime import datetime
import json
from app import db
from app.utils.helpers import beijing_isoformat


class AiAgent(db.Model):
    __tablename__ = 'ai_agents'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='Agent名称')
    description = db.Column(db.String(500), comment='Agent描述')
    system_prompt = db.Column(db.Text, nullable=False, comment='系统提示词')
    enabled_tools = db.Column(db.Text, comment='启用的AI工具列表JSON，null表示全部启用')
    is_default = db.Column(db.Boolean, default=False, comment='是否默认Agent')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_by = db.Column(db.Integer, comment='创建者ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_enabled_tools(self) -> list:
        """获取启用的工具列表，返回None表示全部启用"""
        if not self.enabled_tools:
            return None
        try:
            return json.loads(self.enabled_tools)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_enabled_tools(self, tools: list):
        """设置启用的工具列表"""
        if tools is None:
            self.enabled_tools = None
        else:
            self.enabled_tools = json.dumps(tools, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'enabled_tools': self.get_enabled_tools(),
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }