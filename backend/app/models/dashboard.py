import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class DashboardScript(db.Model):
    """运营数据看板-查询脚本（SQL模板，支持{{参数}}占位符）"""
    __tablename__ = 'dashboard_scripts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    sql_text = db.Column(db.Text, nullable=False)
    chart_type = db.Column(db.String(20), default='line')
    conn_name = db.Column(db.String(200), default='')
    merge_conn_names = db.Column(db.Text)
    description = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_merge_conn_names(self) -> list:
        try:
            return json.loads(self.merge_conn_names) if self.merge_conn_names else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_merge_conn_names(self, names):
        self.merge_conn_names = json.dumps(names or [], ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'sql': self.sql_text,
            'chart_type': self.chart_type or 'line',
            'conn_name': self.conn_name or '',
            'merge_conn_names': self.get_merge_conn_names(),
            'description': self.description or '',
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }


class DashboardQuickQuery(db.Model):
    """运营数据看板-快捷查询（保存查询条件与图表配置）"""
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
            'custom_params': self._load_json(self.custom_params, {}),
            'layout_count': self.layout_count or 1,
            'chart_configs': self._load_json(self.chart_configs, []),
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
