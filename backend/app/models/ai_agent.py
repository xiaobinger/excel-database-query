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
    mcp_server_ids = db.Column(db.Text, comment='授予的MCP Server ID列表JSON')
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

    def get_mcp_server_ids(self) -> list:
        """获取授予的MCP Server ID列表"""
        if not self.mcp_server_ids:
            return []
        try:
            ids = json.loads(self.mcp_server_ids)
            return [int(i) for i in ids] if isinstance(ids, list) else []
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    def set_mcp_server_ids(self, ids: list):
        """设置授予的MCP Server ID列表"""
        if not ids:
            self.mcp_server_ids = None
        else:
            self.mcp_server_ids = json.dumps([int(i) for i in ids])

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'enabled_tools': self.get_enabled_tools(),
            'mcp_server_ids': self.get_mcp_server_ids(),
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }