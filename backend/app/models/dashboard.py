import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class DashboardQuickQuery(db.Model):
    """运营数据看板-快捷查询（保存查询条件与图表配置）

    看板脚本已统一到 scripts 表（type='dashboard'），由脚本管理页维护，
    本模块只保留快捷查询。旧的 dashboard_scripts 表由启动迁移函数
    （raw SQL）一次性搬入 scripts 表后不再维护。
    """
    __tablename__ = 'dashboard_quick_queries'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    script_name = db.Column(db.String(100), default='')
    conn_name = db.Column(db.String(200), default='')
    merge_names = db.Column(db.Text)
    merge_mode = db.Column(db.String(20), default='separate')
    merge_key = db.Column(db.String(200), default='')
    hide_fields = db.Column(db.Text)
    dimension = db.Column(db.String(20), default='day')
    dp_year = db.Column(db.Integer)
    dp_month = db.Column(db.Integer)
    dp_year_start = db.Column(db.Integer)
    dp_year_end = db.Column(db.Integer)
    # 自定义时间范围（dimension='custom' 时使用）
    dp_start_date = db.Column(db.String(10))
    dp_end_date = db.Column(db.String(10))
    custom_params = db.Column(db.Text)
    layout_count = db.Column(db.Integer, default=1)
    chart_configs = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def _load_json(self, field, default):
        try:
            return json.loads(field) if field else default
        except (json.JSONDecodeError, TypeError):
            return default

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'script_name': self.script_name or '',
            'conn_name': self.conn_name or '',
            'merge_names': self._load_json(self.merge_names, []),
            'merge_mode': self.merge_mode or 'separate',
            'merge_key': self.merge_key or '',
            'hide_fields': self._load_json(self.hide_fields, []),
            'dimension': self.dimension or 'day',
            'dp_year': self.dp_year,
            'dp_month': self.dp_month,
            'dp_year_start': self.dp_year_start,
            'dp_year_end': self.dp_year_end,
            'dp_start_date': self.dp_start_date or '',
            'dp_end_date': self.dp_end_date or '',
            'custom_params': self._load_json(self.custom_params, {}),
            'layout_count': self.layout_count or 1,
            'chart_configs': self._load_json(self.chart_configs, []),
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
