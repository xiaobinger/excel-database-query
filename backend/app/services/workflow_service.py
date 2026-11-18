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
    'ai': '智能AI',
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
    'query', 'export', 'system_task', 'script', 'lookup', 'ai', 'email', 'log_query', 'file_generate',
}

# 已归并为「智能AI」节点的旧节点类型：保留执行兼容与旧流程展示，但不再作为新节点提供
DEPRECATED_NODE_TYPES = {'email', 'log_query', 'file_generate'}

# 智能AI节点能力预设提示词
_AI_CAPABILITY_PROMPTS = {
    'auto': '请根据任务指令自行判断需要执行的操作；需要工具时直接调用。',
    'email': ('本次任务是发送邮件通知。请根据任务指令与流程上下文确定收件人、主题和正文，'
              '并调用 send_email 工具实际发送邮件；不得只在回复中描述邮件内容。'),
    'log_query': ('本次任务是查询/分析系统日志。日志数据已随任务提供，请按任务指令完成筛选、统计、'
                  '异常识别或汇总，并输出结论；如任务要求发送邮件或生成文件，可继续调用相应工具。'),
    'file_generate': ('本次任务是生成文件。请整理任务指令要求的内容，并调用 create_file 工具实际生成文件；'
                      '文件名与格式按指令要求确定，不得只在回复中贴出内容。'),
    'summary': '本次任务是总结。请阅读任务指令与流程上下文，输出简洁准确的总结正文，不要调用任何工具。',
    'custom': '请严格按照任务指令执行，必要时调用可用工具。',
}

_TEMPLATE_RE = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')
_NUMBER_RE = re.compile(r'^-?\d+(\.\d+)?$')


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
    from app.models.ai_agent import AiAgent
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
    agents = [{'id': a.id, 'name': a.name, 'agent_role': a.agent_role,
               'description': a.description or ''}
              for a in AiAgent.query.filter_by(is_active=True).order_by(AiAgent.id).all()]

    return {
        'scripts': scripts,
        'databases': databases,
        'system_tasks': system_tasks,
        'approvers': approvers,
        'agents': agents,
        'node_types': [{'type': k, 'label': v} for k, v in NODE_TYPE_LABELS.items()
                       if k not in DEPRECATED_NODE_TYPES],
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
            result = _execute_node(node, ctx, run_id, run.created_by)
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

def _execute_node(node, ctx, run_id, user_id=None):
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

    if node_type == 'ai':
        return _execute_ai_node(cfg, ctx, user_id)

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
    """脚本节点：执行脚本库中的 SQL 脚本，按脚本类型调用对应的原服务。

    query -> 查询服务（需 Excel 参数文件）；export -> 导出服务；lookup -> 信息查询；system -> 执行 SQL。
    """
    from app.models.script import Script

    script_id = cfg.get('script_id') or (cfg.get('script_ids') or [None])[0]
    if not script_id:
        return {'error': '脚本节点未选择 SQL 脚本'}
    try:
        script = Script.query.get(int(script_id))
    except (TypeError, ValueError):
        script = None
    if not script:
        return {'error': f'SQL 脚本不存在：{script_id}'}

    script_type = (script.type or 'query').strip().lower()
    if script_type == 'query':
        return _execute_query_node(dict(cfg, script_ids=[script.id]), ctx)
    if script_type == 'export':
        return _execute_export_node(dict(cfg, script_ids=[script.id]), ctx)
    if script_type == 'lookup':
        return _execute_lookup_node(dict(cfg, script_id=script.id), ctx)
    if script_type == 'system':
        return _execute_system_script(script, cfg, ctx)
    return {'error': f'脚本节点暂不支持的脚本类型：{script_type}'}


def _execute_system_script(script, cfg, ctx):
    """执行系统类 SQL 脚本（DML/DDL），支持参数替换、多语句与列表参数。"""
    from sqlalchemy import text

    from app.models.database import DatabaseConnection
    from app.services.system_task_service import SystemTaskService
    from app.utils.connection_pool import ConnectionPoolManager
    from app.utils.sql_validator import SQLValidator

    sql_text = script.sql_text or ''
    if not sql_text.strip():
        return {'error': 'SQL 脚本内容为空'}

    params_values = _render(cfg.get('param_values') or {}, ctx)
    if not isinstance(params_values, dict):
        params_values = {}
    for key, val in params_values.items():
        sql_text = sql_text.replace(f'{{{{{key}}}}}', '' if val is None else str(val))
    sql_text = _render_string(sql_text, ctx)

    validation = SQLValidator().validate(sql_text, allow_dml=True)
    if not validation.is_valid:
        return {'error': f'SQL 校验失败：{validation.message}'}

    # 过滤空值，并识别需要按 IN 展开的列表参数
    bind_params = {}
    list_params = {}
    for key, val in params_values.items():
        if val is None or val == '':
            continue
        if isinstance(val, (list, tuple)):
            values = [str(v).strip() for v in val if str(v).strip()]
            if values:
                list_params[key] = values
        elif isinstance(val, str) and re.search(r'[,，]', val):
            parts = [p.strip() for p in re.split(r'[,，]', val) if p.strip()]
            if len(parts) >= 2:
                list_params[key] = parts
            else:
                bind_params[key] = val
        else:
            bind_params[key] = val

    statements = SystemTaskService._split_sql_statements(sql_text)
    if not statements:
        return {'error': '没有可执行的 SQL 语句'}
    expanded = []
    for stmt in statements:
        for key, values in list_params.items():
            pattern = rf'\bIN\s*\(\s*:{key}\s*\)'
            if re.search(pattern, stmt, re.IGNORECASE):
                placeholders = ', '.join(f':{key}_{i}' for i in range(len(values)))
                stmt = re.sub(pattern, f'IN ({placeholders})', stmt, flags=re.IGNORECASE)
                for i, val in enumerate(values):
                    bind_params[f'{key}_{i}'] = val
            elif f':{key}' in stmt:
                bind_params[key] = values[0]
        expanded.append(stmt)
    statements = expanded

    db_ids = _as_int_list(cfg.get('database_ids') or cfg.get('database_id'))
    if not db_ids:
        db_ids = script.get_database_ids() or []
    db_ids = list(dict.fromkeys(db_ids))
    if not db_ids:
        return {'error': 'SQL 脚本未配置数据库连接'}

    pool = ConnectionPoolManager.get_instance()
    results = []
    total_affected = 0
    for conn_id in db_ids:
        conn_model = DatabaseConnection.query.get(conn_id)
        if not conn_model:
            continue
        connector = pool.get_connector_with_health_check(conn_id)
        if not connector:
            return {'error': f'数据库连接失败：{conn_model.name}'}

        db_statements = []
        with connector.get_connection() as conn:
            for stmt_idx, stmt in enumerate(statements):
                if not stmt.strip():
                    continue
                result = (conn.execute(text(stmt), bind_params) if bind_params
                          else conn.execute(text(stmt)))

                if SystemTaskService._is_query_statement(stmt):
                    columns = list(result.keys()) if hasattr(result, 'keys') else []
                    rows = []
                    for row in result.fetchall():
                        if columns:
                            rows.append({columns[i]: row[i] for i in range(min(len(columns), len(row)))})
                        else:
                            rows.append({f'col_{i}': val for i, val in enumerate(row)})
                    db_statements.append({
                        'statement_index': stmt_idx,
                        'statement': stmt[:200],
                        'type': 'query',
                        'columns': columns,
                        'row_count': len(rows),
                        'rows': rows,
                    })
                else:
                    rowcount = result.rowcount if hasattr(result, 'rowcount') else 0
                    if rowcount and rowcount > 0:
                        total_affected += rowcount
                    conn.commit()
                    db_statements.append({
                        'statement_index': stmt_idx,
                        'statement': stmt[:200],
                        'type': 'command',
                        'rowcount': rowcount,
                    })

        results.append({
            'database_id': conn_id,
            'database_name': conn_model.name,
            'statements': db_statements,
        })

    return {'output': {
        'script_id': script.id,
        'script_name': script.name,
        'script_type': 'system',
        'total_affected': total_affected,
        'results': results,
    }}


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


def _execute_ai_node(cfg, ctx, user_id=None):
    """智能AI节点：按指定 Agent + 能力 + 白话文指令执行，支持工具调用循环。"""
    from app.models.ai_agent import AiAgent
    from app.services.ai_service import AiService, get_effective_tools

    capability = (cfg.get('capability') or 'auto').strip()
    instruction = _render_string(cfg.get('instruction') or '', ctx).strip()
    if not instruction:
        instruction = '请根据当前流程上下文完成合理处理，并输出处理结果。'

    agent = None
    agent_id = cfg.get('agent_id')
    if agent_id:
        try:
            agent = AiAgent.query.get(int(agent_id))
        except (TypeError, ValueError):
            agent = None
        if not agent:
            return {'error': f'智能AI节点指定的 Agent 不存在：{agent_id}'}

    # 日志能力：先按条件取数，随任务一并提供给AI
    log_output = None
    if capability == 'log_query':
        log_output = _execute_log_query_node({
            'log_type': cfg.get('log_type') or 'operation',
            'keyword': cfg.get('keyword') or '',
            'action': cfg.get('action') or '',
            'limit': cfg.get('limit') or 50,
        }, ctx)
        if log_output.get('error'):
            return log_output

    # 系统提示词：Agent 自身提示词 + 节点角色 + 能力预设
    parts = []
    if agent and agent.system_prompt:
        parts.append(agent.system_prompt.strip())
    parts.append('你是混合工作流中的「智能AI」节点，负责完成当前流程节点交给你的任务。')
    parts.append(_AI_CAPABILITY_PROMPTS.get(capability, _AI_CAPABILITY_PROMPTS['custom']))
    parts.append('执行完成后请给出简明结论，结论会被写入流程上下文供后续节点使用。')
    system_prompt = '\n'.join(p for p in parts if p)

    user_parts = [f'任务指令：\n{instruction}']
    if log_output:
        rows = (log_output.get('output') or {}).get('rows') or []
        log_text = json.dumps(rows, ensure_ascii=False, default=str)
        if len(log_text) > 8000:
            log_text = log_text[:8000] + '...(已截断)'
        user_parts.append(f'日志数据（共 {len(rows)} 条）：\n{log_text}')
    if cfg.get('include_context', True):
        try:
            context_limit = max(500, min(int(cfg.get('context_limit') or 6000), 20000))
        except (TypeError, ValueError):
            context_limit = 6000
        digest = json.dumps(ctx, ensure_ascii=False, default=str)
        if len(digest) > context_limit:
            digest = digest[:context_limit] + '...(已截断)'
        user_parts.append(f'流程上下文（JSON，供参考）：\n{digest}')

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': '\n\n'.join(user_parts)},
    ]

    try:
        max_rounds = max(1, min(int(cfg.get('max_rounds') or 5), 10))
    except (TypeError, ValueError):
        max_rounds = 5

    # 总结能力不需要工具，其余按 Agent 授权工具执行
    tools = [] if capability == 'summary' else get_effective_tools(agent)

    final_content = ''
    tool_log = []
    rounds_used = 0
    try:
        if not tools:
            response = AiService.chat_with_failover(messages, use_tools=False, scope='workflow')
            final_content = response[0] or ''
            rounds_used = 1
        else:
            for round_idx in range(max_rounds):
                rounds_used = round_idx + 1
                response = AiService.chat_with_failover(
                    messages, use_tools=True, tools=tools, scope='workflow')
                content = (response.get('content') or '')
                tool_calls = response.get('tool_calls') or []
                if not tool_calls:
                    final_content = content
                    break

                messages.append({'role': 'assistant', 'content': content, 'tool_calls': tool_calls})
                for tc in tool_calls:
                    func = tc.get('function') or {}
                    func_name = func.get('name') or ''
                    func_args = func.get('arguments') or ''
                    result = AiService.execute_tool_call(
                        func_name, func_args, user_id, agent_id=agent.id if agent else None)
                    result_text = json.dumps(result, ensure_ascii=False, default=str)
                    if len(result_text) > 6000:
                        result_text = result_text[:6000] + '...(已截断)'
                    messages.append({
                        'role': 'tool',
                        'tool_call_id': tc.get('id') or '',
                        'content': result_text,
                    })
                    error = result.get('error') if isinstance(result, dict) else None
                    tool_log.append({'name': func_name, 'arguments': func_args, 'error': error})

            if not final_content:
                # 达到轮次上限仍在调用工具，让AI基于已有结果归总
                response = AiService.chat_with_failover(messages, use_tools=False, scope='workflow')
                final_content = response[0] or ''
    except Exception as e:
        logger.error(f'智能AI节点执行失败: {e}', exc_info=True)
        return {'error': f'智能AI节点执行失败：{e}'}

    final_content = (final_content or '').strip() or 'AI 已完成处理，但未返回文本内容。'
    output = {
        'content': final_content,
        'capability': capability,
        'agent_id': agent.id if agent else None,
        'agent_name': agent.name if agent else '默认AI',
        'rounds': rounds_used,
        'tool_calls': tool_log,
    }
    if log_output:
        output['log_type'] = (log_output.get('output') or {}).get('log_type')
        output['log_row_count'] = (log_output.get('output') or {}).get('row_count', 0)
    return {'output': output}


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