import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from flask import Blueprint, request, jsonify
from app import db
from app.models.system_config import SystemConfig
from app.utils.auth import admin_required

system_bp = Blueprint('system', __name__, url_prefix='/api/system')


@system_bp.route('/config', methods=['GET'])
@admin_required
def get_config():
    configs = SystemConfig.query.all()
    return jsonify({
        'success': True,
        'data': [c.to_dict() for c in configs],
    })


@system_bp.route('/config', methods=['PUT'])
@admin_required
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


@system_bp.route('/test-email', methods=['POST'])
@admin_required
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
    sender_name = from_name.config_value if from_name and from_name.config_value else 'Excel Query System'
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
