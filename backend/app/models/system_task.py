import json
import uuid
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class SystemTask(db.Model):
    __tablename__ = 'system_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='任务名称')
    description = db.Column(db.String(500), comment='描述')
    task_type = db.Column(db.String(20), default='sql', comment='任务类型: sql/api/script')

    # SQL related
    script_id = db.Column(db.Integer, db.ForeignKey('scripts.id'), comment='关联脚本')
    database_connection_id = db.Column(db.Integer, db.ForeignKey('database_connections.id'), comment='关联数据库')
    database_ids = db.Column(db.Text, comment='关联数据库ID列表(JSON)')

    # API related
    api_method = db.Column(db.String(10), default='POST', comment='请求方式: GET/POST/PUT/DELETE')
    api_url = db.Column(db.String(500), comment='API地址')
    api_headers = db.Column(db.Text, comment='请求头(JSON)')
    api_body = db.Column(db.Text, comment='请求体模板(JSON或字符串)')
    api_timeout = db.Column(db.Integer, default=30, comment='API超时时间(秒)')

    # Local script related
    script_type = db.Column(db.String(20), comment='本地脚本类型: python/shell/bat/powershell等')
    script_path = db.Column(db.String(500), comment='本地脚本路径')
    script_timeout = db.Column(db.Integer, default=60, comment='脚本执行超时时间(秒)')
    script_env = db.Column(db.Text, comment='脚本环境变量(JSON)')

    # Common params config (placeholder definitions)
    params_config = db.Column(db.Text, comment='参数配置(JSON)')

    # Response field mapping (for API tasks)
    response_mapping = db.Column(db.Text, comment='响应字段意义映射(JSON)，格式: [{"field":"status","label":"状态","mapping":{"0":"失败","1":"成功"}}]')

    # Signing
    sign_enabled = db.Column(db.Boolean, default=False, comment='是否启用加签')
    sign_key = db.Column(db.String(500), comment='加签密钥')
    sign_method = db.Column(db.String(50), default='md5', comment='加签方法: md5/sha256/hmac_sha256')
    sign_param_name = db.Column(db.String(100), default='sign', comment='签名字段名')
    sign_append_type = db.Column(db.String(20), default='query', comment='签名附加方式: query/body/header')

    is_enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

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

    def get_api_headers(self) -> dict:
        if self.api_headers:
            try:
                return json.loads(self.api_headers)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_api_headers(self, headers: dict):
        self.api_headers = json.dumps(headers, ensure_ascii=False) if headers else None

    def get_params_config(self) -> list:
        if self.params_config:
            try:
                return json.loads(self.params_config)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_params_config(self, config: list):
        self.params_config = json.dumps(config, ensure_ascii=False) if config else None

    def get_response_mapping(self) -> list:
        if self.response_mapping:
            try:
                return json.loads(self.response_mapping)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_response_mapping(self, mapping: list):
        self.response_mapping = json.dumps(mapping, ensure_ascii=False) if mapping else None

    def get_script_env(self) -> dict:
        if self.script_env:
            try:
                return json.loads(self.script_env)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_script_env(self, env: dict):
        self.script_env = json.dumps(env, ensure_ascii=False) if env else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'task_type': self.task_type,
            'script_id': self.script_id,
            'database_connection_id': self.database_connection_id,
            'database_ids': self.get_database_ids(),
            'api_method': self.api_method,
            'api_url': self.api_url,
            'api_headers': self.get_api_headers(),
            'api_body': self.api_body,
            'api_timeout': self.api_timeout,
            'script_type': self.script_type,
            'script_path': self.script_path,
            'script_timeout': self.script_timeout,
            'script_env': self.get_script_env(),
            'params_config': self.get_params_config(),
            'response_mapping': self.get_response_mapping(),
            'sign_enabled': self.sign_enabled,
            'sign_key': self.sign_key,
            'sign_method': self.sign_method,
            'sign_param_name': self.sign_param_name,
            'sign_append_type': self.sign_append_type,
            'is_enabled': self.is_enabled,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }

    def __repr__(self):
        return f'<SystemTask {self.name}>'


class SystemTaskExecution(db.Model):
    __tablename__ = 'system_task_executions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    execution_id = db.Column(db.String(64), nullable=False, unique=True, comment='执行ID')
    system_task_id = db.Column(db.Integer, db.ForeignKey('system_tasks.id'), comment='关联系统任务')
    status = db.Column(db.String(20), default='pending', comment='状态: pending/running/completed/failed/cancelled')
    task_type = db.Column(db.String(20), comment='任务类型: sql/api')
    params_values = db.Column(db.Text, comment='执行参数值(JSON)')
    result_data = db.Column(db.Text, comment='执行结果(JSON)')
    logs = db.Column(db.Text, comment='执行日志(JSON)')
    progress = db.Column(db.Integer, default=0, comment='执行进度(0-100)')
    error_message = db.Column(db.Text, comment='错误信息')
    started_at = db.Column(db.DateTime, comment='开始时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')

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
            'time': beijing_isoformat(datetime.utcnow()),
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

    def get_result_data(self) -> dict:
        if self.result_data:
            try:
                return json.loads(self.result_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_result_data(self, data: dict):
        self.result_data = json.dumps(data, ensure_ascii=False) if data else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'execution_id': self.execution_id,
            'system_task_id': self.system_task_id,
            'status': self.status,
            'task_type': self.task_type,
            'params_values': self.get_params_values(),
            'result_data': self.get_result_data(),
            'logs': self.get_logs(),
            'progress': self.progress,
            'error_message': self.error_message,
            'started_at': beijing_isoformat(self.started_at),
            'completed_at': beijing_isoformat(self.completed_at),
            'created_at': beijing_isoformat(self.created_at),
            'created_by': self.created_by,
        }

    def __repr__(self):
        return f'<SystemTaskExecution {self.execution_id}>'
