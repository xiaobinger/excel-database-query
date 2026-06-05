import os
import time
import logging
from threading import Thread

logger = logging.getLogger(__name__)


def cleanup_old_files(app):
    with app.app_context():
        upload_folder = app.config.get('UPLOAD_FOLDER', './uploads')
        output_folder = app.config.get('OUTPUT_FOLDER', './outputs')
        retention_hours = app.config.get('FILE_RETENTION_HOURS', 24)
        retention_seconds = retention_hours * 3600
        now = time.time()
        cleaned = 0

        for folder in [upload_folder, output_folder]:
            if not os.path.exists(folder):
                continue
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if not os.path.isfile(filepath):
                    continue
                try:
                    file_age = now - os.path.getmtime(filepath)
                    if file_age > retention_seconds:
                        os.remove(filepath)
                        cleaned += 1
                        logger.info(f"清理过期文件: {filepath} (已存在{file_age/3600:.1f}小时)")
                except Exception as e:
                    logger.error(f"清理文件失败 {filepath}: {e}")

        if cleaned > 0:
            logger.info(f"文件清理完成，共清理 {cleaned} 个过期文件（保留{retention_hours}小时内）")
        return cleaned


def start_cleanup_scheduler(app):
    import sched

    scheduler = sched.scheduler(time.time, time.sleep)
    interval = 3600

    def run_cleanup():
        try:
            cleanup_old_files(app)
        except Exception as e:
            logger.error(f"定时清理任务异常: {e}")
        scheduler.enter(interval, 1, run_cleanup)

    def scheduler_loop():
        scheduler.enter(interval, 1, run_cleanup)
        scheduler.run()

    thread = Thread(target=scheduler_loop, daemon=True)
    thread.start()
    logger.info(f"文件定时清理已启动，每{interval}秒执行一次，文件保留{app.config.get('FILE_RETENTION_HOURS', 24)}小时")
