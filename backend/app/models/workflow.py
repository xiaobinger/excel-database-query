import json
from datetime import datetime

from app import db
from app.utils.helpers import beijing_isoformat


class Workflow(db.Model):
    """混合工作流定义

    graph 存储画布结构：{"nodes": [...], "edges": [...], "viewport": {...}}
    variables 存储流程级变量定义，运行时注入上下文。
    """
    __tablename__ = 'workflows'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='工作流名称')
    description = db.Column(db.String(500), comment='工作流描述')
    graph = db.Column(db.Text, comment='画布结构(JSON)')
    variables = db.Column(db.Text, comment='流程变量(JSON list)')
    is_enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建用户ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')

    def get_graph(self) -> dict:
        if self.graph:
            try:
                data = json.loads(self.graph)
                if isinstance(data, dict):
                    data.setdefault('nodes', [])
                    data.setdefault('edges', [])
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
        return {'nodes': [], 'edges': []}

    def set_graph(self, graph: dict):
        self.graph = json.dumps(graph, ensure_ascii=False) if graph else None

    def get_variables(self) -> list:
        if self.variables:
            try:
                return json.loads(self.variables)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_variables(self, variables: list):
        self.variables = json.dumps(variables, ensure_ascii=False) if variables else None

    def to_dict(self, with_graph: bool = True) -> dict:
        graph = self.get_graph()
        d = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'variables': self.get_variables(),
            'is_enabled': self.is_enabled,
            'created_by': self.created_by,
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
            'node_count': len(graph.get('nodes', [])),
        }
        if with_graph:
            d['graph'] = graph
        return d

    def __repr__(self):
        return f'<Workflow {self.name}>'


class WorkflowRun(db.Model):
    """工作流执行实例"""
    __tablename__ = 'workflow_runs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_id = db.Column(db.String(64), nullable=False, unique=True, comment='执行ID')
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflows.id'), comment='工作流ID')
    workflow_name = db.Column(db.String(100), comment='工作流名称快照')

    status = db.Column(db.String(30), default='pending',
                       comment='pending/running/waiting_approval/completed/failed/cancelled')
    inputs = db.Column(db.Text, comment='启动输入(JSON dict)')
    context = db.Column(db.Text, comment='运行上下文(JSON dict)')
    logs = db.Column(db.Text, comment='执行日志(JSON list)')
    current_node_id = db.Column(db.String(64), comment='下一个待执行节点ID')
    pending_approval = db.Column(db.Text, comment='待审批信息(JSON)')

    error_message = db.Column(db.Text, comment='错误信息')
    started_at = db.Column(db.DateTime, comment='开始时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='发起用户ID')

    def get_inputs(self) -> dict:
        return _loads_dict(self.inputs)

    def set_inputs(self, data: dict):
        self.inputs = json.dumps(data, ensure_ascii=False) if data else None

    def get_context(self) -> dict:
        return _loads_dict(self.context)

    def set_context(self, ctx: dict):
        self.context = json.dumps(ctx, ensure_ascii=False, default=str) if ctx else None

    def get_pending_approval(self) -> dict:
        return _loads_dict(self.pending_approval)

    def set_pending_approval(self, data: dict):
        self.pending_approval = json.dumps(data, ensure_ascii=False) if data else None

    def get_logs(self) -> list:
        if self.logs:
            try:
                data = json.loads(self.logs)
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def add_log(self, message: str, level: str = 'info'):
        logs = self.get_logs()
        logs.append({
            'time': beijing_isoformat(datetime.utcnow()),
            'level': level,
            'message': message,
        })
        self.logs = json.dumps(logs[-500:], ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'run_id': self.run_id,
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'status': self.status,
            'inputs': self.get_inputs(),
            'context': self.get_context(),
            'logs': self.get_logs(),
            'current_node_id': self.current_node_id,
            'pending_approval': self.get_pending_approval(),
            'error_message': self.error_message,
            'started_at': beijing_isoformat(self.started_at),
            'completed_at': beijing_isoformat(self.completed_at),
            'created_at': beijing_isoformat(self.created_at),
            'created_by': self.created_by,
        }

    def __repr__(self):
        return f'<WorkflowRun {self.run_id}>'


class WorkflowRunNode(db.Model):
    """工作流节点执行记录"""
    __tablename__ = 'workflow_run_nodes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_id = db.Column(db.String(64), db.ForeignKey('workflow_runs.run_id'), index=True, comment='执行ID')
    node_id = db.Column(db.String(64), comment='节点ID')
    node_name = db.Column(db.String(200), comment='节点名称')
    node_type = db.Column(db.String(30), comment='节点类型')

    status = db.Column(db.String(30), default='running',
                       comment='running/waiting_approval/completed/failed/skipped')
    output = db.Column(db.Text, comment='节点输出(JSON)')
    error_message = db.Column(db.Text, comment='错误信息')

    started_at = db.Column(db.DateTime, comment='开始时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')

    def get_output(self):
        if self.output:
            try:
                return json.loads(self.output)
            except (json.JSONDecodeError, TypeError):
                return self.output
        return None

    def set_output(self, data):
        try:
            self.output = json.dumps(data, ensure_ascii=False, default=str) if data is not None else None
        except (TypeError, ValueError):
            self.output = json.dumps(str(data), ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'run_id': self.run_id,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'node_type': self.node_type,
            'status': self.status,
            'output': self.get_output(),
            'error_message': self.error_message,
            'started_at': beijing_isoformat(self.started_at),
            'completed_at': beijing_isoformat(self.completed_at),
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<WorkflowRunNode {self.run_id}:{self.node_id}>'


def _loads_dict(raw):
    if raw:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}