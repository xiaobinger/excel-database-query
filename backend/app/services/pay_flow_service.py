"""代付流程引擎

负责：
- 流程模板的 CRUD
- 发起流程（为每笔数据创建独立实例）
- 节点推进、条件流转、循环执行
- 通知节点（邮件）执行
- 执行记录查询
"""
import json
import logging
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid

from app import db
from app.models.pay_flow import PayFlowTemplate, PayFlowExecution, PayFlowNodeExecution, PayFlowNotifyTemplate
from app.models.pay_config import PayConfig
from app.utils.helpers import beijing_now, beijing_isoformat

logger = logging.getLogger(__name__)

# 节点字段定义（前端编排时参考）
NODE_FIELDS = {
    'id': {'type': 'string', 'label': '节点ID', 'required': True},
    'name': {'type': 'string', 'label': '节点名称', 'required': True},
    'type': {'type': 'string', 'label': '节点类型', 'options': ['pay', 'notify'], 'required': True},
    'action': {'type': 'object', 'label': '执行动作', 'required': True},
    'transitions': {'type': 'array', 'label': '流转条件', 'default': []},
    'loop': {'type': 'object', 'label': '循环配置', 'default': None},
}

# 条件操作符
OPERATORS = {
    'eq': '等于',
    'neq': '不等于',
    'contains': '包含',
    'not_contains': '不包含',
    'gt': '大于',
    'gte': '大于等于',
    'lt': '小于',
    'lte': '小于等于',
    'in': '在列表中',
    'not_in': '不在列表中',
    'success': '成功',
    'fail': '失败',
}


# ---------------------------------------------------------------------------
# 模板 CRUD
# ---------------------------------------------------------------------------

def get_templates(page=1, per_page=20, keyword=None, is_enabled=None):
    query = PayFlowTemplate.query
    if keyword:
        query = query.filter(PayFlowTemplate.name.contains(keyword))
    if is_enabled is not None:
        query = query.filter(PayFlowTemplate.is_enabled == is_enabled)
    pagination = query.order_by(PayFlowTemplate.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return {
        'items': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
    }


def get_template(template_id):
    t = PayFlowTemplate.query.get(template_id)
    if not t:
        return None
    return t.to_dict()


def create_template(data, created_by=None):
    t = PayFlowTemplate(
        name=data.get('name', ''),
        description=data.get('description', ''),
        is_enabled=data.get('is_enabled', True),
        created_by=created_by,
    )
    t.set_nodes(data.get('nodes', []))
    db.session.add(t)
    db.session.commit()
    return t.to_dict()


def update_template(template_id, data):
    t = PayFlowTemplate.query.get(template_id)
    if not t:
        return None
    if 'name' in data:
        t.name = data['name']
    if 'description' in data:
        t.description = data['description']
    if 'is_enabled' in data:
        t.is_enabled = data['is_enabled']
    if 'nodes' in data:
        t.set_nodes(data['nodes'])
    db.session.commit()
    return t.to_dict()


def delete_template(template_id):
    t = PayFlowTemplate.query.get(template_id)
    if not t:
        return False
    PayFlowNodeExecution.query.filter_by(execution_id=None).delete()
    db.session.delete(t)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# 发起流程
# ---------------------------------------------------------------------------

def start_flow(template_id, rows, params, created_by=None):
    """为每笔数据创建独立流程实例

    Args:
        template_id: 模板ID
        rows: list[list] - Excel 数据行列表
        params: dict - 执行参数（channel, interface_type, environment 等）
            - summary_notify_enabled: 是否启用汇总通知
            - summary_notify_template_id: 汇总通知模板ID
        created_by: 创建用户ID

    Returns:
        batch_id, [execution_id, ...]
    """
    template = PayFlowTemplate.query.get(template_id)
    if not template or not template.is_enabled:
        raise ValueError('流程模板不存在或未启用')

    batch_id = uuid.uuid4().hex
    execution_ids = []

    summary_notify_enabled = bool(params.get('summary_notify_enabled'))
    summary_notify_template_id = params.get('summary_notify_template_id') if summary_notify_enabled else None

    for idx, row in enumerate(rows):
        execution_id = uuid.uuid4().hex
        execution = PayFlowExecution(
            execution_id=execution_id,
            template_id=template.id,
            template_name=template.name,
            batch_id=batch_id,
            row_index=idx + 1,
            status='pending',
            current_node_index=0,
            created_by=created_by,
            summary_notify_enabled=summary_notify_enabled,
            summary_notify_template_id=summary_notify_template_id,
        )
        execution.set_row_data(row)
        execution.set_context({})
        db.session.add(execution)
        execution_ids.append(execution_id)

    db.session.commit()
    logger.info(f'发起代付流程: template={template.name} batch_id={batch_id} 数据行数={len(rows)} 汇总通知={summary_notify_enabled}')
    return batch_id, execution_ids


# ---------------------------------------------------------------------------
# 流程推进
# ---------------------------------------------------------------------------

def advance_flow(execution_id):
    """推进单个流程实例到下一个节点

    由调度器调用，处理：
    1. 当前节点执行
    2. 条件判断决定下一节点
    3. 循环节点处理
    4. 完成/失败处理

    安全：通过数据库原子抢占（CAS）防止同一实例被并发重复执行（资金安全）。
    UPDATE ... WHERE status IN ('pending','waiting') 是数据库级原子操作：
    即使多个后端进程、多个线程同时分发同一实例，也只有一个能抢占成功，
    其余全部跳过。抢占成功后 status='running' 立即提交落库，
    任何后续分发都会因状态不匹配而失败。
    """
    from app import db

    execution = db.session.query(PayFlowExecution).filter(
        PayFlowExecution.execution_id == execution_id
    ).first()

    if not execution:
        return

    # waiting 状态：未到下次执行时间则不推进
    if execution.status == 'waiting':
        if execution.next_run_at and execution.next_run_at > datetime.utcnow():
            return

    # 原子抢占：将 pending/waiting 置为 running，同一时刻只有一个调用方能成功
    claimed = db.session.query(PayFlowExecution).filter(
        PayFlowExecution.execution_id == execution_id,
        PayFlowExecution.status.in_(('pending', 'waiting')),
    ).update({
        'status': 'running',
        'last_dispatched_at': datetime.utcnow(),
    }, synchronize_session=False)
    db.session.commit()

    if claimed == 0:
        logger.info(f'流程 {execution_id} 抢占失败(状态不允许或已被其他线程/进程处理)，跳过')
        return

    # bulk update 不会同步 session 内对象，重新加载最新状态
    db.session.expire_all()
    execution = db.session.query(PayFlowExecution).filter(
        PayFlowExecution.execution_id == execution_id
    ).first()

    template = PayFlowTemplate.query.get(execution.template_id)
    if not template:
        execution.status = 'failed'
        execution.error_message = '模板不存在'
        db.session.commit()
        return

    nodes = template.get_nodes()
    if not nodes:
        execution.status = 'failed'
        execution.error_message = '模板无节点'
        db.session.commit()
        return

    current_idx = execution.current_node_index
    if current_idx >= len(nodes):
        _complete_flow(execution, '所有节点执行完成')
        return

    node = nodes[current_idx]
    node_id = node.get('id', f'node_{current_idx}')
    node_name = node.get('name', f'节点{current_idx + 1}')
    node_type = node.get('type', 'pay')

    # 检查循环
    loop_cfg = node.get('loop') or {}
    is_loop = loop_cfg.get('enabled', False)
    loop_node_id = execution.loop_node_id

    if is_loop and loop_node_id == node_id:
        # 继续循环
        loop_count = execution.loop_count + 1
        max_iter = loop_cfg.get('max_iterations', 10)
        if loop_count >= max_iter:
            # 超过最大循环次数，强制推进
            logger.warning(f'流程 {execution_id} 节点 {node_name} 循环 {loop_count} 次，达到上限 {max_iter}，强制推进')
            execution.loop_node_id = None
            execution.loop_count = 0
            execution.current_node_index = current_idx + 1
            execution.status = 'pending'
            db.session.commit()
            advance_flow(execution_id)
            return

        # 检查是否满足退出条件
        result_fields = {}
        context = execution.get_context()
        if _evaluate_loop_exit(loop_cfg, {'success': True}, result_fields, context):
            logger.info(f'流程 {execution_id} 节点 {node_name} 满足退出条件，退出循环')
            execution.loop_node_id = None
            execution.loop_count = 0
            execution.current_node_index = current_idx + 1
            execution.status = 'pending'
            db.session.commit()
            advance_flow(execution_id)
            return

    # 执行节点（此时 status='running' 已由原子抢占提交落库，
    # 其他线程/进程的重复分发会在抢占阶段被直接拦截）
    now = datetime.utcnow()

    node_exec = PayFlowNodeExecution(
        execution_id=execution_id,
        node_id=node_id,
        node_name=node_name,
        node_type=node_type,
        attempt=execution.loop_count + 1 if is_loop else 1,
        status='running',
        started_at=now,
    )
    db.session.add(node_exec)
    db.session.flush()

    if not execution.started_at:
        execution.started_at = now

    try:
        if node_type == 'pay':
            result = _execute_pay_node(execution, node, node_exec)
        elif node_type == 'notify':
            result = _execute_notify_node(execution, node, node_exec)
        else:
            result = {'success': False, 'message': f'未知节点类型: {node_type}', 'fields': {}}

        node_exec.completed_at = datetime.utcnow()
        node_exec.status = 'completed' if result.get('success') else 'failed'

        # 合并结果到上下文
        ctx = execution.get_context()
        ctx[node_id] = result.get('fields', {})
        execution.set_context(ctx)

        if result.get('success'):
            node_exec.set_result_fields(result.get('fields', {}))
        else:
            node_exec.error_message = result.get('message', '执行失败')
            node_exec.set_result_fields(result.get('fields', {}))

        # 判断流转
        transitions = node.get('transitions', [])
        next_idx = _resolve_next_node(execution, nodes, current_idx, transitions, result)

        # 检查是否为结束节点
        is_end_node = node.get('is_end_node', False)

        if is_loop and next_idx == current_idx:
            # 检查是否满足退出条件
            if _evaluate_loop_exit(loop_cfg, result, result.get('fields', {}), execution.get_context()):
                logger.info(f'流程 {execution_id} 节点 {node_name} 满足退出条件，退出循环')
                execution.loop_node_id = None
                execution.loop_count = 0
                execution.current_node_index = current_idx + 1
                execution.status = 'pending'
                db.session.commit()
                advance_flow(execution_id)
                return
            # 循环：设置下次执行时间
            execution.loop_node_id = node_id
            execution.loop_count = execution.loop_count + 1
            interval = loop_cfg.get('interval_seconds', 60)
            execution.next_run_at = datetime.utcnow() + timedelta(seconds=interval)
            execution.status = 'waiting'
            node_exec.add_log(f'循环等待中，间隔 {interval}s，下次执行: {beijing_isoformat(execution.next_run_at)}')
        elif next_idx is None:
            # 节点失败或无匹配条件，流程失败
            # 重要：节点失败时必须立即停止流程，不允许继续执行
            execution.status = 'failed'
            execution.error_message = f'节点 {node_name} 执行失败'
            execution.completed_at = datetime.utcnow()
            db.session.commit()
            # 发送失败通知（在commit之后，确保状态已保存）
            _send_failure_notification(execution, node, node_exec, result)
            # 检查是否需要触发汇总通知
            _try_trigger_summary_notification(execution)
        elif is_end_node:
            # 结束节点：流程完成
            execution.current_node_index = current_idx + 1
            _complete_flow(execution, f'流程完成（结束节点: {node_name}）')
            # 发送结束通知
            _send_end_notification(execution, node, node_exec, result)
            # 检查是否需要触发汇总通知
            _try_trigger_summary_notification(execution)
        elif next_idx >= len(nodes):
            # 到达末尾
            execution.current_node_index = next_idx
            _complete_flow(execution, f'流程完成，最后节点: {node_name}')
            # 检查是否需要触发汇总通知
            _try_trigger_summary_notification(execution)
        else:
            # 成功流转到下一节点
            execution.current_node_index = next_idx
            execution.loop_node_id = None
            execution.loop_count = 0
            execution.status = 'pending'  # 设置为 pending 允许递归调用继续处理
            db.session.commit()
            # 立即推进下一节点（递归调用）
            advance_flow(execution_id)
            return

        db.session.commit()

    except Exception as e:
        logger.exception(f'流程节点执行异常: {execution_id} node={node_name}')
        node_exec.status = 'failed'
        node_exec.error_message = str(e)
        node_exec.completed_at = datetime.utcnow()
        node_exec.add_log(f'执行异常: {e}', level='error')
        execution.status = 'failed'
        execution.error_message = f'节点 {node_name} 异常: {e}'
        execution.completed_at = datetime.utcnow()
        db.session.commit()
        # 异常时也发送失败通知
        _send_failure_notification(execution, node, node_exec, {'success': False, 'message': str(e), 'fields': {}})
        # 检查是否需要触发汇总通知
        _try_trigger_summary_notification(execution)


def _send_failure_notification(execution, node, node_exec, result):
    """发送失败通知（启用汇总通知时跳过单笔通知）"""
    if not node.get('notify_on_failure'):
        return
    if execution.summary_notify_enabled:
        return
    try:
        _send_node_notification(execution, node, node_exec, '失败', result)
        logger.info(f'已发送失败通知: execution={execution.execution_id}, node={node.get("name", "")}')
    except Exception as notify_err:
        logger.error(f'发送失败通知异常: {notify_err}')


def _send_end_notification(execution, node, node_exec, result):
    """发送结束通知（启用汇总通知时跳过单笔通知）"""
    if not node.get('notify_on_end'):
        return
    if execution.summary_notify_enabled:
        return
    try:
        _send_node_notification(execution, node, node_exec, '完成', result)
        logger.info(f'已发送结束通知: execution={execution.execution_id}, node={node.get("name", "")}')
    except Exception as notify_err:
        logger.error(f'发送结束通知异常: {notify_err}')


def _try_trigger_summary_notification(execution):
    """检查批次是否全部完成，若是则触发汇总通知

    使用 CAS 确保并发下只有一个实例触发汇总通知：
    UPDATE ... WHERE summary_notify_sent=False 是原子操作，
    即使多个实例同时完成，也只有一个能成功抢占。
    """
    if not execution.summary_notify_enabled:
        return
    if execution.summary_notify_sent:
        return

    from app import db

    batch_id = execution.batch_id
    terminal_statuses = ('completed', 'failed', 'cancelled')

    # 检查批次内是否全部完成
    all_done = db.session.query(PayFlowExecution).filter(
        PayFlowExecution.batch_id == batch_id,
        ~PayFlowExecution.status.in_(terminal_statuses),
    ).count() == 0

    if not all_done:
        return

    # CAS 抢占：将 summary_notify_sent 从 False 置为 True，确保只触发一次
    claimed = db.session.query(PayFlowExecution).filter(
        PayFlowExecution.batch_id == batch_id,
        PayFlowExecution.summary_notify_sent == False,  # noqa: E712
    ).update({
        'summary_notify_sent': True,
    }, synchronize_session=False)
    db.session.commit()

    if claimed == 0:
        return

    try:
        _send_summary_notification(batch_id)
    except Exception as notify_err:
        logger.error(f'发送汇总通知异常: {notify_err}', exc_info=True)


def _send_summary_notification(batch_id):
    """发送汇总通知

    汇总批次内所有执行结果：总数、成功数、失败数、成功金额、失败金额、明细列表。
    """
    from app import db

    executions = PayFlowExecution.query.filter_by(batch_id=batch_id).order_by(PayFlowExecution.row_index).all()
    if not executions:
        return

    tpl_id = executions[0].summary_notify_template_id
    if not tpl_id:
        return

    tpl = PayFlowNotifyTemplate.query.get(tpl_id)
    if not tpl or not tpl.is_enabled:
        logger.warning(f'汇总通知模板ID={tpl_id}不存在或已禁用，跳过')
        return

    receivers = []
    if tpl.receivers:
        receivers = [addr.strip() for addr in tpl.receivers.split(',') if addr.strip()]
    if not receivers:
        logger.warning(f'汇总通知模板ID={tpl_id}未配置收件人，跳过')
        return

    # 汇总统计
    total = len(executions)
    success_list = []
    fail_list = []
    success_amount = 0.0
    fail_amount = 0.0

    for e in executions:
        row = e.get_row_data()
        amount_fen = 0.0
        try:
            amount_fen = float(row[8]) if len(row) > 8 and row[8] else 0.0
        except (ValueError, TypeError):
            amount_fen = 0.0
        amount = amount_fen / 100

        item = {
            'row_index': e.row_index,
            'status': e.status,
            'amount': amount,
            'accountName': row[2] if len(row) > 2 else '',
            'businessNo': row[3] if len(row) > 3 else '',
            'error_message': e.error_message or '',
        }

        if e.status == 'completed':
            success_list.append(item)
            success_amount += amount
        else:
            fail_list.append(item)
            fail_amount += amount

    success_count = len(success_list)
    fail_count = len(fail_list)

    # 构建汇总文本（HTML 邮件用 <br> 换行）
    success_lines = []
    for item in success_list:
        success_lines.append(f"行{item['row_index']}: {item['accountName']} {item['businessNo']} 金额{item['amount']:.2f}")
    fail_lines = []
    for item in fail_list:
        fail_lines.append(f"行{item['row_index']}: {item['accountName']} {item['businessNo']} 金额{item['amount']:.2f} 原因:{item['error_message']}")

    success_list_text = '<br>'.join(success_lines) if success_lines else '无'
    fail_list_text = '<br>'.join(fail_lines) if fail_lines else '无'

    # 替换模板变量
    subject = tpl.title or f'【代付流程汇总通知】{executions[0].template_name}'
    content = tpl.content or ''

    summary_vars = {
        'summary.total': str(total),
        'summary.success_count': str(success_count),
        'summary.fail_count': str(fail_count),
        'summary.success_amount': f'{success_amount:.2f}',
        'summary.fail_amount': f'{fail_amount:.2f}',
        'summary.success_list': success_list_text,
        'summary.fail_list': fail_list_text,
        'batch_id': batch_id,
        'template_name': executions[0].template_name,
    }
    for key, val in summary_vars.items():
        content = content.replace(f'{{{key}}}', val)
        subject = subject.replace(f'{{{key}}}', val)

    # 发送邮件
    _send_email(receivers, subject, content)
    logger.info(f'已发送汇总通知: batch_id={batch_id} 总{total}笔 成功{success_count}笔 失败{fail_count}笔')


def _send_email(to_addresses, subject, content):
    """发送邮件（从 SystemConfig 读取 SMTP 配置）"""
    from app.models.system_config import SystemConfig

    smtp_host_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_HOST).first()
    smtp_port_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PORT).first()
    smtp_user_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_USER).first()
    smtp_password_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PASSWORD).first()
    smtp_ssl_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_SSL).first()
    from_name_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_NAME).first()
    from_address_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_ADDRESS).first()

    if not smtp_host_config or not smtp_host_config.config_value:
        logger.error('SMTP主机未配置，无法发送邮件')
        return
    if not smtp_user_config or not smtp_user_config.config_value:
        logger.error('SMTP用户未配置，无法发送邮件')
        return

    host = smtp_host_config.config_value
    port = int(smtp_port_config.config_value) if smtp_port_config and smtp_port_config.config_value else 465
    user = smtp_user_config.config_value
    password = smtp_password_config.get_encrypted_value() if smtp_password_config else ''
    use_ssl = smtp_ssl_config.config_value.lower() in ('true', '1', 'yes') if smtp_ssl_config and smtp_ssl_config.config_value else True
    sender_name = from_name_config.config_value if from_name_config and from_name_config.config_value else '代付流程系统'
    sender_address = from_address_config.config_value if from_address_config and from_address_config.config_value else user

    if not all([host, user, password]):
        logger.error('邮件配置不完整，无法发送邮件')
        return

    msg = MIMEMultipart()
    msg['From'] = formataddr((sender_name, sender_address))
    msg['To'] = ', '.join(to_addresses)
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()
    msg.attach(MIMEText(content, 'html', 'utf-8'))

    import ssl
    context = ssl.create_default_context()
    if use_ssl and port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(user, password)
            server.sendmail(user, to_addresses, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(user, to_addresses, msg.as_string())


def _execute_pay_node(execution, node, node_exec):
    """执行代付动作节点"""
    action = node.get('action', {})
    channel = action.get('channel')
    environment = action.get('environment', 'test')
    interface_type = action.get('interface_type', '代付')
    real_time = action.get('real_time', '是')
    execute_type = action.get('execute_type', '创建代付')

    if not channel:
        return {'success': False, 'message': '未配置渠道', 'fields': {}}

    cfg_db = PayConfig.query.filter_by(channel=channel).first()
    if not cfg_db:
        return {'success': False, 'message': f'渠道 {channel} 未配置', 'fields': {}}

    cfg = cfg_db.get_pro_config() if environment == 'pro' else cfg_db.get_test_config()
    if not cfg:
        return {'success': False, 'message': f'渠道 {channel} 的 {environment} 环境未配置', 'fields': {}}

    row = execution.get_row_data()
    params = {
        'interface_type': interface_type,
        'real_time': real_time,
        'execute_type': execute_type,
        'environment': environment,
        'bank_code': cfg_db.bank_code or 'CCB',
        'online_bank_type': cfg_db.online_bank_type or 'B2C',
        'transfer_mode': cfg_db.transfer_mode or ('6' if channel == 'kls' else '7'),
        'busi_type': cfg_db.busi_type or '144',
        'channel_code': cfg_db.channel_code or ('kls' if channel == 'kls' else 'lepass'),
    }

    node_exec.add_log(f'执行代付: 渠道={channel} 环境={environment} 接口={interface_type}')

    from app.services.pay_service import execute_single_row
    result = execute_single_row(channel, cfg, row, params, log=node_exec.add_log)

    node_exec.add_log(f'执行结果: {"成功" if result.get("success") else "失败"} - {result.get("message", "")}')
    return result


def _execute_notify_node(execution, node, node_exec):
    """执行通知节点"""
    action = node.get('action', {})
    notify_type = action.get('notify_type', 'email')

    if notify_type == 'email':
        return _send_email_notification(execution, action, node_exec)
    return {'success': False, 'message': f'未知通知类型: {notify_type}', 'fields': {}}


def _send_email_notification(execution, action, node_exec):
    """发送邮件通知"""
    to_addresses = action.get('to_addresses', [])
    subject = action.get('subject', '代付流程通知')
    content = action.get('content', '')

    if not to_addresses:
        return {'success': False, 'message': '未配置收件人', 'fields': {}}

    from app.models.system_config import SystemConfig

    smtp_host_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_HOST).first()
    smtp_port_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PORT).first()
    smtp_user_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_USER).first()
    smtp_password_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PASSWORD).first()
    smtp_ssl_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_SSL).first()
    from_name_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_NAME).first()
    from_address_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_ADDRESS).first()

    if not smtp_host_config or not smtp_host_config.config_value:
        return {'success': False, 'message': 'SMTP主机未配置', 'fields': {}}
    if not smtp_user_config or not smtp_user_config.config_value:
        return {'success': False, 'message': 'SMTP用户未配置', 'fields': {}}

    host = smtp_host_config.config_value
    port = int(smtp_port_config.config_value) if smtp_port_config and smtp_port_config.config_value else 465
    user = smtp_user_config.config_value
    password = smtp_password_config.get_encrypted_value() if smtp_password_config else ''
    use_ssl = smtp_ssl_config.config_value.lower() in ('true', '1', 'yes') if smtp_ssl_config and smtp_ssl_config.config_value else True
    sender_name = from_name_config.config_value if from_name_config and from_name_config.config_value else '代付流程系统'
    sender_address = from_address_config.config_value if from_address_config and from_address_config.config_value else user

    ctx = execution.get_context()
    row_data = execution.get_row_data()
    row_dict = {
        'accountName': row_data[2] if len(row_data) > 2 else '',
        'businessNo': row_data[3] if len(row_data) > 3 else '',
        'amount': row_data[8] if len(row_data) > 8 else '',
    }

    for key, val in row_dict.items():
        content = content.replace(f'{{{key}}}', str(val))
    content = content.replace('{execution_id}', execution.execution_id)
    content = content.replace('{template_name}', execution.template_name)
    content = content.replace('{status}', execution.status)

    node_exec.add_log(f'发送邮件通知: 收件人={to_addresses} 主题={subject}')

    msg = MIMEMultipart()
    msg['From'] = formataddr((sender_name, sender_address))
    msg['To'] = ', '.join(to_addresses)
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=sender_address.split('@')[-1] if '@' in sender_address else 'localhost')
    msg['MIME-Version'] = '1.0'
    msg.attach(MIMEText(content, 'html', 'utf-8'))

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()

    server.login(user, password)
    refused = server.sendmail(sender_address, to_addresses, msg.as_string())
    server.quit()

    if refused:
        node_exec.add_log(f'部分收件人被拒绝: {refused}', level='warning')

    node_exec.add_log(f'邮件通知已发送至 {", ".join(to_addresses)}')
    return {'success': True, 'message': '邮件通知已发送', 'fields': {'to': to_addresses, 'subject': subject}}


def _replace_template_vars(text, execution, node, node_exec, notify_type, result=None):
    """替换模板变量

    支持变量:
    - 基础信息: {execution_id}, {template_name}, {status}, {node_name}, {notify_type}, {error_message}, {row_index}, {batch_id}
    - 行数据: {accountName}, {businessNo}, {amount}
    - 执行结果: {result.success}, {result.message}, {result.fields.xxx}
    - 上下文节点结果: {nodeId.fieldName}
    """
    if not text:
        return text
    row_data = execution.get_row_data()
    row_dict = {
        'accountName': row_data[2] if len(row_data) > 2 else '',
        'businessNo': row_data[3] if len(row_data) > 3 else '',
        'amount': row_data[8] if len(row_data) > 8 else '',
    }
    for key, val in row_dict.items():
        text = text.replace(f'{{{key}}}', str(val))
    text = text.replace('{execution_id}', execution.execution_id)
    text = text.replace('{template_name}', execution.template_name)
    text = text.replace('{status}', execution.status)
    text = text.replace('{node_name}', node.get('name', ''))
    text = text.replace('{notify_type}', notify_type)
    text = text.replace('{error_message}', node_exec.error_message or '')
    text = text.replace('{row_index}', str(execution.row_index))
    text = text.replace('{batch_id}', execution.batch_id or '')

    if result:
        text = text.replace('{result.success}', str(result.get('success', '')))
        text = text.replace('{result.message}', str(result.get('message', '')))
        result_fields = result.get('fields', {})
        if isinstance(result_fields, dict):
            for field_key, field_val in result_fields.items():
                text = text.replace(f'{{result.fields.{field_key}}}', str(field_val))

    context = execution.get_context()
    if context:
        import re
        pattern = r'\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_.]+)\}'
        matches = re.findall(pattern, text)
        for node_id, field_path in matches:
            if node_id in context:
                node_result = context[node_id]
                if isinstance(node_result, dict):
                    val = node_result
                    for part in field_path.split('.'):
                        if isinstance(val, dict):
                            val = val.get(part, '')
                        else:
                            val = ''
                            break
                    placeholder = '{' + node_id + '.' + field_path + '}'
                    text = text.replace(placeholder, str(val))
    return text


def _send_node_notification(execution, node, node_exec, notify_type, result=None):
    """发送节点通知（失败通知/结束通知）

    Args:
        execution: 流程实例
        node: 节点配置
        node_exec: 节点执行记录
        notify_type: '失败' 或 '完成'
        result: 当前节点执行结果（可选，用于模板变量替换）
    """
    action = node.get('action', {})
    notify_template_id = action.get('notify_template_id')

    # 如果配置了通知模板ID，从模板获取配置
    if notify_template_id:
        from app.models.pay_flow import PayFlowNotifyTemplate
        tpl = PayFlowNotifyTemplate.query.get(notify_template_id)
        if tpl and tpl.is_enabled:
            to_addresses = []
            receivers = tpl.receivers or ''
            if receivers:
                to_addresses = [addr.strip() for addr in receivers.split(',') if addr.strip()]
            subject = tpl.title or f'【代付流程{notify_type}】{execution.template_name}'
            content = tpl.content or ''
        else:
            node_exec.add_log(f'通知模板ID={notify_template_id}不存在或已禁用，跳过{notify_type}通知', level='warning')
            return
    else:
        to_addresses = action.get('to_addresses', [])

        # 支持从 to_addresses_str 解析
        if not to_addresses:
            to_addresses_str = action.get('to_addresses_str', '')
            if to_addresses_str:
                to_addresses = [addr.strip() for addr in to_addresses_str.split(',') if addr.strip()]

        if not to_addresses:
            node_exec.add_log(f'未配置收件人，跳过{notify_type}通知', level='warning')
            return

        subject = action.get('subject', f'【代付流程{notify_type}】{execution.template_name}')
        content = action.get('content', '')

    # 替换标题和正文中的模板变量
    subject = _replace_template_vars(subject, execution, node, node_exec, notify_type, result)
    content = _replace_template_vars(content, execution, node, node_exec, notify_type, result)

    # 构建邮件内容
    if not content:
        # 构建结果字段信息
        result_info = ''
        if result:
            result_info += f'<p><strong>执行结果:</strong> {"成功" if result.get("success") else "失败"}</p>'
            result_info += f'<p><strong>结果消息:</strong> {result.get("message", "")}</p>'
            result_fields = result.get('fields', {})
            if result_fields:
                result_info += '<p><strong>结果字段:</strong></p><ul>'
                for k, v in result_fields.items():
                    result_info += f'<li>{k}: {v}</li>'
                result_info += '</ul>'

        content = f'''
        <html>
        <body>
            <h3>代付流程{notify_type}通知</h3>
            <p><strong>模板名称:</strong> {execution.template_name}</p>
            <p><strong>执行ID:</strong> {execution.execution_id}</p>
            <p><strong>节点名称:</strong> {node.get('name', '')}</p>
            <p><strong>行序号:</strong> {execution.row_index}</p>
            <p><strong>状态:</strong> {execution.status}</p>
            <p><strong>时间:</strong> {beijing_isoformat(datetime.utcnow())}</p>
            <p><strong>账户名:</strong> {row_dict.get('accountName', '')}</p>
            <p><strong>商户号:</strong> {row_dict.get('businessNo', '')}</p>
            <p><strong>金额:</strong> {row_dict.get('amount', '')}</p>
            {f'<p><strong>错误信息:</strong> {node_exec.error_message}</p>' if node_exec.error_message else ''}
            {result_info}
        </body>
        </html>
        '''

    # 发送邮件
    from app.models.system_config import SystemConfig

    smtp_host_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_HOST).first()
    smtp_port_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PORT).first()
    smtp_user_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_USER).first()
    smtp_password_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PASSWORD).first()
    smtp_ssl_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_SSL).first()
    from_name_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_NAME).first()
    from_address_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_ADDRESS).first()

    if not smtp_host_config or not smtp_host_config.config_value:
        node_exec.add_log('SMTP主机未配置，无法发送通知', level='warning')
        return

    host = smtp_host_config.config_value
    port = int(smtp_port_config.config_value) if smtp_port_config and smtp_port_config.config_value else 465
    user = smtp_user_config.config_value if smtp_user_config and smtp_user_config.config_value else ''
    password = smtp_password_config.get_encrypted_value() if smtp_password_config else ''
    use_ssl = smtp_ssl_config.config_value.lower() in ('true', '1', 'yes') if smtp_ssl_config and smtp_ssl_config.config_value else True
    sender_name = from_name_config.config_value if from_name_config and from_name_config.config_value else '代付流程系统'
    sender_address = from_address_config.config_value if from_address_config and from_address_config.config_value else user

    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((sender_name, sender_address))
        msg['To'] = ', '.join(to_addresses)
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain=sender_address.split('@')[-1] if '@' in sender_address else 'localhost')
        msg['MIME-Version'] = '1.0'
        msg.attach(MIMEText(content, 'html', 'utf-8'))

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(user, password)
        server.sendmail(sender_address, to_addresses, msg.as_string())
        server.quit()

        node_exec.add_log(f'{notify_type}通知已发送至 {", ".join(to_addresses)}')
    except Exception as e:
        node_exec.add_log(f'发送{notify_type}通知失败: {e}', level='error')


def _resolve_next_node(execution, nodes, current_idx, transitions, result):
    """根据流转条件决定下一个节点索引

    transitions 格式:
    [
        {"condition": {"field": "nodeId.retCode", "operator": "eq", "value": "0000"}, "target_node_index": 2},
        {"condition": {"field": "nodeId.retCode", "operator": "neq", "value": "0000"}, "target_node_index": null},
    ]

    target_node_index:
        - int: 跳转到指定索引
        - null: 流程失败
        - 缺省: 顺序执行下一节点（仅当当前节点成功时）

    重要：当前节点失败时，流程必须立即停止（返回 None）
    资金安全：失败节点不允许通过流转条件继续执行
    """
    is_success = result.get('success', False)

    # 节点失败时，流程必须立即停止，不允许通过流转条件继续
    if not is_success:
        return None

    if not transitions:
        # 无流转条件时：成功则继续下一节点
        return current_idx + 1

    result_fields = result.get('fields', {})
    context = execution.get_context()

    for trans in transitions:
        condition = trans.get('condition', {})
        target = trans.get('target_node_index', current_idx + 1)

        if _evaluate_condition(condition, result, result_fields, context):
            return target

    # 无匹配条件时：成功则顺序继续下一节点
    return current_idx + 1


def _evaluate_condition(condition, result, result_fields, context=None):
    """评估单个条件

    支持两种字段引用方式:
    - 简单字段名: "retCode" - 从当前节点结果中查找
    - 节点引用: "nodeId.retCode" - 从上下文中指定节点的结果中查找
    """
    field_name = condition.get('field', '')
    operator = condition.get('operator', 'eq')
    expected = condition.get('value')

    # 特殊操作符：success/fail
    if operator == 'success':
        return result.get('success', False) == True
    if operator == 'fail':
        return result.get('success', False) == False

    actual = _resolve_field_value(field_name, result_fields, context)

    if actual is None:
        return False

    return _compare_values(actual, operator, expected)


def _resolve_field_value(field_name, result_fields, context):
    """解析字段值，支持 nodeId.fieldName 格式"""
    if not field_name:
        return None

    if '.' in field_name:
        node_id, sub_field = field_name.split('.', 1)
        if context and node_id in context:
            node_result = context[node_id]
            if isinstance(node_result, dict):
                return node_result.get(sub_field)
        return None
    else:
        return result_fields.get(field_name)


def _compare_values(actual, operator, expected):
    """比较值"""
    actual_str = str(actual)
    expected_str = str(expected) if expected is not None else ''

    if operator == 'eq':
        return actual_str == expected_str
    elif operator == 'neq':
        return actual_str != expected_str
    elif operator == 'contains':
        return expected_str in actual_str
    elif operator == 'not_contains':
        return expected_str not in actual_str
    elif operator == 'gt':
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == 'gte':
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == 'lt':
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == 'lte':
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False
    elif operator == 'in':
        if isinstance(expected, list):
            return actual_str in [str(v) for v in expected]
        elif isinstance(expected, str):
            return actual_str in [v.strip() for v in expected.split(',')]
        return actual_str == expected_str
    elif operator == 'not_in':
        if isinstance(expected, list):
            return actual_str not in [str(v) for v in expected]
        elif isinstance(expected, str):
            return actual_str not in [v.strip() for v in expected.split(',')]
        return actual_str != expected_str

    return False


def _evaluate_loop_exit(loop_cfg, result, result_fields, context):
    """评估循环退出条件

    支持多个条件，通过 exit_logic (and/or) 组合

    loop_cfg 格式:
    {
        "enabled": true,
        "interval_seconds": 60,
        "max_iterations": 10,
        "exit_logic": "and",
        "exit_conditions": [
            {"field": "nodeId.orderStatus", "operator": "eq", "value": "1"},
            {"field": "nodeId.retCode", "operator": "neq", "value": "0000"}
        ]
    }
    """
    exit_conditions = loop_cfg.get('exit_conditions', [])
    if not exit_conditions:
        return False

    exit_logic = loop_cfg.get('exit_logic', 'and')

    results = []
    for cond in exit_conditions:
        results.append(_evaluate_condition(cond, result, result_fields, context))

    if exit_logic == 'or':
        return any(results)
    else:
        return all(results)


def _complete_flow(execution, message):
    execution.status = 'completed'
    execution.completed_at = datetime.utcnow()
    execution.result_message = message
    logger.info(f'流程完成: {execution.execution_id} - {message}')


# ---------------------------------------------------------------------------
# 执行记录查询
# ---------------------------------------------------------------------------

def get_executions(batch_id=None, status=None, page=1, per_page=20):
    query = PayFlowExecution.query
    if batch_id:
        query = query.filter_by(batch_id=batch_id)
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(PayFlowExecution.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return {
        'items': [e.to_dict() for e in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
    }


def get_execution_detail(execution_id):
    execution = PayFlowExecution.query.filter_by(execution_id=execution_id).first()
    if not execution:
        return None

    nodes = PayFlowNodeExecution.query.filter_by(execution_id=execution_id)\
        .order_by(PayFlowNodeExecution.created_at.asc()).all()

    result = execution.to_dict()
    result['node_executions'] = [n.to_dict() for n in nodes]

    # 模板节点定义（用于前端走势动画）
    template = PayFlowTemplate.query.get(execution.template_id)
    if template:
        result['template_nodes'] = template.get_nodes()
    else:
        result['template_nodes'] = []

    return result


def get_batch_summary(batch_id):
    """获取批次摘要"""
    executions = PayFlowExecution.query.filter_by(batch_id=batch_id).all()
    total = len(executions)
    completed = sum(1 for e in executions if e.status == 'completed')
    failed = sum(1 for e in executions if e.status == 'failed')
    running = sum(1 for e in executions if e.status in ('running', 'waiting'))
    pending = sum(1 for e in executions if e.status == 'pending')
    cancelled = sum(1 for e in executions if e.status == 'cancelled')

    # 检查是否所有失败实例都在第一个节点失败（用于判断是否允许批次重试）
    all_failed_at_first_node = True
    if failed > 0:
        for e in executions:
            if e.status == 'failed' and e.current_node_index != 0:
                all_failed_at_first_node = False
                break

    return {
        'batch_id': batch_id,
        'total': total,
        'completed': completed,
        'failed': failed,
        'running': running,
        'pending': pending,
        'cancelled': cancelled,
        'progress': round((completed + failed) / total * 100, 1) if total > 0 else 0,
        'can_batch_retry': all_failed_at_first_node and failed > 0 and running == 0 and pending == 0,
    }


def get_batches(page=1, per_page=20, keyword=None, start_date=None, end_date=None):
    """获取批次列表（按 batch_id 聚合）"""
    from sqlalchemy import func, case

    # 子查询：获取每个 batch_id 的统计信息
    query_base = db.session.query(PayFlowExecution)
    if start_date:
        from datetime import datetime
        try:
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            query_base = query_base.filter(PayFlowExecution.created_at >= dt)
        except (ValueError, TypeError):
            pass
    if end_date:
        from datetime import datetime
        try:
            dt = datetime.strptime(end_date, '%Y-%m-%d')
            dt = dt.replace(hour=23, minute=59, second=59)
            query_base = query_base.filter(PayFlowExecution.created_at <= dt)
        except (ValueError, TypeError):
            pass

    subq = query_base.with_entities(
        PayFlowExecution.batch_id,
        func.count(PayFlowExecution.id).label('total'),
        func.sum(case((PayFlowExecution.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(case((PayFlowExecution.status == 'failed', 1), else_=0)).label('failed'),
        func.sum(case((PayFlowExecution.status.in_(['running', 'waiting']), 1), else_=0)).label('running'),
        func.sum(case((PayFlowExecution.status == 'pending', 1), else_=0)).label('pending'),
        func.sum(case((PayFlowExecution.status == 'cancelled', 1), else_=0)).label('cancelled'),
        func.max(PayFlowExecution.created_at).label('created_at'),
        func.max(PayFlowExecution.template_name).label('template_name'),
    ).group_by(PayFlowExecution.batch_id).subquery()

    query = db.session.query(subq)
    if keyword:
        query = query.filter(subq.c.template_name.contains(keyword))

    total = query.count()
    items = query.order_by(subq.c.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    batch_list = []
    for item in items:
        batch_id = item.batch_id
        total_count = int(item.total or 0)
        completed = int(item.completed or 0)
        failed = int(item.failed or 0)
        running = int(item.running or 0)
        pending = int(item.pending or 0)
        cancelled = int(item.cancelled or 0)

        # 检查是否所有失败实例都在第一个节点失败
        can_batch_retry = False
        if failed > 0 and running == 0 and pending == 0:
            failed_executions = PayFlowExecution.query.filter_by(batch_id=batch_id, status='failed').all()
            can_batch_retry = all(e.current_node_index == 0 for e in failed_executions)

        batch_list.append({
            'batch_id': batch_id,
            'template_name': item.template_name or '',
            'total': total_count,
            'completed': completed,
            'failed': failed,
            'running': running,
            'pending': pending,
            'cancelled': cancelled,
            'progress': round((completed + failed) / total_count * 100, 1) if total_count > 0 else 0,
            'created_at': beijing_isoformat(item.created_at),
            'can_batch_retry': can_batch_retry,
        })

    return {
        'items': batch_list,
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page if total > 0 else 0,
    }


def get_batch_detail(batch_id):
    """获取批次详情（含所有执行记录）"""
    summary = get_batch_summary(batch_id)
    if summary['total'] == 0:
        return None

    executions = PayFlowExecution.query.filter_by(batch_id=batch_id).order_by(
        PayFlowExecution.row_index.asc()
    ).all()

    return {
        **summary,
        'executions': [e.to_dict() for e in executions],
    }


def retry_batch(batch_id):
    """批次重试

    前提条件：批次内所有执行实例都必须在第一个节点失败
    （current_node_index == 0 且 status == 'failed'），且没有运行中/待执行的实例。

    Returns:
        (success: bool, message: str)
    """
    executions = PayFlowExecution.query.filter_by(batch_id=batch_id).all()
    if not executions:
        return False, '批次不存在或无执行记录'

    # 检查是否有运行中/待执行的实例
    running = [e for e in executions if e.status in ('running', 'waiting')]
    if running:
        return False, f'批次中有 {len(running)} 个实例正在运行中，无法重试'

    pending = [e for e in executions if e.status == 'pending']
    if pending:
        return False, f'批次中有 {len(pending)} 个实例待执行，无法重试'

    # 检查所有失败实例是否都在第一个节点
    failed_executions = [e for e in executions if e.status == 'failed']
    if not failed_executions:
        return False, '批次中没有失败的实例，无需重试'

    not_first_node = [e for e in failed_executions if e.current_node_index != 0]
    if not_first_node:
        return False, f'有 {len(not_first_node)} 个实例在非首节点失败，不满足批次重试条件（所有失败实例必须在第一个节点失败）'

    # 重置所有失败实例
    for execution in failed_executions:
        execution.status = 'pending'
        execution.error_message = None
        execution.current_node_index = 0
        execution.loop_node_id = None
        execution.loop_count = 0
        execution.next_run_at = None
        execution.completed_at = None
        execution.context = None
        execution.result_message = None
        # 重置汇总通知标记，批次重新完成后可再次触发汇总通知
        execution.summary_notify_sent = False
        # 清除节点执行记录
        PayFlowNodeExecution.query.filter_by(execution_id=execution.execution_id).delete()

    db.session.commit()
    logger.info(f'批次重试: batch_id={batch_id} 重置 {len(failed_executions)} 个实例')
    return True, f'已重置 {len(failed_executions)} 个实例，等待调度器执行'


def cancel_execution(execution_id):
    execution = PayFlowExecution.query.filter_by(execution_id=execution_id).first()
    if not execution:
        return False
    if execution.status in ('completed', 'failed', 'cancelled'):
        return False
    execution.status = 'cancelled'
    execution.completed_at = datetime.utcnow()
    db.session.commit()
    return True


def retry_execution(execution_id):
    """重试失败的流程实例"""
    execution = PayFlowExecution.query.filter_by(execution_id=execution_id).first()
    if not execution:
        return False
    if execution.status not in ('failed', 'cancelled'):
        return False
    execution.status = 'pending'
    execution.error_message = None
    execution.current_node_index = 0
    execution.loop_node_id = None
    execution.loop_count = 0
    execution.next_run_at = None
    execution.completed_at = None
    # 重置汇总通知标记，批次重新完成后可再次触发汇总通知
    execution.summary_notify_sent = False
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# 执行记录删除
# ---------------------------------------------------------------------------

def _delete_execution_record(execution: PayFlowExecution):
    """删除单个执行实例及其节点执行记录"""
    PayFlowNodeExecution.query.filter_by(execution_id=execution.execution_id).delete()
    db.session.delete(execution)


def delete_execution(execution_id):
    """删除单条执行记录（含节点执行日志）"""
    execution = PayFlowExecution.query.filter_by(execution_id=execution_id).first()
    if not execution:
        return False
    if execution.status in ('running', 'waiting'):
        return False
    _delete_execution_record(execution)
    db.session.commit()
    logger.info(f'删除代付流程执行记录: {execution_id}')
    return True


def batch_delete_executions(execution_ids):
    """批量删除执行记录（含节点执行日志）

    Returns:
        (deleted_count, skipped_ids) - 成功删除数量与被跳过的ID列表（运行中/不存在）
    """
    if not execution_ids:
        return 0, []
    deleted = 0
    skipped = []
    executions = PayFlowExecution.query.filter(PayFlowExecution.execution_id.in_(execution_ids)).all()
    found_ids = {e.execution_id for e in executions}
    for eid in execution_ids:
        if eid not in found_ids:
            skipped.append(eid)
    for execution in executions:
        if execution.status in ('running', 'waiting'):
            skipped.append(execution.execution_id)
            continue
        _delete_execution_record(execution)
        deleted += 1
    db.session.commit()
    logger.info(f'批量删除代付流程执行记录: 删除{deleted}条, 跳过{len(skipped)}条')
    return deleted, skipped
