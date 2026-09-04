import json
import uuid
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class PayFlowNotifyTemplate(db.Model):
    """代付流程通知模板

    统一维护节点通知的标题、正文、Webhook、接收人等配置，
    在流程编排时通过 ID 引用，避免每个节点重复配置。
    """
    __tablename__ = 'pay_flow_notify_templates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='模板名称')
    description = db.Column(db.String(500), comment='模板描述')

    # 通知内容
    title = db.Column(db.String(255), comment='通知标题')
    content = db.Column(db.Text, comment='通知正文模板')
    webhook_url = db.Column(db.String(500), comment='Webhook 地址')
    receivers = db.Column(db.String(500), comment='接收人(逗号分隔)')

    is_enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'title': self.title,
            'content': self.content,
            'webhook_url': self.webhook_url,
            'receivers': self.receivers,
            'is_enabled': self.is_enabled,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }


class PayFlowTemplate(db.Model):
    """代付流程模板

    定义节点的有序列表、每个节点的代付动作/通知配置、
    定时循环配置、流转条件，供每笔数据（Excel 每一行）独立执行。
    """
    __tablename__ = 'pay_flow_templates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='流程名称')
    description = db.Column(db.String(500), comment='流程描述')

    # 节点定义（JSON 列表），每个节点结构见 pay_flow_service.NODE_KEYS
    nodes = db.Column(db.Text, comment='节点定义(JSON列表)')

    is_enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def get_nodes(self) -> list:
        if self.nodes:
            try:
                return json.loads(self.nodes)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_nodes(self, nodes: list):
        self.nodes = json.dumps(nodes, ensure_ascii=False) if nodes else None

    def to_dict(self, with_nodes=True) -> dict:
        d = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_enabled': self.is_enabled,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
        if with_nodes:
            d['nodes'] = self.get_nodes()
        return d

    def __repr__(self):
        return f'<PayFlowTemplate {self.name}>'


class PayFlowExecution(db.Model):
    """代付流程执行实例

    每笔数据（Excel 每一行）对应一个独立实例，按模板节点序列流转。
    batch_id 用于聚合一次「发起代付流程」产生的所有实例。
    """
    __tablename__ = 'pay_flow_executions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    execution_id = db.Column(db.String(64), nullable=False, unique=True, comment='流程实例ID')
    template_id = db.Column(db.Integer, db.ForeignKey('pay_flow_templates.id'), comment='流程模板ID')
    template_name = db.Column(db.String(100), comment='流程名称快照')
    batch_id = db.Column(db.String(64), index=True, comment='批次ID(一次发起流程)')

    # 单笔数据
    row_index = db.Column(db.Integer, default=0, comment='所在 Excel 行序号(1-based)')
    row_data = db.Column(db.Text, comment='该行数据(JSON list)')

    # 执行状态
    status = db.Column(db.String(20), default='pending', comment='pending/running/waiting/completed/failed/cancelled')
    current_node_index = db.Column(db.Integer, default=0, comment='当前待执行节点索引')
    next_run_at = db.Column(db.DateTime, comment='下次推进时间(循环间隔用)')
    loop_node_id = db.Column(db.String(64), comment='当前循环中的节点ID')
    loop_count = db.Column(db.Integer, default=0, comment='当前节点已循环次数')
    last_dispatched_at = db.Column(db.DateTime, comment='调度器最后分发时间(防重入)')

    # 汇总通知配置（发起流程时设置，批次内所有实例共享）
    summary_notify_enabled = db.Column(db.Boolean, default=False, comment='是否启用汇总通知')
    summary_notify_template_id = db.Column(db.Integer, db.ForeignKey('pay_flow_notify_templates.id'), comment='汇总通知模板ID')
    summary_notify_sent = db.Column(db.Boolean, default=False, comment='汇总通知是否已发送')

    # 上下文（累积字段，供流转条件判断）
    context = db.Column(db.Text, comment='执行上下文字段(JSON dict)')

    result_message = db.Column(db.Text, comment='最终结果摘要')
    error_message = db.Column(db.Text, comment='错误信息')

    started_at = db.Column(db.DateTime, comment='开始时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='发起用户ID')

    def get_row_data(self) -> list:
        if self.row_data:
            try:
                return json.loads(self.row_data)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_row_data(self, row: list):
        self.row_data = json.dumps(row, ensure_ascii=False) if row else None

    def get_context(self) -> dict:
        if self.context:
            try:
                return json.loads(self.context)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_context(self, ctx: dict):
        self.context = json.dumps(ctx, ensure_ascii=False) if ctx else None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'execution_id': self.execution_id,
            'template_id': self.template_id,
            'template_name': self.template_name,
            'batch_id': self.batch_id,
            'row_index': self.row_index,
            'row_data': self.get_row_data(),
            'status': self.status,
            'current_node_index': self.current_node_index,
            'next_run_at': beijing_isoformat(self.next_run_at),
            'loop_node_id': self.loop_node_id,
            'loop_count': self.loop_count,
            'summary_notify_enabled': self.summary_notify_enabled,
            'summary_notify_template_id': self.summary_notify_template_id,
            'summary_notify_sent': self.summary_notify_sent,
            'context': self.get_context(),
            'result_message': self.result_message,
            'error_message': self.error_message,
            'started_at': beijing_isoformat(self.started_at),
            'completed_at': beijing_isoformat(self.completed_at),
            'created_at': beijing_isoformat(self.created_at),
            'created_by': self.created_by,
        }

    def __repr__(self):
        return f'<PayFlowExecution {self.execution_id}>'


class PayFlowNodeExecution(db.Model):
    """流程节点执行记录

    记录每个实例每个节点的每次尝试（含循环重试）的结构化结果与日志。
    """
    __tablename__ = 'pay_flow_node_executions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    execution_id = db.Column(db.String(64), db.ForeignKey('pay_flow_executions.execution_id'),
                             index=True, comment='流程实例ID')
    node_id = db.Column(db.String(64), comment='节点ID')
    node_name = db.Column(db.String(200), comment='节点名称')
    node_type = db.Column(db.String(20), comment='节点类型: pay/notify')
    attempt = db.Column(db.Integer, default=1, comment='第几次尝试(循环重试)')

    status = db.Column(db.String(20), default='pending', comment='pending/running/completed/failed')
    result_fields = db.Column(db.Text, comment='节点返回字段(JSON dict)')
    logs = db.Column(db.Text, comment='节点日志(JSON list)')
    error_message = db.Column(db.Text, comment='错误/失败原因')

    started_at = db.Column(db.DateTime, comment='开始时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')

    def get_result_fields(self) -> dict:
        if self.result_fields:
            try:
                return json.loads(self.result_fields)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_result_fields(self, fields: dict):
        self.result_fields = json.dumps(fields, ensure_ascii=False) if fields else None

    def get_logs(self) -> list:
        if self.logs:
            try:
                return json.loads(self.logs)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def add_log(self, message: str, level: str = 'info'):
        current = self.get_logs()
        current.append({
            'time': beijing_isoformat(datetime.utcnow()),
            'level': level,
            'message': message,
        })
        self.logs = json.dumps(current, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'execution_id': self.execution_id,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'node_type': self.node_type,
            'attempt': self.attempt,
            'status': self.status,
            'result_fields': self.get_result_fields(),
            'logs': self.get_logs(),
            'error_message': self.error_message,
            'started_at': beijing_isoformat(self.started_at),
            'completed_at': beijing_isoformat(self.completed_at),
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<PayFlowNodeExecution {self.execution_id}:{self.node_name}#{self.attempt}>'