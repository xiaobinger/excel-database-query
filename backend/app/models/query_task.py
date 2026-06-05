import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat, format_beijing


class QueryTask(db.Model):
    __tablename__ = 'query_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.String(64), nullable=False, unique=True, comment='任务ID')
    status = db.Column(db.String(20), default='pending', comment='状态: pending/running/completed/failed/cancelled')
    script_id = db.Column(db.Integer, db.ForeignKey('scripts.id'), comment='关联脚本')
    database_connection_id = db.Column(db.Integer, db.ForeignKey('database_connections.id'), comment='关联数据库连接')
    database_ids = db.Column(db.Text, comment='关联数据库ID列表(JSON)')
    input_file = db.Column(db.String(500), comment='输入文件路径')
    output_file = db.Column(db.String(500), comment='输出文件路径')
    total_rows = db.Column(db.Integer, default=0, comment='总行数')
    success_count = db.Column(db.Integer, default=0, comment='成功行数')
    failure_count = db.Column(db.Integer, default=0, comment='失败行数')
    progress = db.Column(db.Integer, default=0, comment='执行进度(0-100)')
    logs = db.Column(db.Text, comment='执行日志(JSON)')
    merge_strategy = db.Column(db.String(20), default='concat', comment='结果合并策略')
    error_message = db.Column(db.Text, comment='错误信息')
    started_at = db.Column(db.DateTime, comment='开始时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')
    type = db.Column(db.String(20), default='query', comment='任务类型: query/export')
    params_values = db.Column(db.Text, comment='导出参数值(JSON)')
    output_format = db.Column(db.String(20), default='sheets', comment='导出格式: sheets/zip')
    script_ids_json = db.Column(db.Text, comment='关联脚本ID列表(JSON)')
    is_auto = db.Column(db.Boolean, default=False, comment='是否自动执行任务')
    auto_task_id = db.Column(db.Integer, db.ForeignKey('auto_export_tasks.id'), comment='关联自动任务ID')

    def get_database_ids(self) -> list:
        if self.database_ids:
            try:
                return json.loads(self.database_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        if self.database_connection_id:
            return [self.database_connection_id]
        return []

    def set_database_ids(self, ids: list):
        self.database_ids = json.dumps(ids) if ids else None

    def get_logs(self) -> list:
        if self.logs:
            try:
                return json.loads(self.logs)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def add_log(self, message: str, level: str = 'info'):
        current_logs = self.get_logs()
        current_logs.append({
            'time': format_beijing(datetime.utcnow()),
            'level': level,
            'message': message
        })
        self.logs = json.dumps(current_logs, ensure_ascii=False)

    def get_params_values(self) -> dict:
        if self.params_values:
            try:
                return json.loads(self.params_values)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_params_values(self, values: dict):
        self.params_values = json.dumps(values, ensure_ascii=False) if values else None

    def get_script_ids_json(self) -> list:
        if self.script_ids_json:
            try:
                return json.loads(self.script_ids_json)
            except (json.JSONDecodeError, TypeError):
                return []
        if self.script_id:
            return [self.script_id]
        return []

    def set_script_ids_json(self, ids: list):
        self.script_ids_json = json.dumps(ids) if ids else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'task_id': self.task_id,
            'status': self.status,
            'script_id': self.script_id,
            'database_connection_id': self.database_connection_id,
            'database_ids': self.get_database_ids(),
            'input_file': self.input_file,
            'output_file': self.output_file,
            'total_rows': self.total_rows,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'progress': self.progress,
            'logs': self.get_logs(),
            'merge_strategy': self.merge_strategy,
            'error_message': self.error_message,
            'started_at': beijing_isoformat(self.started_at),
            'completed_at': beijing_isoformat(self.completed_at),
            'created_at': beijing_isoformat(self.created_at),
            'created_by': self.created_by,
            'type': self.type,
            'params_values': self.get_params_values(),
            'output_format': self.output_format,
            'script_ids': self.get_script_ids_json(),
            'is_auto': self.is_auto,
            'auto_task_id': self.auto_task_id,
        }

    def __repr__(self):
        return f'<QueryTask {self.task_id}>'
