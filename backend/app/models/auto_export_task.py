import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class AutoExportTask(db.Model):
    __tablename__ = 'auto_export_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='任务名称')
    description = db.Column(db.String(500), comment='描述')
    script_ids = db.Column(db.Text, nullable=False, comment='关联导出选项ID列表(JSON)')
    cron_expression = db.Column(db.String(100), nullable=False, comment='Cron表达式')
    output_format = db.Column(db.String(20), default='sheets', comment='导出格式: sheets/zip')
    auto_params = db.Column(db.Text, comment='自动参数配置(JSON)')
    is_enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    last_run_at = db.Column(db.DateTime, comment='上次执行时间')
    last_run_status = db.Column(db.String(20), comment='上次执行状态')
    last_task_id = db.Column(db.String(64), comment='上次执行的任务ID')
    next_run_at = db.Column(db.DateTime, comment='下次预计执行时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    notify_enabled = db.Column(db.Boolean, default=False, comment='是否启用通知')
    notify_emails = db.Column(db.Text, comment='通知邮箱列表(JSON数组)')
    notify_attach_file = db.Column(db.Boolean, default=False, comment='是否附件发送结果文件')

    def get_script_ids(self) -> list:
        if self.script_ids:
            try:
                return json.loads(self.script_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_script_ids(self, ids: list):
        self.script_ids = json.dumps(ids) if ids else None

    def get_auto_params(self) -> dict:
        if self.auto_params:
            try:
                return json.loads(self.auto_params)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_auto_params(self, params: dict):
        self.auto_params = json.dumps(params, ensure_ascii=False) if params else None

    def get_notify_emails(self) -> list:
        if self.notify_emails:
            try:
                return json.loads(self.notify_emails)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_notify_emails(self, emails: list):
        self.notify_emails = json.dumps(emails, ensure_ascii=False) if emails else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'script_ids': self.get_script_ids(),
            'cron_expression': self.cron_expression,
            'output_format': self.output_format,
            'auto_params': self.get_auto_params(),
            'is_enabled': self.is_enabled,
            'last_run_at': beijing_isoformat(self.last_run_at),
            'last_run_status': self.last_run_status,
            'last_task_id': self.last_task_id,
            'next_run_at': beijing_isoformat(self.next_run_at),
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
            'notify_enabled': self.notify_enabled,
            'notify_emails': self.get_notify_emails(),
            'notify_attach_file': self.notify_attach_file,
        }
