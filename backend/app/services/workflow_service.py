"""混合工作流服务

支持将查询任务、导出任务、系统任务、信息查询、邮件通知、日志查询、
文件生成、审批、条件判断、延时等能力编排为节点，通过共享上下文流转执行。

审批节点支持两种模式：
- manual：指定审批人，流程暂停为 waiting_approval，审批后恢复执行；
- ai：由 AI 督查员根据提示词与上下文自动判定 PASS / REJECT。
"""
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime

from flask import current_app

from app import db
from app.models.workflow import Workflow, WorkflowRun, WorkflowRunNode
from app.utils.helpers import beijing_isoformat

logger = logging.getLogger(__name__)

_active_runs = set()
_cancel_flags = set()
_lock = threading.Lock()

NODE_TYPE_LABELS = {
    'start': '开始',
    'query': '查询任务',
    'export': '导出任务',
    'system_task': '系统任务',
    'script': '脚本执行',
    'lookup': '信息查询',
    'email': '邮件通知',
    'log_query': '查询日志',
    'file_generate': '生成文件',
    'approval': '审批节点',
    'condition': '条件判断',
    'delay': '延时等待',
    'end': '结束',
}

# 支持自循环的业务任务节点（开始/结束/条件/延时/审批等控制类节点除外）
LOOPABLE_NODE_TYPES = {
    'query', 'export', 'system_task', 'script', 'lookup', 'email', 'log_query', 'file_generate',
}

_TEMPLATE_RE = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')
_NUMBER_RE = re.compile(r'^-?\d+(\.\d+)?$')

# 脚本节点支持的预置脚本类型 -> 解释器命令前缀
_SCRIPT_INTERPRETERS = {
    'python': [sys.executable or 'python'],
    'shell': ['bash'],
    'bash': ['bash'],
    'sh': ['bash'],
    'bat': ['cmd', '/c'],
    'cmd': ['cmd', '/c'],
    'powershell': ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File'],
    'ps1': ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File'],
    'node': ['node'],
    'javascript': ['node'],
    'js': ['node'],
}
# 内联脚本写入临时文件时使用的后缀
_SCRIPT_SUFFIXES = {
    'python': '.py',
    'shell': '.sh',
    'bash': '.sh',
    'sh': '.sh',
    'bat': '.bat',
    'cmd': '.bat',
    'powershell': '.ps1',
    'ps1': '.ps1',
    'node': '.js',
    'javascript': '.js',
    'js': '.js',
}


# ---------------------------------------------------------------------------
# 工作流 CRUD
# ---------------------------------------------------------------------------

def get_workflows(page=1, per_page=50, keyword=None):
    query = Workflow.query
    if keyword:
        query = query.filter(Workflow.name.contains(keyword))
    pagination = query.order_by(Workflow.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': [w.to_dict(with_graph=False) for w in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    }


def get_workflow(workflow_id):
    wf = Workflow.query.get(workflow_id)
    return wf.to_dict() if wf else None


def create_workflow(data, created_by=None):
    wf = Workflow(
        name=(data.get('name') or '未命名工作流').strip(),
        description=data.get('description') or '',
        is_enabled=data.get('is_enabled', True),
        created_by=created_by,
    )
    wf.set_graph(data.get('graph') or {'nodes': [], 'edges': []})
    wf.set_variables(data.get('variables') or [])
    db.session.add(wf)
    db.session.commit()
    return wf.to_dict()


def update_workflow(workflow_id, data):
    wf = Workflow.query.get(workflow_id)
    if not wf:
        return None
    if 'name' in data and data['name']:
        wf.name = data['name'].strip()
    if 'description' in data:
        wf.description = data['description']
    if 'is_enabled' in data:
        wf.is_enabled = bool(data['is_enabled'])
    if 'graph' in data:
        wf.set_graph(data['graph'])
    if 'variables' in data:
        wf.set_variables(data['variables'])
    db.session.commit()
    return wf.to_dict()


def delete_workflow(workflow_id):
    """物理删除工作流，并连带删除其全部执行记录与节点执行记录。

    存在待执行/执行中/待审批的运行时禁止删除，需先取消，避免后台线程
    写入已被删除的记录。
    """
    wf = Workflow.query.get(workflow_id)
    if not wf:
        return False

    active = WorkflowRun.query.filter(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.status.in_(('pending', 'running', 'waiting_approval')),
    ).first()
    if active:
        raise ValueError(f'工作流存在进行中的执行记录（{active.status}），请先取消运行后再删除')

    run_ids = [r.run_id for r in WorkflowRun.query.filter_by(workflow_id=workflow_id).all()]
    if run_ids:
        WorkflowRunNode.query.filter(WorkflowRunNode.run_id.in_(run_ids)).delete(synchronize_session=False)
        WorkflowRun.query.filter(WorkflowRun.workflow_id == workflow_id).delete(synchronize_session=False)

    db.session.delete(wf)
    db.session.commit()
    return True


def get_capabilities():
    """返回编排面板可用的各类资源清单"""
    from app.models.script import Script
    from app.models.database import DatabaseConnection
    from app.models.system_task import SystemTask
    from app.models.user import User

    scripts = []
    for s in Script.query.order_by(Script.tag, Script.priority.desc(), Script.id.desc()).all():
        scripts.append({
            'id': s.id,
            'name': s.name,
            'type': s.type,
            'tag': s.tag or '',
            'params_config': s.get_params_config(),
            'database_ids': s.get_database_ids(),
        })

    databases = [{'id': d.id, 'name': d.name, 'db_type': d.db_type}
                 for d in DatabaseConnection.query.order_by(DatabaseConnection.id).all()]
    system_tasks = [{'id': t.id, 'name': t.name, 'task_type': t.task_type}
                    for t in SystemTask.query.order_by(SystemTask.id.desc()).all()]
    approvers = [{'id': u.id, 'username': u.username, 'display_name': u.display_name or u.username}
                 for u in User.query.filter_by(is_active=True).order_by(User.id).all()]

    return {
        'scripts': scripts,
        'databases': databases,
        'system_tasks': system_tasks,
        'approvers': approvers,
        'node_types': [{'type': k, 'label': v} for k, v in NODE_TYPE_LABELS.items()],
    }


# ---------------------------------------------------------------------------
# 执行记录
# ---------------------------------------------------------------------------

def get_runs(page=1, per_page=20, workflow_id=None, status=None):
    query = WorkflowRun.query
    if workflow_id:
        query = query.filter_by(workflow_id=workflow_id)
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(WorkflowRun.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': [_run_brief(r) for r in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    }


def get_run_detail(run_id):
    run = WorkflowRun.query.filter_by(run_id=run_id).first()
    if not run:
        return None
    data = run.to_dict()
    nodes = WorkflowRunNode.query.filter_by(run_id=run_id).order_by(WorkflowRunNode.id).all()
    data['nodes'] = [n.to_dict() for n in nodes]
    workflow = Workflow.query.get(run.workflow_id) if run.workflow_id else None
    data['graph'] = workflow.get_graph() if workflow else {'nodes': [], 'edges': []}
    return data


def _run_brief(run):
    data = run.to_dict()
    data.pop('context', None)
    data.pop('logs', None)
    return data


# ---------------------------------------------------------------------------
# 启动 / 审批 / 取消
# ---------------------------------------------------------------------------

def start_run(workflow_id, inputs=None, created_by=None):
    wf = Workflow.query.get(workflow_id)
    if not wf:
        raise ValueError('工作流不存在')
    graph = wf.get_graph()
    nodes = graph.get('nodes') or []
    if not nodes:
        raise ValueError('工作流还没有节点，请先编排流程')

    start_node_id = _find_start_node_id(graph)
    if not start_node_id:
        raise ValueError('工作流缺少开始节点')

    ctx = {}
    for var in wf.get_variables():
        name = (var or {}).get('name')
        if name:
            ctx[name] = (var or {}).get('default')
    ctx['inputs'] = inputs or {}
    ctx['workflow'] = {'id': wf.id, 'name': wf.name}

    run = WorkflowRun(
        run_id=str(uuid.uuid4()),
        workflow_id=wf.id,
        workflow_name=wf.name,
        status='pending',
        current_node_id=start_node_id,
        created_by=created_by,
        started_at=datetime.utcnow(),
    )
    run.set_inputs(inputs or {})
    run.set_context(ctx)
    run.add_log('工作流已创建，等待执行')
    db.session.add(run)
    db.session.commit()

    _spawn_run(run.run_id)
    return run.to_dict()


def _spawn_run(run_id):
    thread = threading.Thread(target=_execute_run_thread, args=(run_id,), daemon=True)
    thread.start()


def approve_run(run_id, approved, comment='', approver_name='', approver_id=None):
    run = WorkflowRun.query.filter_by(run_id=run_id).first()
    if not run:
        return False, '执行记录不存在'
    if run.status != 'waiting_approval':
        return False, '当前流程不在待审批状态'

    pending = run.get_pending_approval()
    node_id = pending.get('node_id')
    if not node_id:
        return False, '待审批节点信息缺失'

    workflow = Workflow.query.get(run.workflow_id)
    graph = workflow.get_graph() if workflow else {'nodes': [], 'edges': []}

    node_exec = WorkflowRunNode.query.filter_by(
        run_id=run_id, node_id=node_id, status='waiting_approval'
    ).order_by(WorkflowRunNode.id.desc()).first()
    if not node_exec:
        return False, '待审批节点执行记录不存在'

    ctx = run.get_context() or {}
    ctx.setdefault('approvals', {})[node_id] = {
        'approved': bool(approved),
        'comment': comment or '',
        'approver': approver_name or '',
        'approver_id': approver_id,
        'time': beijing_isoformat(datetime.utcnow()),
    }
    run.set_context(ctx)

    node_exec.completed_at = datetime.utcnow()
    if approved:
        node_exec.status = 'completed'
        node_exec.set_output(ctx['approvals'][node_id])
        branch = 'approved'
    else:
        node_exec.status = 'completed'
        node_exec.set_output(ctx['approvals'][node_id])
        branch = 'rejected'

    next_id = _pick_edge(graph.get('edges') or [], node_id, branch, fallback=('fail',) if not approved else ())
    run.set_pending_approval(None)

    if branch == 'rejected' and not next_id:
        run.status = 'failed'
        run.error_message = f'审批被拒绝：{comment or "无说明"}'
        run.completed_at = datetime.utcnow()
        run.add_log(run.error_message, 'error')
        db.session.commit()
        return True, '审批已拒绝，流程结束'

    run.current_node_id = next_id
    run.status = 'running' if next_id else 'completed'
    if not next_id:
        run.completed_at = datetime.utcnow()
    run.add_log(f'审批{"通过" if approved else "拒绝"}（{approver_name or "审批人"}）：{comment or "无说明"}')
    db.session.commit()

    if next_id:
        _spawn_run(run_id)
    return True, '审批已提交'


def cancel_run(run_id):
    run = WorkflowRun.query.filter_by(run_id=run_id).first()
    if not run:
        return False, '执行记录不存在'
    if run.status not in ('pending', 'running', 'waiting_approval'):
        return False, '当前状态不可取消'

    _cancel_flags.add(run_id)
    pending = run.get_pending_approval()
    if pending.get('node_id'):
        node_exec = WorkflowRunNode.query.filter_by(
            run_id=run_id, node_id=pending['node_id'], status='waiting_approval'
        ).order_by(WorkflowRunNode.id.desc()).first()
        if node_exec:
            node_exec.status = 'skipped'
            node_exec.error_message = '流程已取消'
            node_exec.completed_at = datetime.utcnow()
    run.status = 'cancelled'
    run.completed_at = datetime.utcnow()
    run.set_pending_approval(None)
    run.add_log('流程已取消', 'warning')
    db.session.commit()
    return True, '已取消'


# ---------------------------------------------------------------------------
# 执行引擎
# ---------------------------------------------------------------------------

def _execute_run_thread(run_id):
    with _lock:
        if run_id in _active_runs:
            return
        _active_runs.add(run_id)
    try:
        try:
            from app import create_app
            app = create_app()
        except Exception:
            app = current_app._get_current_object()

        with app.app_context():
            _execute_run(run_id)
    except Exception as e:
        logger.error(f'工作流执行线程异常: {e}', exc_info=True)
        try:
            run = WorkflowRun.query.filter_by(run_id=run_id).first()
            if run:
                run.status = 'failed'
                run.error_message = str(e)
                run.completed_at = datetime.utcnow()
                run.add_log(f'执行异常: {e}', 'error')
                db.session.commit()
        except Exception:
            db.session.rollback()
    finally:
        with _lock:
            _active_runs.discard(run_id)


def _execute_run(run_id):
    run = WorkflowRun.query.filter_by(run_id=run_id).first()
    if not run:
        return
    workflow = Workflow.query.get(run.workflow_id)
    if not workflow:
        _fail_run(run, '工作流不存在')
        return

    graph = workflow.get_graph()
    nodes = {n.get('id'): n for n in (graph.get('nodes') or []) if n.get('id')}
    edges = graph.get('edges') or []
    ctx = run.get_context() or {}

    run.status = 'running'
    run.started_at = run.started_at or datetime.utcnow()
    run.add_log('开始执行工作流')
    db.session.commit()

    current_id = run.current_node_id or _find_start_node_id(graph)
    if not current_id:
        _fail_run(run, '找不到开始节点')
        return

    visited_steps = 0
    while current_id:
        if run_id in _cancel_flags:
            _cancel_flags.discard(run_id)
            return
        visited_steps += 1
        if visited_steps > 300:
            _fail_run(run, '节点执行次数超过上限，可能存在循环')
            return

        node = nodes.get(current_id)
        if not node:
            _fail_run(run, f'节点不存在: {current_id}')
            return

        node_type = node.get('type') or 'task'
        node_name = node.get('name') or NODE_TYPE_LABELS.get(node_type, node_type)

        node_exec = WorkflowRunNode(
            run_id=run_id,
            node_id=current_id,
            node_name=node_name,
            node_type=node_type,
            status='running',
            started_at=datetime.utcnow(),
        )
        db.session.add(node_exec)
        db.session.commit()
        run.current_node_id = current_id
        run.add_log(f'执行节点：{node_name}（{NODE_TYPE_LABELS.get(node_type, node_type)}）')
        db.session.commit()

        try:
            result = _execute_node(node, ctx, run_id)
        except Exception as e:
            logger.error(f'节点执行失败 {node_name}: {e}', exc_info=True)
            node_exec.status = 'failed'
            node_exec.error_message = str(e)
            node_exec.completed_at = datetime.utcnow()
            run.add_log(f'节点 {node_name} 执行失败：{e}', 'error')

            next_id = _pick_edge(edges, current_id, 'fail')
            if next_id:
                run.current_node_id = next_id
                db.session.commit()
                current_id = next_id
                continue
            _fail_run(run, f'节点「{node_name}」执行失败：{e}')
            return

        if result.get('pending'):
            node_exec.status = 'waiting_approval'
            db.session.commit()
            run.status = 'waiting_approval'
            run.set_pending_approval(result['approval'])
            run.current_node_id = _pick_edge(edges, current_id, 'approved', fallback=('default',))
            run.add_log(f'节点「{node_name}」等待审批：{result["approval"].get("message", "")}', 'warning')
            db.session.commit()
            return

        output = result.get('output')
        output_key = node.get('output_key') or current_id
        ctx[output_key] = output
        ctx.setdefault('nodes', {})[current_id] = output
        ctx['last'] = output
        run.set_context(ctx)
        node_exec.completed_at = datetime.utcnow()

        if result.get('error'):
            node_exec.status = 'failed'
            node_exec.error_message = result['error']
            node_exec.set_output(output)
            run.add_log(f'节点 {node_name} 失败：{result["error"]}', 'error')
            next_id = _pick_edge(edges, current_id, 'fail')
            if next_id:
                run.current_node_id = next_id
                db.session.commit()
                current_id = next_id
                continue
            _fail_run(run, f'节点「{node_name}」失败：{result["error"]}')
            return

        node_exec.status = 'completed'
        node_exec.set_output(output)
        run.add_log(f'节点 {node_name} 执行完成')

        # 业务任务节点自循环：未满足跳出条件且未达最大次数时重复执行本节点
        if node_type in LOOPABLE_NODE_TYPES:
            loop_cfg = (node.get('config') or {}).get('loop') or {}
            if loop_cfg.get('enabled'):
                loops = ctx.setdefault('loops', {})
                loop_count = int(loops.get(current_id) or 0) + 1
                loops[current_id] = loop_count
                try:
                    max_times = int(loop_cfg.get('max_times') or 3)
                except (TypeError, ValueError):
                    max_times = 3
                max_times = max(1, min(max_times, 100))

                exit_expr = (loop_cfg.get('exit_condition') or '').strip()
                exited = False
                if exit_expr:
                    try:
                        exited = bool(_eval_condition(exit_expr, ctx))
                    except Exception as e:
                        run.add_log(f'节点「{node_name}」循环跳出条件解析失败：{e}', 'warning')

                if exited or loop_count >= max_times:
                    reason = '满足跳出条件' if exited else f'达到最大循环次数 {max_times}'
                    run.add_log(f'节点「{node_name}」循环结束（已执行 {loop_count} 次，{reason}）')
                    run.set_context(ctx)
                else:
                    try:
                        interval = float(loop_cfg.get('interval') or 0)
                    except (TypeError, ValueError):
                        interval = 0
                    interval = max(0.0, min(interval, 60.0))
                    run.set_context(ctx)
                    run.add_log(f'节点「{node_name}」第 {loop_count} 次执行完成，未满足跳出条件，继续循环', 'warning')
                    db.session.commit()
                    if interval:
                        time.sleep(interval)
                    continue

        if node_type == 'end':
            run.status = 'completed'
            run.completed_at = datetime.utcnow()
            run.current_node_id = None
            run.add_log('工作流执行完成', 'success')
            db.session.commit()
            return

        branch = result.get('branch') or 'success'
        fallback = ('fail',) if branch == 'rejected' else ('default',)
        next_id = _pick_edge(edges, current_id, branch, fallback=fallback)
        if not next_id:
            if branch == 'rejected':
                _fail_run(run, f'节点「{node_name}」审批未通过')
                return
            # 没有后继节点视为流程结束
            run.status = 'completed'
            run.completed_at = datetime.utcnow()
            run.current_node_id = None
            run.add_log('没有后继节点，工作流结束', 'success')
            db.session.commit()
            return

        run.current_node_id = next_id
        db.session.commit()
        current_id = next_id


def _fail_run(run, message):
    run.status = 'failed'
    run.error_message = message
    run.completed_at = datetime.utcnow()
    run.add_log(message, 'error')
    db.session.commit()


def _find_start_node_id(graph):
    nodes = graph.get('nodes') or []
    for n in nodes:
        if n.get('type') == 'start':
            return n.get('id')
    return nodes[0].get('id') if nodes else None


def _pick_edge(edges, node_id, branch, fallback=('default',)):
    candidates = [e for e in edges if e.get('source') == node_id]
    if not candidates:
        return None
    for key in (branch,) + tuple(fallback) + ('default',):
        if not key:
            continue
        for e in candidates:
            edge_branch = e.get('branch') or 'default'
            if edge_branch == key:
                return e.get('target')
    # 没有分支标记的普通连线
    for e in candidates:
        if not e.get('branch'):
            return e.get('target')
    return None


# ---------------------------------------------------------------------------
# 节点执行
# ---------------------------------------------------------------------------

def _execute_node(node, ctx, run_id):
    node_type = node.get('type') or 'task'
    cfg = node.get('config') or {}

    if node_type == 'start':
        return {'output': {'inputs': ctx.get('inputs', {})}}

    if node_type == 'end':
        return {'output': {'message': _render(cfg.get('message') or '流程结束', ctx)}}

    if node_type == 'delay':
        seconds = cfg.get('seconds', 3)
        try:
            seconds = max(0, min(float(seconds), 300))
        except (TypeError, ValueError):
            seconds = 3
        time.sleep(seconds)
        return {'output': {'seconds': seconds}}

    if node_type == 'condition':
        cond = _eval_condition(cfg.get('expression'), ctx)
        return {'output': {'result': cond}, 'branch': 'true' if cond else 'false'}

    if node_type == 'approval':
        return _execute_approval(node, cfg, ctx)

    if node_type == 'query':
        return _execute_query_node(cfg, ctx)

    if node_type == 'export':
        return _execute_export_node(cfg, ctx)

    if node_type == 'system_task':
        return _execute_system_task_node(cfg, ctx)

    if node_type == 'script':
        return _execute_script_node(cfg, ctx)

    if node_type == 'lookup':
        return _execute_lookup_node(cfg, ctx)

    if node_type == 'email':
        return _execute_email_node(cfg, ctx)

    if node_type == 'log_query':
        return _execute_log_query_node(cfg, ctx)

    if node_type == 'file_generate':
        return _execute_file_node(cfg, ctx)

    return {'error': f'不支持的节点类型: {node_type}'}


def _execute_approval(node, cfg, ctx):
    mode = cfg.get('mode') or 'manual'
    message = _render_string(cfg.get('message') or '请审批该流程节点', ctx)
    node_name = node.get('name') or '审批节点'

    if mode == 'ai':
        instruction = cfg.get('ai_instruction') or '请判断当前流程是否可以继续执行，只回答 PASS 或 REJECT，并给出简要理由。'
        digest = json.dumps(ctx, ensure_ascii=False, default=str)
        if len(digest) > 6000:
            digest = digest[:6000] + '...(已截断)'
        messages = [
            {'role': 'system', 'content': '你是流程审批督查员。请严格依据给定信息判断，只输出 PASS 或 REJECT，并附一句理由。'},
            {'role': 'user', 'content': f'审批事项：{message}\n审批要求：{instruction}\n流程上下文：{digest}'},
        ]
        try:
            from app.services.ai_service import AiService
            result = AiService.chat_with_failover(messages)
            text = result[0] if isinstance(result, tuple) else str(result)
        except Exception as e:
            return {'error': f'AI 督查员审批失败：{e}'}

        approved = 'REJECT' not in (text or '').upper()
        output = {'mode': 'ai', 'approved': approved, 'reason': (text or '').strip()}
        return {
            'output': output,
            'branch': 'approved' if approved else 'rejected',
        }

    approvers = cfg.get('approvers') or []
    if isinstance(approvers, str):
        approvers = [a.strip() for a in approvers.split(',') if a.strip()]
    approval = {
        'node_id': node.get('id'),
        'node_name': node_name,
        'mode': 'manual',
        'message': message,
        'approvers': approvers,
    }
    return {'pending': True, 'approval': approval}


def _execute_query_node(cfg, ctx):
    from app.services.query_service import QueryService

    script_ids = _as_int_list(cfg.get('script_ids') or cfg.get('script_id'))
    if not script_ids:
        return {'error': '查询节点未选择脚本'}
    input_file = _render_string(cfg.get('input_file') or '', ctx)
    if not input_file:
        return {'error': '查询节点需要指定输入文件（Excel 参数文件）'}
    if not os.path.exists(input_file):
        return {'error': f'输入文件不存在：{input_file}'}

    db_ids = _as_int_list(cfg.get('database_ids'))
    if not db_ids:
        for sid in script_ids:
            from app.models.script import Script
            script = Script.query.get(sid)
            if script:
                db_ids.extend(script.get_database_ids())
    db_ids = list(dict.fromkeys(db_ids))

    output_dir = current_app.config.get('OUTPUT_FOLDER', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    template_params = _render(cfg.get('param_values') or {}, ctx)
    task = QueryService.create_task(script_ids[0], db_ids, input_file,
                                    merge_strategy=cfg.get('merge_strategy') or 'concat')
    QueryService.execute_query_async(
        task.task_id, script_ids[0], script_ids, db_ids, input_file, output_dir,
        param_column=cfg.get('param_column') or None,
        merge_strategy=cfg.get('merge_strategy') or 'concat',
        template_params=template_params or None,
    )
    info = _wait_task(QueryService.get_task_status, task.task_id)
    if info.get('status') != 'completed':
        return {'error': info.get('error_message') or f'查询任务状态：{info.get("status")}'}
    return {'output': {
        'task_id': task.task_id,
        'output_file': info.get('output_file'),
        'total_rows': info.get('total_rows', 0),
        'success_count': info.get('success_count', 0),
        'failure_count': info.get('failure_count', 0),
    }}


def _execute_export_node(cfg, ctx):
    from app.services.export_service import ExportService

    script_ids = _as_int_list(cfg.get('script_ids') or cfg.get('script_id'))
    if not script_ids:
        return {'error': '导出节点未选择脚本'}

    params_values = _render(cfg.get('param_values') or {}, ctx)
    output_dir = current_app.config.get('OUTPUT_FOLDER', 'outputs')
    os.makedirs(output_dir, exist_ok=True)
    output_format = cfg.get('output_format') or 'sheets'

    task = ExportService.create_export_task(script_ids, params_values, output_format=output_format)
    ExportService.execute_export_async(task.task_id, script_ids, params_values, output_dir,
                                       output_format=output_format)
    info = _wait_task(ExportService.get_task_status, task.task_id)
    if info.get('status') != 'completed':
        return {'error': info.get('error_message') or f'导出任务状态：{info.get("status")}'}
    return {'output': {
        'task_id': task.task_id,
        'output_file': info.get('output_file'),
        'total_rows': info.get('total_rows', 0),
        'output_format': output_format,
    }}


def _execute_system_task_node(cfg, ctx):
    from app.services.system_task_service import SystemTaskService

    system_task_id = cfg.get('system_task_id')
    if not system_task_id:
        return {'error': '系统任务节点未选择系统任务'}
    params_values = _render(cfg.get('param_values') or {}, ctx)

    execution = SystemTaskService.create_execution(int(system_task_id), params_values)
    SystemTaskService.execute_async(execution.execution_id, int(system_task_id), params_values,
                                    database_id=cfg.get('database_id'))
    info = _wait_task(SystemTaskService.get_execution_status, execution.execution_id)
    if info.get('status') != 'completed':
        return {'error': info.get('error_message') or f'系统任务状态：{info.get("status")}'}
    return {'output': {
        'execution_id': execution.execution_id,
        'status': info.get('status'),
        'result': info.get('result_data'),
    }}


def _execute_script_node(cfg, ctx):
    """脚本节点：支持 Python/Shell/Bat/PowerShell/Node 及自定义解释器脚本"""
    script_type = (cfg.get('script_type') or 'python').strip().lower()
    interpreter = _build_script_command(script_type, cfg.get('interpreter'))
    if not interpreter:
        return {'error': f'脚本节点解释器无效：{script_type}'}

    script_source = cfg.get('script_source') or 'inline'
    script_path = _render_string(cfg.get('script_path') or '', ctx).strip()
    content = _render_string(cfg.get('script_content') or '', ctx)
    if script_source == 'file' and not script_path:
        return {'error': '脚本节点未配置脚本文件路径'}
    if script_source != 'file' and not content.strip():
        return {'error': '脚本节点未填写脚本内容'}

    params_values = _render(cfg.get('param_values') or {}, ctx)
    if not isinstance(params_values, dict):
        params_values = {}
    try:
        timeout = int(cfg.get('timeout') or 300)
    except (TypeError, ValueError):
        timeout = 300
    timeout = max(1, min(timeout, 3600))

    temp_dir = None
    try:
        if script_source == 'file':
            if not os.path.isfile(script_path):
                return {'error': f'脚本文件不存在：{script_path}'}
            target_path = script_path
            workdir = os.path.dirname(os.path.abspath(script_path)) or None
        else:
            temp_dir = tempfile.mkdtemp(prefix='wf_script_')
            suffix = _SCRIPT_SUFFIXES.get(script_type, '.txt')
            target_path = os.path.join(temp_dir, f'node_script{suffix}')
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            workdir = temp_dir

        cmd = [*interpreter, target_path]
        env = os.environ.copy()
        for k, v in params_values.items():
            key = str(k)
            cmd.extend([f'--{key}', '' if v is None else str(v)])
            env[f'SCRIPT_PARAM_{key.upper()}'] = '' if v is None else str(v)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                    env=env, cwd=workdir)
        except subprocess.TimeoutExpired:
            return {'error': f'脚本执行超时（{timeout}秒）'}
        except FileNotFoundError as e:
            return {'error': f'脚本解释器未找到：{e}'}

        stdout = result.stdout or ''
        stderr = result.stderr or ''
        output = {
            'returncode': result.returncode,
            'stdout': _parse_script_stdout(stdout),
            'stderr': stderr,
            'success': result.returncode == 0,
        }
        if result.returncode != 0:
            detail = stderr.strip()[:500]
            return {'output': output, 'error': f'脚本执行失败，返回码 {result.returncode}' + (f'：{detail}' if detail else '')}
        return {'output': output}
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _build_script_command(script_type, interpreter):
    """根据脚本类型返回解释器命令前缀，自定义类型直接解析解释器命令"""
    if script_type == 'custom':
        command = (interpreter or '').strip()
        return shlex.split(command) if command else None
    prefix = _SCRIPT_INTERPRETERS.get(script_type)
    if prefix is not None:
        return list(prefix)
    # 未预置的类型视为解释器名（如 ruby、php、perl）
    command = (interpreter or script_type).strip()
    return shlex.split(command) if command else None


def _parse_script_stdout(stdout):
    text = (stdout or '').strip()
    if not text:
        return ''
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return stdout


def _execute_lookup_node(cfg, ctx):
    from app.services.lookup_service import LookupService

    script_id = cfg.get('script_id') or (cfg.get('script_ids') or [None])[0]
    if not script_id:
        return {'error': '信息查询节点未选择脚本'}
    params_values = _render(cfg.get('param_values') or {}, ctx)
    result = LookupService.execute_lookup(int(script_id), params_values)
    if not result.get('success'):
        return {'error': result.get('error_message') or '信息查询失败'}
    return {'output': {
        'row_count': result.get('row_count', 0),
        'columns': result.get('columns') or [],
        'results': result.get('results') or [],
    }}


def _execute_email_node(cfg, ctx):
    from app.services.pay_flow_service import _send_email

    to_raw = cfg.get('to') or cfg.get('to_addresses') or []
    if isinstance(to_raw, str):
        to_addresses = [a.strip() for a in re.split(r'[,;，；\s]+', to_raw) if a.strip()]
    else:
        to_addresses = [str(a).strip() for a in to_raw if str(a).strip()]
    if not to_addresses:
        return {'error': '邮件节点未配置收件人'}

    subject = _render_string(cfg.get('subject') or '工作流通知', ctx)
    content = _render_string(cfg.get('content') or '', ctx)
    _send_email(to_addresses, subject, content)
    return {'output': {'to': to_addresses, 'subject': subject, 'sent': True}}


def _execute_log_query_node(cfg, ctx):
    from app.models.login_log import LoginLog
    from app.models.operation_log import OperationLog

    log_type = cfg.get('log_type') or 'operation'
    try:
        limit = min(int(cfg.get('limit') or 50), 500)
    except (TypeError, ValueError):
        limit = 50
    keyword = _render_string(cfg.get('keyword') or '', ctx).strip()

    if log_type == 'login':
        query = LoginLog.query
        if keyword:
            query = query.filter(LoginLog.username.contains(keyword))
        rows = [r.to_dict() for r in query.order_by(LoginLog.id.desc()).limit(limit).all()]
    else:
        query = OperationLog.query
        if keyword:
            query = query.filter(OperationLog.username.contains(keyword))
        action = _render_string(cfg.get('action') or '', ctx).strip()
        if action:
            query = query.filter(OperationLog.action == action)
        rows = [r.to_dict() for r in query.order_by(OperationLog.id.desc()).limit(limit).all()]

    return {'output': {'log_type': log_type, 'row_count': len(rows), 'rows': rows}}


def _execute_file_node(cfg, ctx):
    from app.services.file_generation_service import create_file

    content = _render_string(cfg.get('content') or '', ctx)
    filename = _render_string(cfg.get('filename') or '', ctx) or None
    title = _render_string(cfg.get('title') or '', ctx) or None
    sheets = cfg.get('sheets')
    if isinstance(sheets, str) and sheets.strip():
        try:
            sheets = json.loads(_render_string(sheets, ctx))
        except (json.JSONDecodeError, TypeError):
            return {'error': 'sheets 配置必须是合法 JSON'}
    result = create_file(filename=filename, content=content, sheets=sheets,
                         title=title, fmt=cfg.get('fmt'))
    if isinstance(result, dict) and result.get('error'):
        return {'error': result['error']}
    return {'output': result}


# ---------------------------------------------------------------------------
# 等待子任务 / 模板渲染 / 条件判断
# ---------------------------------------------------------------------------

def _wait_task(status_fn, task_id, timeout=1800, interval=1.0):
    deadline = time.time() + timeout
    info = None
    while time.time() < deadline:
        info = status_fn(task_id)
        if not info:
            raise RuntimeError('子任务记录不存在或已被删除')
        if info.get('status') in ('completed', 'failed', 'cancelled'):
            return info
        time.sleep(interval)
    raise RuntimeError('子任务执行超时')


def _render(value, ctx):
    if isinstance(value, str):
        stripped = value.strip()
        match = _TEMPLATE_RE.fullmatch(stripped)
        if match:
            return _resolve_path(ctx, match.group(1))
        return _TEMPLATE_RE.sub(lambda m: _to_text(_resolve_path(ctx, m.group(1))), value)
    if isinstance(value, list):
        return [_render(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _render(v, ctx) for k, v in value.items()}
    return value


def _render_string(value, ctx):
    if value is None:
        return ''
    return _to_text(_render(str(value), ctx))


def _resolve_path(ctx, path):
    path = (path or '').strip()
    if path.startswith('ctx.'):
        path = path[4:]
    parts = re.split(r'\.|\[|\]', path)
    parts = [p for p in parts if p != '']
    current = ctx
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return ''
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return ''
        else:
            return ''
    return current


def _to_text(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _eval_condition(expression, ctx):
    if not expression:
        return False
    text = _TEMPLATE_RE.sub(lambda m: _to_text(_resolve_path(ctx, m.group(1))), str(expression))
    text = text.strip()
    if not text:
        return False
    for or_part in re.split(r'\|\||\s+or\s+', text, flags=re.IGNORECASE):
        conditions = re.split(r'&&|\s+and\s+', or_part, flags=re.IGNORECASE)
        if all(_eval_single(c.strip(), ctx) for c in conditions if c.strip()):
            return True
    return False


def _operand_value(text, ctx):
    """条件操作数取值：支持 {{变量}}、裸路径、数字/字符串字面量。"""
    text = (text or '').strip()
    lowered = text.lower()
    if (ctx is not None and lowered not in ('true', 'false', 'null', 'none')
            and re.match(r'^[A-Za-z_][\w.\[\]]*$', text)):
        resolved = _resolve_path(ctx, text)
        if resolved != '' and resolved is not None:
            return resolved
    return _parse_literal(text)


def _eval_single(text, ctx=None):
    if not text:
        return False
    match = re.match(r'^(.*?)\s*(>=|<=|==|!=|>|<|contains)\s*(.*?)$', text, re.IGNORECASE)
    if not match:
        value = _operand_value(text, ctx)
        return _to_text(value).strip().lower() not in ('', 'false', '0', 'no', 'null', 'none')
    left, op, right = match.group(1).strip(), match.group(2).lower(), match.group(3).strip()
    left_val = _operand_value(left, ctx)
    right_val = _operand_value(right, ctx)
    try:
        if op == 'contains':
            return str(right_val or '').lower() in str(left_val or '').lower()
        if op in ('>', '<', '>=', '<='):
            left_num = float(left_val)
            right_num = float(right_val)
            return {'>': left_num > right_num, '<': left_num < right_num,
                    '>=': left_num >= right_num, '<=': left_num <= right_num}[op]
        if op == '==':
            return _loose_equal(left_val, right_val)
        return not _loose_equal(left_val, right_val)
    except (TypeError, ValueError):
        return False


def _parse_literal(text):
    text = (text or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    lowered = text.lower()
    if lowered in ('true', 'false'):
        return lowered == 'true'
    if lowered in ('null', 'none'):
        return None
    if _NUMBER_RE.match(text):
        return float(text) if '.' in text else int(text)
    return text


def _loose_equal(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return _to_text(a) == _to_text(b)


def _as_int_list(value):
    if value is None or value == '':
        return []
    if isinstance(value, (int, str)):
        value = [value]
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result