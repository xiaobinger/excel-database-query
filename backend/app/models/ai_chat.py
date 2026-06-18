from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class AiChat(db.Model):
    __tablename__ = 'ai_chats'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    title = db.Column(db.String(200), comment='对话标题')
    agent_id = db.Column(db.Integer, comment='关联Agent ID')
    model_id = db.Column(db.Integer, comment='关联模型ID(AiConfig)')
    is_archived = db.Column(db.Boolean, default=False, comment='是否归档')
    is_deleted = db.Column(db.Boolean, default=False, comment='是否软删除')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'agent_id': self.agent_id,
            'model_id': self.model_id,
            'is_archived': self.is_archived,
            'is_deleted': self.is_deleted,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }


class AiChatMessage(db.Model):
    __tablename__ = 'ai_chat_messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('ai_chats.id'), nullable=False, comment='对话ID')
    agent_id = db.Column(db.Integer, comment='关联Agent ID')
    role = db.Column(db.String(20), nullable=False, comment='角色: user/assistant/system')
    content = db.Column(db.Text, comment='消息内容')
    tokens_used = db.Column(db.Integer, default=0, comment='消耗token总数')
    prompt_tokens = db.Column(db.Integer, default=0, comment='输入token数')
    completion_tokens = db.Column(db.Integer, default=0, comment='输出token数')
    cache_creation_tokens = db.Column(db.Integer, default=0, comment='缓存写入token数')
    cache_read_tokens = db.Column(db.Integer, default=0, comment='缓存命中token数')
    elapsed = db.Column(db.Float, default=0, comment='响应耗时(秒)')
    is_deleted = db.Column(db.Boolean, default=False, comment='是否软删除')
    msg_metadata = db.Column('metadata', db.Text, comment='消息元数据(JSON)，用于存储工具调用状态等')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        result = {
            'id': self.id,
            'chat_id': self.chat_id,
            'agent_id': self.agent_id,
            'role': self.role,
            'content': self.content,
            'tokens_used': self.tokens_used,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'cache_creation_tokens': self.cache_creation_tokens or 0,
            'cache_read_tokens': self.cache_read_tokens or 0,
            'elapsed': self.elapsed,
            'created_at': beijing_isoformat(self.created_at),
        }
        if self.msg_metadata:
            try:
                import json
                result['_metadata'] = json.loads(self.msg_metadata)
            except:
                pass
        return result
