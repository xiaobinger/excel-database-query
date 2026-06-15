from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class ToolMemory(db.Model):
    """工具调用记忆 - 记录用户成功执行的工具调用模式，供AI参考"""
    __tablename__ = 'tool_memories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    intent = db.Column(db.String(200), nullable=False, comment='用户意图关键词，如"查询SN绑定状态"')
    tool_name = db.Column(db.String(100), nullable=False, comment='工具名称，如request_lookup')
    tool_args = db.Column(db.Text, comment='工具参数JSON，如{"lookup_name":"查询SN激活绑定状态","params":{"device_sn":"..."}}')
    success_count = db.Column(db.Integer, default=1, comment='成功执行次数')
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow, comment='最后使用时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json
        tool_args_data = None
        if self.tool_args:
            try:
                tool_args_data = json.loads(self.tool_args)
            except:
                tool_args_data = self.tool_args
        return {
            'id': self.id,
            'user_id': self.user_id,
            'intent': self.intent,
            'tool_name': self.tool_name,
            'tool_args': tool_args_data,
            'success_count': self.success_count,
            'last_used_at': beijing_isoformat(self.last_used_at),
        }
