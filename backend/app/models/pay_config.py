import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class PayConfig(db.Model):
    """代付提现渠道配置

    每个渠道（合利宝/电银/乐商通PLUS/快乐刷）各一条记录，
    pro_config / test_config 分别存储生产、测试环境的 JSON 配置。
    """
    __tablename__ = 'pay_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    channel = db.Column(db.String(50), nullable=False, unique=True, comment='渠道标识: helipay/dianyin/lepass/kls')
    name = db.Column(db.String(100), nullable=False, comment='渠道名称')
    description = db.Column(db.String(500), comment='渠道描述')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    sort_order = db.Column(db.Integer, default=0, comment='排序')

    # 各环境配置（JSON 字符串）
    pro_config = db.Column(db.Text, comment='生产环境配置(JSON)')
    test_config = db.Column(db.Text, comment='测试环境配置(JSON)')

    # 渠道参数（用于代付请求的固定参数）
    online_bank_type = db.Column(db.String(10), default='B2C', comment='转账类型 B2C对私/B2B对公')
    bank_code = db.Column(db.String(10), default='CCB', comment='银行编码')
    transfer_mode = db.Column(db.String(10), comment='代付模式(乐商通/快乐刷: 6/7)')
    busi_type = db.Column(db.String(10), default='144', comment='跑批业务类型(快乐刷)')
    channel_code = db.Column(db.String(20), comment='子代理查询渠道码(kls/lepass)')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_pro_config(self):
        if self.pro_config:
            try:
                return json.loads(self.pro_config)
            except Exception:
                return {}
        return {}

    def set_pro_config(self, cfg):
        self.pro_config = json.dumps(cfg, ensure_ascii=False) if cfg else None

    def get_test_config(self):
        if self.test_config:
            try:
                return json.loads(self.test_config)
            except Exception:
                return {}
        return {}

    def set_test_config(self, cfg):
        self.test_config = json.dumps(cfg, ensure_ascii=False) if cfg else None

    def to_dict(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'pro_config': self.get_pro_config(),
            'test_config': self.get_test_config(),
            'online_bank_type': self.online_bank_type,
            'bank_code': self.bank_code,
            'transfer_mode': self.transfer_mode,
            'busi_type': self.busi_type,
            'channel_code': self.channel_code,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
