from datetime import datetime
import json
from app import db
from app.utils.helpers import beijing_isoformat


class ApiCallLog(db.Model):
    """开放API调用记录 - 每次对外调用一条（对话内容/耗时/token/模型/IP）"""
    __tablename__ = 'api_call_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey('api_keys.id'), nullable=False, comment='关联ApiKey ID')
    api_key_name = db.Column(db.String(100), comment='ApiKey名称快照（key删除后仍可读）')
    endpoint = db.Column(db.String(20), comment='端点: openai/custom')
    model_requested = db.Column(db.String(100), comment='请求的模型名(外部名或auto)')
    model_used = db.Column(db.String(100), comment='最终调用的模型名')
    caller_ip = db.Column(db.String(64), comment='调用方IP')
    messages = db.Column(db.Text(16000000), comment='请求的对话内容(JSON)，MEDIUMTEXT防止长对话超限')
    response_content = db.Column(db.Text(16000000), comment='AI回复全文，MEDIUMTEXT防止长回复超限')
    tokens_used = db.Column(db.Integer, default=0, comment='消耗token总数')
    prompt_tokens = db.Column(db.Integer, default=0, comment='输入token数')
    completion_tokens = db.Column(db.Integer, default=0, comment='输出token数')
    cache_creation_tokens = db.Column(db.Integer, default=0, comment='缓存写入token数')
    cache_read_tokens = db.Column(db.Integer, default=0, comment='缓存命中token数')
    elapsed = db.Column(db.Float, default=0, comment='响应耗时(秒)')
    is_success = db.Column(db.Boolean, default=True, comment='是否成功')
    error_msg = db.Column(db.Text, comment='失败原因')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_content: bool = False) -> dict:
        result = {
            'id': self.id,
            'api_key_id': self.api_key_id,
            'api_key_name': self.api_key_name,
            'endpoint': self.endpoint,
            'model_requested': self.model_requested,
            'model_used': self.model_used,
            'caller_ip': self.caller_ip,
            'tokens_used': self.tokens_used,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'cache_creation_tokens': self.cache_creation_tokens or 0,
            'cache_read_tokens': self.cache_read_tokens or 0,
            'elapsed': self.elapsed,
            'is_success': self.is_success,
            'error_msg': self.error_msg,
            'created_at': beijing_isoformat(self.created_at),
        }
        if include_content:
            try:
                result['messages'] = json.loads(self.messages) if self.messages else []
            except (json.JSONDecodeError, TypeError):
                result['messages'] = []
            result['response_content'] = self.response_content or ''
        return result
