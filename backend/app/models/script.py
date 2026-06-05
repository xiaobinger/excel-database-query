import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class Script(db.Model):
    __tablename__ = 'scripts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='脚本名称')
    description = db.Column(db.String(500), comment='脚本描述')
    sql_text = db.Column(db.Text, nullable=False, comment='SQL语句')
    tag = db.Column(db.String(100), comment='标签')
    result_sheet_name = db.Column(db.String(100), default='查询结果', comment='结果工作表名')
    batch_size = db.Column(db.Integer, default=100, comment='批处理大小')
    timeout = db.Column(db.Integer, default=30, comment='超时时间(秒)')
    query_mode = db.Column(db.String(20), default='batch', comment='查询模式: batch/in')
    param_column = db.Column(db.String(100), comment='参数列名')
    database_connection_id = db.Column(db.Integer, db.ForeignKey('database_connections.id'), nullable=True, comment='默认数据库连接')
    database_ids = db.Column(db.Text, comment='关联数据库ID列表(JSON)')
    merge_strategy = db.Column(db.String(20), default='concat', comment='结果合并策略: concat/separate')
    column_mapping = db.Column(db.Text, comment='列映射配置(JSON)')
    new_sheet = db.Column(db.Boolean, default=True, comment='是否新建工作表')
    primary_key = db.Column(db.String(100), comment='主键字段(不新建工作表时使用)')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    type = db.Column(db.String(20), default='query', comment='类型: query/export')
    params_config = db.Column(db.Text, comment='导出参数配置(JSON)')
    sql_template = db.Column(db.Text, comment='SQL模板(Jinja2语法,启用模板时使用)')
    template_config = db.Column(db.Text, comment='模板变量配置(JSON)')
    is_template = db.Column(db.Boolean, default=False, comment='是否启用SQL模板')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def get_database_ids(self) -> list:
        if self.database_ids:
            try:
                return json.loads(self.database_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        ids = []
        if self.database_connection_id:
            ids.append(self.database_connection_id)
        return ids

    def set_database_ids(self, ids: list):
        self.database_ids = json.dumps(ids) if ids else None

    def get_column_mapping(self) -> dict:
        if self.column_mapping:
            try:
                return json.loads(self.column_mapping)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_column_mapping(self, mapping: dict):
        self.column_mapping = json.dumps(mapping) if mapping else None

    def get_params_config(self) -> list:
        if self.params_config:
            try:
                return json.loads(self.params_config)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_params_config(self, config: list):
        self.params_config = json.dumps(config, ensure_ascii=False) if config else None

    def get_template_config(self) -> list:
        if self.template_config:
            try:
                return json.loads(self.template_config)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_template_config(self, config: list):
        self.template_config = json.dumps(config, ensure_ascii=False) if config else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'sql_text': self.sql_text,
            'tag': self.tag,
            'result_sheet_name': self.result_sheet_name,
            'batch_size': self.batch_size,
            'timeout': self.timeout,
            'query_mode': self.query_mode,
            'param_column': self.param_column,
            'database_connection_id': self.database_connection_id,
            'database_ids': self.get_database_ids(),
            'merge_strategy': self.merge_strategy,
            'column_mapping': self.get_column_mapping(),
            'new_sheet': self.new_sheet,
            'primary_key': self.primary_key,
            'is_active': self.is_active,
            'type': self.type,
            'params_config': self.get_params_config(),
            'sql_template': self.sql_template,
            'template_config': self.get_template_config(),
            'is_template': self.is_template,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }

    def __repr__(self):
        return f'<Script {self.name}>'
