import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class AiStrategy(db.Model):
    __tablename__ = 'ai_strategies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, default='默认策略', comment='策略名称')

    # Strategy type: priority | round_robin | token_balanced
    strategy_type = db.Column(db.String(50), default='priority', comment='策略类型: priority/round_robin/token_balanced')

    # JSON array of model IDs in order (first = highest priority for priority strategy)
    model_ids = db.Column(db.Text, comment='模型ID列表(JSON array, ordered)')

    # Whether this strategy is currently active (only one should be active)
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')

    # Failover: if a model fails, try the next one (always enabled for safety)
    failover_enabled = db.Column(db.Boolean, default=True, comment='启用故障转移')
    failover_max_retries = db.Column(db.Integer, default=3, comment='最大重试次数')
    failover_timeout = db.Column(db.Integer, default=30, comment='单次请求超时(秒)')

    # Token tracking for token_balanced strategy (JSON: {model_id: cumulative_tokens})
    token_usage = db.Column(db.Text, comment='各模型累计token消耗(JSON)')

    # Round-robin index (for round_robin strategy)
    round_robin_index = db.Column(db.Integer, default=0, comment='轮询索引')

    description = db.Column(db.String(500), comment='策略描述')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_model_ids(self) -> list:
        if self.model_ids:
            try:
                return json.loads(self.model_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_model_ids(self, ids: list):
        self.model_ids = json.dumps(ids) if ids else None

    def get_token_usage(self) -> dict:
        if self.token_usage:
            try:
                return json.loads(self.token_usage)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_token_usage(self, usage: dict):
        self.token_usage = json.dumps(usage) if usage else None

    def record_token_usage(self, model_id: int, tokens: int):
        usage = self.get_token_usage()
        usage[str(model_id)] = usage.get(str(model_id), 0) + tokens
        self.set_token_usage(usage)

    def get_next_round_robin_index(self, total_models: int) -> int:
        if total_models <= 0:
            return 0
        idx = self.round_robin_index % total_models
        self.round_robin_index = idx + 1
        return idx

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'strategy_type': self.strategy_type,
            'model_ids': self.get_model_ids(),
            'is_active': self.is_active,
            'failover_enabled': self.failover_enabled,
            'failover_max_retries': self.failover_max_retries,
            'failover_timeout': self.failover_timeout,
            'token_usage': self.get_token_usage(),
            'round_robin_index': self.round_robin_index,
            'description': self.description,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }

    def __repr__(self):
        return f'<AiStrategy {self.name} ({self.strategy_type})>'
