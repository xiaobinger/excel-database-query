import logging
import os
import smtplib
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from croniter import croniter
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate, make_msgid

logger = logging.getLogger(__name__)

_scheduler_thread = None
_scheduler_lock = threading.Lock()
_running = False


def resolve_auto_params(auto_params: dict) -> dict:
    from app.utils.helpers import beijing_now
    import calendar
    from datetime import timedelta
    now = beijing_now()
    resolved = {}
    for param_name, expression in auto_params.items():
        if not isinstance(expression, str):
            resolved[param_name] = expression
            continue
        expr = expression.strip().lower()
        if expr == 'current_year':
            resolved[param_name] = now.strftime('%Y')
        elif expr == 'last_year':
            resolved[param_name] = str(now.year - 1)
        elif expr == 'current_month':
            resolved[param_name] = now.strftime('%Y-%m')
        elif expr == 'last_month':
            if now.month == 1:
                resolved[param_name] = f'{now.year - 1}-12'
            else:
                resolved[param_name] = f'{now.year}-{now.month - 1:02d}'
        elif expr == 'current_day':
            resolved[param_name] = now.strftime('%Y-%m-%d')
        elif expr == 'last_day':
            yesterday = now - timedelta(days=1)
            resolved[param_name] = yesterday.strftime('%Y-%m-%d')
        elif expr == 'current_datetime':
            resolved[param_name] = now.strftime('%Y-%m-%d %H:%M:%S')
        elif expr == 'current_month_start':
            resolved[param_name] = now.strftime('%Y-%m-01')
        elif expr == 'last_month_start':
            if now.month == 1:
                resolved[param_name] = f'{now.year - 1}-12-01'
            else:
                resolved[param_name] = f'{now.year}-{now.month - 1:02d}-01'
        elif expr == 'last_month_end':
            if now.month == 1:
                resolved[param_name] = f'{now.year - 1}-12-31'
            else:
                last_day = calendar.monthrange(now.year, now.month - 1)[1]
                resolved[param_name] = f'{now.year}-{now.month - 1:02d}-{last_day}'
        elif expr == 'range_current_month':
            last_day = calendar.monthrange(now.year, now.month)[1]
            resolved[f'{param_name}_start'] = now.strftime('%Y-%m-01')
            resolved[f'{param_name}_end'] = f'{now.strftime("%Y-%m")}-{last_day}'
        elif expr == 'range_last_month':
            if now.month == 1:
                ly, lm = now.year - 1, 12
            else:
                ly, lm = now.year, now.month - 1
            last_day = calendar.monthrange(ly, lm)[1]
            resolved[f'{param_name}_start'] = f'{ly}-{lm:02d}-01'
            resolved[f'{param_name}_end'] = f'{ly}-{lm:02d}-{last_day}'
        elif expr == 'range_current_year':
            resolved[f'{param_name}_start'] = f'{now.year}-01-01'
            resolved[f'{param_name}_end'] = f'{now.year}-12-31'
        elif expr == 'range_last_year':
            resolved[f'{param_name}_start'] = f'{now.year - 1}-01-01'
            resolved[f'{param_name}_end'] = f'{now.year - 1}-12-31'
        elif expr == 'range_current_quarter':
            q = (now.month - 1) // 3
            q_start_month = q * 3 + 1
            q_end_month = q_start_month + 2
            last_day = calendar.monthrange(now.year, q_end_month)[1]
            resolved[f'{param_name}_start'] = f'{now.year}-{q_start_month:02d}-01'
            resolved[f'{param_name}_end'] = f'{now.year}-{q_end_month:02d}-{last_day}'
        elif expr == 'range_last_quarter':
            q = (now.month - 1) // 3
            if q == 0:
                ly, lq_start = now.year - 1, 10
            else:
                ly, lq_start = now.year, (q - 1) * 3 + 1
            lq_end = lq_start + 2
            last_day = calendar.monthrange(ly, lq_end)[1]
            resolved[f'{param_name}_start'] = f'{ly}-{lq_start:02d}-01'
            resolved[f'{param_name}_end'] = f'{ly}-{lq_end:02d}-{last_day}'
        elif expr == 'range_last_7_days':
            start = now - timedelta(days=7)
            resolved[f'{param_name}_start'] = start.strftime('%Y-%m-%d')
            resolved[f'{param_name}_end'] = now.strftime('%Y-%m-%d')
        elif expr == 'range_last_30_days':
            start = now - timedelta(days=30)
            resolved[f'{param_name}_start'] = start.strftime('%Y-%m-%d')
            resolved[f'{param_name}_end'] = now.strftime('%Y-%m-%d')
        else:
            resolved[param_name] = expression
    return resolved


def start_auto_export_scheduler(app):
    global _scheduler_thread, _running
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        _running = True
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(app,),
            daemon=True,
            name='auto-export-scheduler'
        )
        _scheduler_thread.start()
        logger.info('自动导出调度器已启动')


def stop_auto_export_scheduler():
    global _running
    _running = False


def _scheduler_loop(app):
    while _running:
        try:
            _check_and_execute(app)
        except Exception as e:
            logger.error(f'自动导出调度器异常: {e}', exc_info=True)
        time.sleep(30)


def _check_and_execute(app):
    with app.app_context():
        from app.models.auto_export_task import AutoExportTask
        from app.services.export_service import ExportService
        from app.utils.helpers import beijing_now, utc_to_beijing

        now = beijing_now()
        tasks = AutoExportTask.query.filter_by(is_enabled=True).all()

        for auto_task in tasks:
            try:
                cron = croniter(auto_task.cron_expression, now)
                prev_run = cron.get_prev(datetime)
                last_run_bj = utc_to_beijing(auto_task.last_run_at) if auto_task.last_run_at else datetime(2000, 1, 1, tzinfo=timezone(timedelta(hours=8)))
                if prev_run > last_run_bj:
                    if abs((now - prev_run).total_seconds()) <= 60:
                        _execute_auto_task(app, auto_task)
            except Exception as e:
                logger.error(f'自动导出任务 [{auto_task.name}] 检查失败: {e}')

            try:
                cron = croniter(auto_task.cron_expression, now)
                next_run_bj = cron.get_next(datetime)
                auto_task.next_run_at = next_run_bj.astimezone(timezone.utc).replace(tzinfo=None) if hasattr(next_run_bj, 'astimezone') else next_run_bj
            except Exception:
                auto_task.next_run_at = None

        from app import db
        db.session.commit()


def _execute_auto_task(app, auto_task):
    from app import db
    from app.models.auto_export_task import AutoExportTask
    from app.models.script import Script
    from app.services.export_service import ExportService

    script_ids = auto_task.get_script_ids()
    if not script_ids:
        logger.warning(f'自动导出任务 [{auto_task.name}] 没有关联导出选项')
        return

    for sid in script_ids:
        script = Script.query.get(sid)
        if not script or script.type != 'export':
            logger.warning(f'自动导出任务 [{auto_task.name}] 导出选项 {sid} 不存在或类型不正确')
            return

    auto_params = auto_task.get_auto_params()
    params_values = resolve_auto_params(auto_params)

    output_dir = app.config['OUTPUT_FOLDER']
    os.makedirs(output_dir, exist_ok=True)

    try:
        task = ExportService.create_export_task(
            script_ids=script_ids,
            params_values=params_values,
            output_format=auto_task.output_format or 'sheets',
            created_by=auto_task.created_by,
        )
        task.is_auto = True
        task.auto_task_id = auto_task.id
        db.session.commit()

        auto_task.last_run_at = datetime.utcnow()
        auto_task.last_run_status = 'triggered'
        auto_task.last_task_id = task.task_id
        db.session.commit()

        logger.info(f'自动导出任务 [{auto_task.name}] 已触发, task_id={task.task_id}')

        ExportService.execute_export_async(
            task_id=task.task_id,
            script_ids=script_ids,
            params_values=params_values,
            output_dir=output_dir,
            output_format=auto_task.output_format or 'sheets',
            on_complete=lambda tid, tstatus: _on_export_complete(app, auto_task.id, tid, tstatus),
        )
    except Exception as e:
        auto_task.last_run_at = datetime.utcnow()
        auto_task.last_run_status = 'failed'
        db.session.commit()
        logger.error(f'自动导出任务 [{auto_task.name}] 触发失败: {e}')
        send_auto_export_notification(app, auto_task, None, 'failed')


def _on_export_complete(app, auto_task_id, task_id, task_status):
    with app.app_context():
        from app.models.auto_export_task import AutoExportTask
        from app.models.query_task import QueryTask
        auto_task = AutoExportTask.query.get(auto_task_id)
        if not auto_task:
            return
        query_task = QueryTask.query.filter_by(task_id=task_id).first() if task_id else None
        send_auto_export_notification(app, auto_task, query_task, task_status)


def send_auto_export_notification(app, auto_task, query_task, status):
    if not auto_task.notify_enabled:
        return

    try:
        from app.models.system_config import SystemConfig
        from app.models.script import Script
        from app.utils.helpers import format_beijing

        smtp_host_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_HOST).first()
        smtp_port_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PORT).first()
        smtp_user_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_USER).first()
        smtp_password_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_PASSWORD).first()
        smtp_ssl_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_SMTP_SSL).first()
        from_name_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_NAME).first()
        from_address_config = SystemConfig.query.filter_by(config_key=SystemConfig.EMAIL_FROM_ADDRESS).first()

        if not smtp_host_config or not smtp_host_config.config_value:
            logger.warning('邮件通知: SMTP主机未配置，跳过通知')
            return
        if not smtp_user_config or not smtp_user_config.config_value:
            logger.warning('邮件通知: SMTP用户未配置，跳过通知')
            return
        if not smtp_password_config or not smtp_password_config.get_encrypted_value():
            logger.warning('邮件通知: SMTP密码未配置，跳过通知')
            return

        host = smtp_host_config.config_value
        port = int(smtp_port_config.config_value) if smtp_port_config and smtp_port_config.config_value else 465
        user = smtp_user_config.config_value
        password = smtp_password_config.get_encrypted_value()
        use_ssl = smtp_ssl_config.config_value.lower() in ('true', '1', 'yes') if smtp_ssl_config and smtp_ssl_config.config_value else True
        sender_name = from_name_config.config_value if from_name_config and from_name_config.config_value else 'Excel Database Query'
        sender_address = from_address_config.config_value if from_address_config and from_address_config.config_value else user

        emails = auto_task.get_notify_emails()
        if not emails:
            logger.warning(f'自动导出任务 [{auto_task.name}] 未配置通知邮箱，跳过通知')
            return

        status_text = '执行成功' if status in ('triggered', 'completed') else '执行失败'
        status_color = '#67c23a' if status in ('triggered', 'completed') else '#f56c6c'
        subject = auto_task.name

        auto_params = auto_task.get_auto_params()
        resolved_params = resolve_auto_params(auto_params)

        param_label_map = {}
        try:
            script_ids = auto_task.get_script_ids()
            for sid in script_ids:
                script = Script.query.get(sid)
                if script:
                    for p in script.get_params_config():
                        if p.get('name') and p.get('label'):
                            param_label_map[p['name']] = p['label']
        except Exception:
            pass

        param_rows_html = ''
        if resolved_params:
            param_rows = []
            for k, v in resolved_params.items():
                display_name = param_label_map.get(k, k)
                param_rows.append(f'<tr><td style="padding:8px 16px;border-bottom:1px solid #ebeef5;font-weight:600;color:#303133;">{display_name}</td><td style="padding:8px 16px;border-bottom:1px solid #ebeef5;color:#606266;">{v}</td></tr>')
            param_rows_html = '''
            <tr>
              <td style="padding:12px 16px;color:#909399;font-weight:600;vertical-align:top;width:100px;">参数设置</td>
              <td style="padding:12px 16px;">
                <table style="width:100%;border-collapse:collapse;border:1px solid #ebeef5;border-radius:4px;overflow:hidden;">
                  <tr style="background:#f5f7fa;"><th style="padding:8px 16px;text-align:left;border-bottom:1px solid #ebeef5;color:#909399;font-size:13px;">参数名称</th><th style="padding:8px 16px;text-align:left;border-bottom:1px solid #ebeef5;color:#909399;font-size:13px;">参数值</th></tr>
                  {param_rows}
                </table>
              </td>
            </tr>'''.format(param_rows=''.join(param_rows))

        attach_info = ''
        if auto_task.notify_attach_file and query_task and query_task.output_file and os.path.exists(query_task.output_file):
            attach_info = '<tr><td style="padding:12px 16px;color:#909399;font-weight:600;vertical-align:top;width:100px;">结果文件</td><td style="padding:12px 16px;color:#67c23a;">已作为附件发送</td></tr>'

        html_body = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:'Microsoft YaHei','Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fa;padding:32px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
      <tr>
        <td style="background:linear-gradient(135deg,#409eff,#66b1ff);padding:24px 32px;">
          <h2 style="margin:0;color:#fff;font-size:20px;font-weight:600;">{task_name}</h2>
        </td>
      </tr>
      <tr>
        <td style="padding:24px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <td style="padding:12px 16px;color:#909399;font-weight:600;vertical-align:top;width:100px;">执行状态</td>
              <td style="padding:12px 16px;"><span style="display:inline-block;padding:4px 12px;border-radius:4px;color:#fff;font-size:13px;font-weight:600;background:{status_color};">{status_text}</span></td>
            </tr>
            <tr>
              <td style="padding:12px 16px;color:#909399;font-weight:600;vertical-align:top;width:100px;">执行时间</td>
              <td style="padding:12px 16px;color:#303133;">{exec_time}</td>
            </tr>
            {desc_row}
            {task_id_row}
            {param_rows_html}
            {attach_info}
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding:16px 32px;background:#fafafa;border-top:1px solid #ebeef5;text-align:center;">
          <p style="margin:0;color:#c0c4cc;font-size:12px;">此邮件由系统自动发送，请勿回复</p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>'''.format(
            task_name=auto_task.name,
            status_text=status_text,
            status_color=status_color,
            exec_time=format_beijing(datetime.utcnow()),
            desc_row=f'<tr><td style="padding:12px 16px;color:#909399;font-weight:600;vertical-align:top;width:100px;">任务描述</td><td style="padding:12px 16px;color:#606266;">{auto_task.description}</td></tr>' if auto_task.description else '',
            task_id_row=f'<tr><td style="padding:12px 16px;color:#909399;font-weight:600;vertical-align:top;width:100px;">任务ID</td><td style="padding:12px 16px;color:#606266;font-family:Consolas,Monaco,monospace;">{query_task.task_id}</td></tr>' if query_task else '',
            param_rows_html=param_rows_html,
            attach_info=attach_info,
        )

        msg = MIMEMultipart()
        msg['From'] = formataddr((sender_name, sender_address))
        msg['To'] = ', '.join(emails)
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain=sender_address.split('@')[-1] if '@' in sender_address else 'localhost')
        msg['MIME-Version'] = '1.0'
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        if auto_task.notify_attach_file and query_task and query_task.output_file:
            file_path = query_task.output_file
            if os.path.exists(file_path):
                logger.info(f'邮件通知: 准备附加文件 {file_path} (大小: {os.path.getsize(file_path)} bytes)')
                with open(file_path, 'rb') as f:
                    attachment = MIMEBase('application', 'octet-stream')
                    attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file_path))
                msg.attach(attachment)
            else:
                logger.warning(f'邮件通知: 附件文件不存在 {file_path}')

        logger.info(f'邮件通知: 连接SMTP {host}:{port} (SSL={use_ssl}), 发件人={sender_address}, 收件人={emails}')

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(user, password)
        refused = server.sendmail(sender_address, emails, msg.as_string())
        if refused:
            logger.warning(f'邮件通知: 部分收件人被拒绝: {refused}')
        server.quit()

        logger.info(f'自动导出任务 [{auto_task.name}] 邮件通知已发送至 {", ".join(emails)}')
    except Exception as e:
        logger.error(f'自动导出任务 [{auto_task.name}] 邮件通知发送失败: {e}')
