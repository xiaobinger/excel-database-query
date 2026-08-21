import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from flask import Blueprint, request, jsonify
from app import db
from app.models.system_config import SystemConfig
from app.utils.auth import permission_required, login_required, admin_required

system_bp = Blueprint('system', __name__, url_prefix='/api/system')

# ── 菜单配置 ──────────────────────────────────────────────

MENU_CONFIG_KEY = 'menu_config'

# 所有可用菜单项（供系统地图选择，来源于系统路由）
ALL_MENU_ITEMS = [
    {"path": "/", "title": "仪表盘", "icon": "fa-tachometer-alt", "permission": "dashboard", "affix": True},
    {"path": "/databases", "title": "数据库管理", "icon": "fa-database", "permission": "databases"},
    {"path": "/scripts", "title": "脚本管理", "icon": "fa-clipboard-list", "permission": "scripts"},
    {"path": "/query", "title": "查询执行", "icon": "fa-play-circle", "permission": "query"},
    {"path": "/history", "title": "执行历史", "icon": "fa-history", "permission": "history"},
    {"path": "/export-exec", "title": "导出任务", "icon": "fa-download", "permission": "export_exec"},
    {"path": "/profit-share", "title": "分润导出", "icon": "fa-hand-holding-usd", "permission": "profit_share"},
    {"path": "/auto-export", "title": "自动导出", "icon": "fa-clock", "permission": "auto_export"},
    {"path": "/ai-chat", "title": "AI 助手", "icon": "fa-robot", "permission": "ai_chat"},
    {"path": "/ai-sessions", "title": "AI会话管理", "icon": "fa-comments", "permission": "ai_sessions"},
    {"path": "/skills", "title": "Skills", "icon": "fa-brain", "permission": "skills"},
    {"path": "/system", "title": "系统配置", "icon": "fa-cog", "permission": "system"},
    {"path": "/users", "title": "用户管理", "icon": "fa-users", "permission": "users"},
    {"path": "/roles", "title": "角色管理", "icon": "fa-user-shield", "permission": "roles"},
    {"path": "/agents", "title": "Agent 管理", "icon": "fa-robot", "permission": "agent_manager"},
    {"path": "/mcp-servers", "title": "MCP 服务", "icon": "fa-plug", "permission": "mcp_servers"},
    {"path": "/cache-stats", "title": "缓存统计", "icon": "fa-bolt", "permission": "cache_stats"},
    {"path": "/business", "title": "业务系统", "icon": "fa-th-large", "permission": "business_systems"},
    {"path": "/system-tasks", "title": "系统任务", "icon": "fa-cogs", "permission": "system_tasks"},
    {"path": "/tickets", "title": "工单管理", "icon": "fa-ticket", "permission": "tickets"},
    {"path": "/system-map", "title": "系统地图", "icon": "fa-sitemap", "permission": "system_map"},
]

# 默认菜单配置
DEFAULT_MENU_CONFIG = [
    {"type": "item", "path": "/", "title": "仪表盘", "icon": "fa-tachometer-alt", "permission": "dashboard", "affix": True, "visible": True},
    {"type": "group", "title": "数据管理", "icon": "fa-database", "visible": True, "children": [
        {"path": "/databases", "title": "数据库管理", "icon": "fa-database", "permission": "databases", "visible": True},
        {"path": "/scripts", "title": "脚本管理", "icon": "fa-clipboard-list", "permission": "scripts", "visible": True},
    ]},
    {"type": "group", "title": "导出中心", "icon": "fa-download", "visible": True, "children": [
        {"path": "/query", "title": "查询执行", "icon": "fa-play-circle", "permission": "query", "visible": True},
        {"path": "/history", "title": "执行历史", "icon": "fa-history", "permission": "history", "visible": True},
        {"path": "/export-exec", "title": "导出任务", "icon": "fa-download", "permission": "export_exec", "visible": True},
        {"path": "/profit-share", "title": "分润导出", "icon": "fa-hand-holding-usd", "permission": "profit_share", "visible": True},
        {"path": "/auto-export", "title": "自动导出", "icon": "fa-clock", "permission": "auto_export", "visible": True},
    ]},
    {"type": "group", "title": "AI 智能", "icon": "fa-robot", "visible": True, "children": [
        {"path": "/ai-chat", "title": "AI 助手", "icon": "fa-robot", "permission": "ai_chat", "visible": True},
        {"path": "/ai-sessions", "title": "AI会话管理", "icon": "fa-comments", "permission": "ai_sessions", "visible": True},
        {"path": "/skills", "title": "Skills", "icon": "fa-brain", "permission": "skills", "visible": True},
    ]},
    {"type": "group", "title": "系统管理", "icon": "fa-cog", "visible": True, "children": [
        {"path": "/system", "title": "系统配置", "icon": "fa-cog", "permission": "system", "visible": True},
        {"path": "/users", "title": "用户管理", "icon": "fa-users", "permission": "users", "visible": True},
        {"path": "/roles", "title": "角色管理", "icon": "fa-user-shield", "permission": "roles", "visible": True},
        {"path": "/agents", "title": "Agent 管理", "icon": "fa-robot", "permission": "agent_manager", "visible": True},
        {"path": "/mcp-servers", "title": "MCP 服务", "icon": "fa-plug", "permission": "mcp_servers", "visible": True},
        {"path": "/cache-stats", "title": "缓存统计", "icon": "fa-bolt", "permission": "cache_stats", "visible": True},
        {"path": "/business", "title": "业务系统", "icon": "fa-th-large", "permission": "business_systems", "visible": True},
        {"path": "/system-tasks", "title": "系统任务", "icon": "fa-cogs", "permission": "system_tasks", "visible": True},
        {"path": "/tickets", "title": "工单管理", "icon": "fa-ticket", "permission": "tickets", "visible": True},
        {"path": "/system-map", "title": "系统地图", "icon": "fa-sitemap", "permission": "system_map", "visible": True},
    ]},
]


@system_bp.route('/config', methods=['GET'])
@permission_required('system')
def get_config():
    configs = SystemConfig.query.all()
    return jsonify({
        'success': True,
        'data': [c.to_dict() for c in configs],
    })


@system_bp.route('/config', methods=['PUT'])
@permission_required('system')
def update_config():
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    items = data.get('items', [])
    for item in items:
        key = item.get('key')
        value = item.get('value')
        if not key:
            continue

        config = SystemConfig.query.filter_by(config_key=key).first()
        if not config:
            config = SystemConfig(config_key=key)
            db.session.add(config)

        if key == SystemConfig.EMAIL_SMTP_PASSWORD:
            if value:
                config.set_encrypted_value(value)
            config.config_value = None
        else:
            config.config_value = str(value) if value is not None else None

    db.session.commit()

    configs = SystemConfig.query.all()
    return jsonify({
        'success': True,
        'data': [c.to_dict() for c in configs],
        'message': '配置已更新',
    })


@system_bp.route('/config/batch-delete', methods=['POST'])
@permission_required('system')
def batch_delete_configs():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    deleted_count = 0
    for config_id in ids:
        config = SystemConfig.query.get(config_id)
        if config:
            db.session.delete(config)
            deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个配置', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@system_bp.route('/config/all', methods=['DELETE'])
@permission_required('system')
def delete_all_configs():
    try:
        deleted_count = SystemConfig.query.delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个配置', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@system_bp.route('/test-email', methods=['POST'])
@permission_required('system')
def test_email():
    data = request.get_json()
    if not data or not data.get('recipient'):
        return jsonify({'success': False, 'message': '请提供收件人邮箱'}), 400

    recipient = data.get('recipient')

    smtp_host = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_HOST).first()
    smtp_port = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PORT).first()
    smtp_user = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_USER).first()
    smtp_password = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PASSWORD).first()
    smtp_ssl = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_SSL).first()
    from_name = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_NAME).first()
    from_address = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_ADDRESS).first()

    if not smtp_host or not smtp_host.config_value:
        return jsonify({'success': False, 'message': 'SMTP主机未配置'}), 400
    if not smtp_user or not smtp_user.config_value:
        return jsonify({'success': False, 'message': 'SMTP用户未配置'}), 400
    if not smtp_password or not smtp_password.get_encrypted_value():
        return jsonify({'success': False, 'message': 'SMTP密码未配置'}), 400

    host = smtp_host.config_value
    port = int(smtp_port.config_value) if smtp_port and smtp_port.config_value else 465
    user = smtp_user.config_value
    password = smtp_password.get_encrypted_value()
    use_ssl = smtp_ssl.config_value.lower() in ('true', '1', 'yes') if smtp_ssl and smtp_ssl.config_value else True
    sender_name = from_name.config_value if from_name and from_name.config_value else '综合运营管理系统'
    sender_address = from_address.config_value if from_address and from_address.config_value else user

    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((sender_name, sender_address))
        msg['To'] = recipient
        msg['Subject'] = '测试邮件 - Excel Database Query System'
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain=sender_address.split('@')[-1] if '@' in sender_address else 'localhost')
        msg['MIME-Version'] = '1.0'
        msg.attach(MIMEText('这是一封测试邮件，如果您收到此邮件，说明邮件配置正确。', 'plain', 'utf-8'))

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(user, password)
        refused = server.sendmail(sender_address, [recipient], msg.as_string())
        if refused:
            return jsonify({'success': False, 'message': f'收件人被拒绝: {refused}'}), 500
        server.quit()

        return jsonify({'success': True, 'message': '测试邮件发送成功，请检查收件箱（含垃圾邮件文件夹）'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'邮件发送失败: {str(e)}'}), 500


# ── 菜单配置 API ──────────────────────────────────────────

@system_bp.route('/menu-config', methods=['GET'])
@login_required
def get_menu_config():
    """获取菜单配置（登录用户可访问，用于渲染侧边栏）"""
    config = SystemConfig.query.filter_by(config_key=MENU_CONFIG_KEY).first()
    if config and config.config_value:
        try:
            menu_config = json.loads(config.config_value)
            return jsonify({'success': True, 'data': menu_config})
        except json.JSONDecodeError:
            pass
    return jsonify({'success': True, 'data': DEFAULT_MENU_CONFIG})


@system_bp.route('/menu-config', methods=['PUT'])
@admin_required
def update_menu_config():
    """保存菜单配置（仅管理员）"""
    data = request.get_json()
    if not data or 'menu_config' not in data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    menu_config = data.get('menu_config')
    if not isinstance(menu_config, list):
        return jsonify({'success': False, 'message': '菜单配置必须是数组'}), 400

    config = SystemConfig.query.filter_by(config_key=MENU_CONFIG_KEY).first()
    if not config:
        config = SystemConfig(config_key=MENU_CONFIG_KEY, description='菜单配置')
        db.session.add(config)
    config.config_value = json.dumps(menu_config, ensure_ascii=False)
    db.session.commit()

    return jsonify({'success': True, 'message': '菜单配置已更新', 'data': menu_config})


@system_bp.route('/menu-items', methods=['GET'])
@admin_required
def get_menu_items():
    """获取所有可用菜单项（供系统地图选择，仅管理员）"""
    return jsonify({'success': True, 'data': ALL_MENU_ITEMS})
