from datetime import datetime
import json
from app import db
from app.utils.helpers import beijing_isoformat


class AiAgent(db.Model):
    __tablename__ = 'ai_agents'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='Agent名称')
    description = db.Column(db.String(500), comment='Agent描述')
    agent_role = db.Column(db.String(20), default='general', nullable=False, comment='Agent角色: general(通用)/executor(执行者)/supervisor(监督者)')
    can_confirm_execution = db.Column(db.Boolean, default=False, comment='是否授权该Agent(作为监督者)直接确认执行待确认操作，跳过提交者人工确认')
    can_retry_processing = db.Column(db.Boolean, default=False, comment='是否授权该Agent(作为监督者)智能重试卡住的处理中工单(超时未完成自动触发重试)')
    can_close_ticket = db.Column(db.Boolean, default=False, comment='是否授权该Agent(作为监督者)自动验收已处理工单并结束(无需提交者人工确认结束)')
    enable_chat_review = db.Column(db.Boolean, default=False, comment='是否启用对话复核(仅执行者角色有意义，开启后监督者会复核回复质量)')
    max_supervisor_rounds = db.Column(db.Integer, default=3, comment='监督者最大监督轮次(仅监督者角色有意义，1-20默认3)')
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
            'agent_role': self.agent_role or 'general',
            'can_confirm_execution': bool(self.can_confirm_execution),
            'can_retry_processing': bool(self.can_retry_processing),
            'can_close_ticket': bool(self.can_close_ticket),
            'enable_chat_review': bool(self.enable_chat_review),
            'max_supervisor_rounds': self.max_supervisor_rounds if self.max_supervisor_rounds else 3,
            'system_prompt': self.system_prompt,
            'enabled_tools': self.get_enabled_tools(),
            'mcp_server_ids': self.get_mcp_server_ids(),
            'is_default': self.is_default,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }