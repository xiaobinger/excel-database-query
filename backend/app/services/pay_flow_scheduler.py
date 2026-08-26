"""代付流程调度器

后台线程定期检查并推进所有进行中的流程实例：
- 推进 pending 状态的实例
- 检查 waiting 状态的实例是否到达下次执行时间
"""
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_scheduler_thread = None
_scheduler_lock = threading.Lock()
_running = False


def start_pay_flow_scheduler(app):
    global _scheduler_thread, _running
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        _running = True
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(app,),
            daemon=True,
            name='pay-flow-scheduler'
        )
        _scheduler_thread.start()
        logger.info('代付流程调度器已启动')


def stop_pay_flow_scheduler():
    global _running
    _running = False


def _scheduler_loop(app):
    while _running:
        try:
            _check_and_advance(app)
        except Exception as e:
            logger.error(f'代付流程调度器异常: {e}', exc_info=True)
        time.sleep(5)


def _check_and_advance(app):
    with app.app_context():
        from app import db
        from app.models.pay_flow import PayFlowExecution
        from app.services.pay_flow_service import advance_flow

        now = datetime.utcnow()

        pending = PayFlowExecution.query.filter_by(status='pending').all()
        for execution in pending:
            try:
                advance_flow(execution.execution_id)
                db.session.commit()
            except Exception as e:
                logger.error(f'推进流程 {execution.execution_id} 失败: {e}', exc_info=True)
                db.session.rollback()

        waiting = PayFlowExecution.query.filter_by(status='waiting').all()
        for execution in waiting:
            if execution.next_run_at and execution.next_run_at <= now:
                try:
                    advance_flow(execution.execution_id)
                    db.session.commit()
                except Exception as e:
                    logger.error(f'推进等待流程 {execution.execution_id} 失败: {e}', exc_info=True)
                    db.session.rollback()
