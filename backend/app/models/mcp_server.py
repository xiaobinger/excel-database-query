from datetime import datetime
import json
from app import db
from app.utils.helpers import beijing_isoformat


def _fernet():
    from cryptography.fernet import Fernet
    import base64, hashlib
    from flask import current_app
    secret = current_app.config.get('ENCRYPTION_KEY', 'encryption-key-32-bytes-long-change!')
    key = hashlib.sha256(secret.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class McpServer(db.Model):
    """MCP Server 配置 - 独立配置，可授予给AI Agent扩展其工具能力"""
    __tablename__ = 'mcp_servers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='名称(唯一，用于工具前缀)')
    description = db.Column(db.String(500), comment='描述')
    transport_type = db.Column(db.String(20), nullable=False, default='stdio', comment='传输类型: stdio/sse/streamable_http')
    command = db.Column(db.Text, comment='stdio启动命令，如: uvx mcp-server-time 或 npx -y xxx')
    env_json = db.Column(db.Text, comment='stdio环境变量(JSON，加密存储)')
    url = db.Column(db.String(500), comment='远程服务URL(sse/streamable_http)')
    headers_json = db.Column(db.Text, comment='请求头(JSON，加密存储)')
    timeout_seconds = db.Column(db.Integer, default=60, comment='连接/调用超时(秒)')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    tools_cache = db.Column(db.Text, comment='工具清单缓存(JSON)')
    tools_updated_at = db.Column(db.DateTime, comment='工具清单刷新时间')
    last_error = db.Column(db.Text, comment='最近一次连接/调用错误')
    created_by = db.Column(db.Integer, comment='创建者ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_env(self, env: dict):
        """加密存储环境变量"""
        if not env:
            self.env_json = None
            return
        self.env_json = _fernet().encrypt(json.dumps(env, ensure_ascii=False).encode('utf-8')).decode('utf-8')

    def get_env(self) -> dict:
        if not self.env_json:
            return {}
        try:
            return json.loads(_fernet().decrypt(self.env_json.encode('utf-8')).decode('utf-8'))
        except Exception:
            return {}

    def set_headers(self, headers: dict):
        """加密存储请求头"""
        if not headers:
            self.headers_json = None
            return
        self.headers_json = _fernet().encrypt(json.dumps(headers, ensure_ascii=False).encode('utf-8')).decode('utf-8')

    def get_headers(self) -> dict:
        if not self.headers_json:
            return {}
        try:
            return json.loads(_fernet().decrypt(self.headers_json.encode('utf-8')).decode('utf-8'))
        except Exception:
            return {}

    def get_tools_cache(self) -> list:
        if not self.tools_cache:
            return []
        try:
            return json.loads(self.tools_cache)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tools_cache(self, tools: list):
        self.tools_cache = json.dumps(tools, ensure_ascii=False) if tools else None
        self.tools_updated_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'transport_type': self.transport_type,
            'command': self.command,
            'url': self.url,
            'timeout_seconds': self.timeout_seconds,
            'is_active': self.is_active,
            'tools_count': len(self.get_tools_cache()),
            'tools': self.get_tools_cache(),
            'tools_updated_at': beijing_isoformat(self.tools_updated_at),
            'last_error': self.last_error,
            'has_env': bool(self.env_json),
            'has_headers': bool(self.headers_json),
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
