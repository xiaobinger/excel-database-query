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
from app.models.pay_flow import PayFlowTemplate, PayFlowExecution, PayFlowNodeExecution
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

def get_templates(page=1, per_page=20, keyword=None):
    query = PayFlowTemplate.query
    if keyword:
        query = query.filter(PayFlowTemplate.name.contains(keyword))
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
        created_by: 创建用户ID

    Returns:
        batch_id, [execution_id, ...]
    """
    template = PayFlowTemplate.query.get(template_id)
    if not template or not template.is_enabled:
        raise ValueError('流程模板不存在或未启用')

    batch_id = uuid.uuid4().hex
    execution_ids = []

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
        )
        execution.set_row_data(row)
        execution.set_context({})
        db.session.add(execution)
        execution_ids.append(execution_id)

    db.session.commit()
    logger.info(f'发起代付流程: template={template.name} batch_id={batch_id} 数据行数={len(rows)}')
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

    安全：通过状态检查防止同一执行实例被重复处理（资金安全）
    """
    execution = PayFlowExecution.query.filter_by(execution_id=execution_id).first()
    if not execution:
        return

    # 安全检查：只处理 pending 或 waiting 状态的实例
    # 防止同一行数据被重复执行（涉及资金安全）
    if execution.status not in ('pending', 'waiting'):
        logger.warning(f'流程 {execution_id} 状态为 {execution.status}，跳过执行')
        return

    # 对于 waiting 状态，检查是否到达下次执行时间
    if execution.status == 'waiting':
        if execution.next_run_at and execution.next_run_at > datetime.utcnow():
            return

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
            db.session.commit()
            advance_flow(execution_id)
            return

    # 安全检查：检查是否已有该节点的 running 记录（防止重复执行）
    # 这是资金安全的最后一道防线
    existing_running = PayFlowNodeExecution.query.filter_by(
        execution_id=execution_id,
        node_id=node_id,
        status='running'
    ).first()
    if existing_running:
        logger.warning(f'流程 {execution_id} 节点 {node_name} 已有 running 记录，跳过重复执行')
        return

    # 执行节点
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

    execution.status = 'running'
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
            # 无匹配条件，流程失败
            execution.status = 'failed'
            execution.error_message = f'节点 {node_name} 无匹配的流转条件'
            execution.completed_at = datetime.utcnow()
            # 发送失败通知
            if node.get('notify_on_failure'):
                _send_node_notification(execution, node, node_exec, '失败', result)
        elif is_end_node:
            # 结束节点：流程完成
            execution.current_node_index = current_idx + 1
            _complete_flow(execution, f'流程完成（结束节点: {node_name}）')
            # 发送结束通知
            if node.get('notify_on_end'):
                _send_node_notification(execution, node, node_exec, '完成', result)
        elif next_idx >= len(nodes):
            # 到达末尾
            execution.current_node_index = next_idx
            _complete_flow(execution, f'流程完成，最后节点: {node_name}')
        else:
            execution.current_node_index = next_idx
            execution.loop_node_id = None
            execution.loop_count = 0
            db.session.commit()
            # 立即推进下一节点
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


def _send_node_notification(execution, node, node_exec, notify_type, result=None):
    """发送节点通知（失败通知/结束通知）

    Args:
        execution: 流程实例
        node: 节点配置
        node_exec: 节点执行记录
        notify_type: '失败' 或 '完成'
        result: 当前节点执行结果（可选，用于模板变量替换）

    支持的模板变量:
    - 基础信息: {execution_id}, {template_name}, {status}, {node_name}, {notify_type}, {error_message}, {row_index}, {batch_id}
    - 行数据: {accountName}, {businessNo}, {amount}
    - 执行结果: {result.success}, {result.message}, 以及 result.fields 中的所有字段
    - 上下文节点结果: {nodeId.fieldName} 格式引用任意节点的结果字段
    """
    action = node.get('action', {})
    to_addresses = action.get('to_addresses', [])

    # 支持从 to_addresses_str 解析
    if not to_addresses:
        to_addresses_str = action.get('to_addresses_str', '')
        if to_addresses_str:
            to_addresses = [addr.strip() for addr in to_addresses_str.split(',') if addr.strip()]

    if not to_addresses:
        node_exec.add_log(f'未配置收件人，跳过{notify_type}通知', level='warning')
        return

    # 构建通知内容
    subject_prefix = '【代付流程失败】' if notify_type == '失败' else '【代付流程完成】'
    subject = action.get('subject', f'{subject_prefix} {execution.template_name}')
    content = action.get('content', '')

    # 替换变量
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
    content = content.replace('{node_name}', node.get('name', ''))
    content = content.replace('{notify_type}', notify_type)
    content = content.replace('{error_message}', node_exec.error_message or '')
    content = content.replace('{row_index}', str(execution.row_index))
    content = content.replace('{batch_id}', execution.batch_id or '')

    # 替换当前节点执行结果变量
    if result:
        content = content.replace('{result.success}', str(result.get('success', '')))
        content = content.replace('{result.message}', str(result.get('message', '')))
        # 替换 result.fields 中的所有字段
        result_fields = result.get('fields', {})
        if isinstance(result_fields, dict):
            for field_key, field_val in result_fields.items():
                content = content.replace(f'{{result.fields.{field_key}}}', str(field_val))

    # 替换上下文节点结果变量（nodeId.fieldName 格式）
    context = execution.get_context()
    if context:
        # 收集所有 nodeId.fieldName 格式的变量引用
        import re
        pattern = r'\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_.]+)\}'
        matches = re.findall(pattern, content)
        for node_id, field_path in matches:
            if node_id in context:
                node_result = context[node_id]
                if isinstance(node_result, dict):
                    # 支持嵌套路径如 data.orderNo
                    val = node_result
                    for part in field_path.split('.'):
                        if isinstance(val, dict):
                            val = val.get(part, '')
                        else:
                            val = ''
                            break
                    placeholder = '{' + node_id + '.' + field_path + '}'
                    content = content.replace(placeholder, str(val))

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

    重要：当前节点失败时，若无匹配流转条件，流程应停止（返回 None）
    """
    is_success = result.get('success', False)

    if not transitions:
        # 无流转条件时：成功则继续下一节点，失败则流程停止
        return current_idx + 1 if is_success else None

    result_fields = result.get('fields', {})
    context = execution.get_context()

    for trans in transitions:
        condition = trans.get('condition', {})
        target = trans.get('target_node_index', current_idx + 1)

        if _evaluate_condition(condition, result, result_fields, context):
            return target

    # 无匹配条件时：成功则继续下一节点，失败则流程停止
    return current_idx + 1 if is_success else None


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

    return {
        'batch_id': batch_id,
        'total': total,
        'completed': completed,
        'failed': failed,
        'running': running,
        'pending': pending,
        'progress': round((completed + failed) / total * 100, 1) if total > 0 else 0,
    }


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
    db.session.commit()
    return True
