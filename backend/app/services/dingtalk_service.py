"""钉钉 Webhook 通知服务

支持：
- 加签验证（HMAC-SHA256）
- Markdown 消息
- @指定用户（通过手机号）
- 工单通知模板渲染
"""
import time
import hmac
import hashlib
import base64
import urllib.parse
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认通知模板
DEFAULT_TEMPLATES = {
    'assign': (
        "### 📋 工单提醒\n"
        "> **工单编号**：{ticket_no}\n"
        "> **标题**：{title}\n"
        "> **指派人**：{assignee_name}\n"
        "> **提交人**：{creator_name}\n"
        "\n请及时接收并处理该工单。"
    ),
    'complete': (
        "### ✅ 工单完成通知\n"
        "> **工单编号**：{ticket_no}\n"
        "> **标题**：{title}\n"
        "> **提交人**：{creator_name}\n"
        "> **指派人**：{assignee_name}\n"
        "\n工单已处理完成并通过质检验收，请知悉。"
    ),
}


def _get_dingtalk_config():
    """从 SystemConfig 读取钉钉配置"""
    from app.models.system_config import SystemConfig
    cfg = {}
    for key in ('dingtalk_webhook_url', 'dingtalk_secret', 'dingtalk_enabled'):
        row = SystemConfig.query.filter_by(config_key=key).first()
        if row:
            if key == 'dingtalk_secret':
                cfg[key] = row.get_encrypted_value()
            else:
                cfg[key] = row.config_value or ''
    return cfg


def _sign_url(webhook_url: str, secret: str) -> str:
    """钉钉加签：生成 timestamp + sign 参数"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = '&' if '?' in webhook_url else '?'
    return f"{webhook_url}{sep}timestamp={timestamp}&sign={sign}"


def send_dingtalk_markdown(title: str, text: str, at_mobiles: list = None, at_all: bool = False) -> bool:
    """发送钉钉 Markdown 消息

    Args:
        title: 消息标题（通知栏显示）
        text: Markdown 正文
        at_mobiles: 需要@的手机号列表
        at_all: 是否@所有人

    Returns:
        bool: 是否发送成功
    """
    cfg = _get_dingtalk_config()
    webhook_url = cfg.get('dingtalk_webhook_url', '')
    secret = cfg.get('dingtalk_secret', '')
    enabled = cfg.get('dingtalk_enabled', 'false').lower() in ('true', '1', 'yes')

    if not enabled:
        logger.debug('钉钉通知未启用，跳过')
        return False
    if not webhook_url:
        logger.warning('钉钉 Webhook 地址未配置，跳过通知')
        return False

    # 加签
    if secret:
        url = _sign_url(webhook_url, secret)
    else:
        url = webhook_url

    # 构建消息体
    at_mobiles = [m for m in (at_mobiles or []) if m]
    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text,
        },
        "at": {
            "atMobiles": at_mobiles,
            "isAtAll": at_all,
        },
    }

    try:
        resp = requests.post(url, json=body, timeout=10)
        result = resp.json()
        if result.get('errcode') != 0:
            logger.error(f'钉钉通知发送失败: {result}')
            return False
        logger.info(f'钉钉通知发送成功: {title}')
        return True
    except Exception as e:
        logger.error(f'钉钉通知发送异常: {e}')
        return False


def _render_template(template: str, context: dict) -> str:
    """渲染模板，替换 {key} 占位符"""
    try:
        return template.format(**context)
    except (KeyError, IndexError) as e:
        logger.warning(f'模板渲染失败: {e}，使用原始模板')
        return template


def notify_ticket_assigned(ticket) -> bool:
    """工单指派通知：通知指派人

    触发时机：工单提交/重新指派后
    @对象：指派人（user类型）
    """
    # 只通知 user 类型的指派人
    if ticket.assignee_type != 'user' or not ticket.assignee:
        return False

    assignee = ticket.assignee
    creator = ticket.creator

    context = {
        'ticket_no': ticket.ticket_no or f'#{ticket.id}',
        'title': ticket.title or '',
        'assignee_name': assignee.display_name or assignee.username or '',
        'creator_name': creator.display_name or creator.username or '' if creator else '',
        'content_preview': (ticket.content or '')[:100],
    }

    # 获取模板
    from app.models.system_config import SystemConfig
    tpl_row = SystemConfig.query.filter_by(config_key='dingtalk_template_assign').first()
    template = tpl_row.config_value if tpl_row and tpl_row.config_value else DEFAULT_TEMPLATES['assign']

    text = _render_template(template, context)

    # @指派人手机号
    at_mobiles = []
    if assignee.phone:
        at_mobiles.append(assignee.phone)
        # 在文本末尾追加 @手机号（钉钉要求文本中也要有 @手机号 才能高亮）
        text += f"\n\n@{assignee.phone}"

    title = f'工单提醒: {ticket.title[:30]}'
    return send_dingtalk_markdown(title, text, at_mobiles=at_mobiles)


def notify_ticket_completed(ticket) -> bool:
    """工单完成通知：质检验收通过后通知提交人

    触发时机：提交人核实通过（processed → closed）
    @对象：提交人
    """
    creator = ticket.creator
    if not creator:
        return False

    assignee_name = ''
    if ticket.assignee_type == 'ai':
        assignee_name = ticket.assignee_agent.name if ticket.assignee_agent else 'AI助手'
    else:
        assignee_name = ticket.assignee.display_name or ticket.assignee.username if ticket.assignee else ''

    context = {
        'ticket_no': ticket.ticket_no or f'#{ticket.id}',
        'title': ticket.title or '',
        'assignee_name': assignee_name,
        'creator_name': creator.display_name or creator.username or '',
        'processed_at': ticket.processed_at.strftime('%Y-%m-%d %H:%M') if ticket.processed_at else '',
    }

    # 获取模板
    from app.models.system_config import SystemConfig
    tpl_row = SystemConfig.query.filter_by(config_key='dingtalk_template_complete').first()
    template = tpl_row.config_value if tpl_row and tpl_row.config_value else DEFAULT_TEMPLATES['complete']

    text = _render_template(template, context)

    # @提交人手机号
    at_mobiles = []
    if creator.phone:
        at_mobiles.append(creator.phone)
        text += f"\n\n@{creator.phone}"

    title = f'工单完成: {ticket.title[:30]}'
    return send_dingtalk_markdown(title, text, at_mobiles=at_mobiles)


def notify_ticket_restarted(ticket, admin_name: str) -> bool:
    """工单重启通知：管理员重启已结束的工单

    触发时机：管理员重启 closed → submitted
    @对象：指派人（user类型）
    """
    if ticket.assignee_type != 'user' or not ticket.assignee:
        return False

    assignee = ticket.assignee
    context = {
        'ticket_no': ticket.ticket_no or f'#{ticket.id}',
        'title': ticket.title or '',
        'assignee_name': assignee.display_name or assignee.username or '',
        'admin_name': admin_name,
    }

    text = (
        f"### 🔄 工单重启通知\n"
        f"> **工单编号**：{context['ticket_no']}\n"
        f"> **标题**：{context['title']}\n"
        f"> **操作人**：{admin_name}（管理员）\n"
        f"\n该工单已被管理员重启，请重新处理。"
    )

    at_mobiles = []
    if assignee.phone:
        at_mobiles.append(assignee.phone)
        text += f"\n\n@{assignee.phone}"

    title = f'工单重启: {ticket.title[:30]}'
    return send_dingtalk_markdown(title, text, at_mobiles=at_mobiles)
