import json
import logging
import threading
from app import db
from app.models.user_behavior import UserBehavior
from app.models.ai_skill import AiSkill

logger = logging.getLogger(__name__)


def track_behavior(user_id, action, target_type=None, target_id=None, detail=None):
    """
    记录用户行为，并在满足条件时触发自动学习
    """
    try:
        detail_str = None
        if detail:
            detail_str = json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else str(detail)

        behavior = UserBehavior(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail_str,
        )
        db.session.add(behavior)
        db.session.commit()

        # 异步触发自动学习检查
        _trigger_auto_learn(user_id)
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        logger.warning(f'行为追踪失败: {e}')


def track_behavior_async(user_id, action, target_type=None, target_id=None, detail=None):
    """异步记录用户行为（不阻塞主流程）"""
    thread = threading.Thread(
        target=_async_track,
        args=(user_id, action, target_type, target_id, detail),
        daemon=True,
    )
    thread.start()


def _async_track(user_id, action, target_type=None, target_id=None, detail=None):
    """在独立线程中记录行为"""
    try:
        from app import create_app
        app = create_app()
    except:
        from flask import current_app
        app = current_app._get_current_object()

    with app.app_context():
        track_behavior(user_id, action, target_type, target_id, detail)


def _trigger_auto_learn(user_id):
    """
    检查是否满足自动学习条件，如果满足则生成Skills
    """
    try:
        # 检查用户最近的行为数量
        recent_count = UserBehavior.query.filter_by(user_id=user_id).count()

        # 每20次行为触发一次学习检查
        if recent_count > 0 and recent_count % 20 == 0:
            _do_auto_learn(user_id)
    except Exception as e:
        logger.warning(f'自动学习触发失败: {e}')


def _do_auto_learn(user_id):
    """执行自动学习，分析行为模式生成Skills"""
    new_skills = []

    try:
        # 1. 分析查询模式
        query_behaviors = UserBehavior.query.filter_by(
            user_id=user_id, action='query', target_type='script'
        ).order_by(UserBehavior.created_at.desc()).limit(50).all()

        if len(query_behaviors) >= 5:
            # 统计最常查询的脚本
            script_counts = {}
            for b in query_behaviors:
                if b.target_id:
                    script_counts[b.target_id] = script_counts.get(b.target_id, 0) + 1

            if script_counts:
                top_scripts = sorted(script_counts.items(), key=lambda x: -x[1])[:5]
                existing = AiSkill.query.filter_by(
                    user_id=user_id, category='query', source='auto_learn',
                    name='频繁查询模式'
                ).first()

                if not existing:
                    from app.models.script import Script
                    script_names = []
                    for sid, count in top_scripts:
                        s = Script.query.get(sid)
                        if s:
                            script_names.append({'id': sid, 'name': s.name, 'count': count})

                    if script_names:
                        skill = AiSkill(
                            name='频繁查询模式',
                            skill_type='user',
                            category='query',
                            description=f'基于{len(query_behaviors)}次查询行为自动识别的常用查询模式',
                            content=json.dumps({'frequent_scripts': script_names}, ensure_ascii=False),
                            user_id=user_id,
                            source='auto_learn',
                        )
                        db.session.add(skill)
                        new_skills.append(skill)

        # 2. 分析导出模式
        export_behaviors = UserBehavior.query.filter_by(
            user_id=user_id, action='export', target_type='export_script'
        ).order_by(UserBehavior.created_at.desc()).limit(50).all()

        if len(export_behaviors) >= 3:
            existing = AiSkill.query.filter_by(
                user_id=user_id, category='export', source='auto_learn',
                name='频繁导出模式'
            ).first()

            if not existing:
                script_counts = {}
                for b in export_behaviors:
                    if b.target_id:
                        script_counts[b.target_id] = script_counts.get(b.target_id, 0) + 1

                if script_counts:
                    from app.models.script import Script
                    script_names = []
                    for sid, count in sorted(script_counts.items(), key=lambda x: -x[1])[:5]:
                        s = Script.query.get(sid)
                        if s:
                            script_names.append({'id': sid, 'name': s.name, 'count': count})

                    if script_names:
                        skill = AiSkill(
                            name='频繁导出模式',
                            skill_type='user',
                            category='export',
                            description=f'基于{len(export_behaviors)}次导出行为自动识别的常用导出模式',
                            content=json.dumps({'frequent_scripts': script_names}, ensure_ascii=False),
                            user_id=user_id,
                            source='auto_learn',
                        )
                        db.session.add(skill)
                        new_skills.append(skill)

        # 3. 分析操作习惯（时间偏好）
        all_behaviors = UserBehavior.query.filter_by(user_id=user_id)\
            .order_by(UserBehavior.created_at.desc()).limit(100).all()

        if len(all_behaviors) >= 20:
            existing = AiSkill.query.filter_by(
                user_id=user_id, category='behavior', source='auto_learn',
                name='操作时间偏好'
            ).first()

            if not existing:
                from app.utils.helpers import utc_to_beijing
                hour_counts = {}
                action_type_counts = {}
                for b in all_behaviors:
                    bj_time = utc_to_beijing(b.created_at) if b.created_at else None
                    if bj_time:
                        hour = bj_time.hour
                        hour_counts[hour] = hour_counts.get(hour, 0) + 1
                    action_type_counts[b.action] = action_type_counts.get(b.action, 0) + 1

                peak_hours = sorted(hour_counts.items(), key=lambda x: -x[1])[:3]
                top_actions = sorted(action_type_counts.items(), key=lambda x: -x[1])[:5]

                skill = AiSkill(
                    name='操作时间偏好',
                    skill_type='user',
                    category='behavior',
                    description=f'基于{len(all_behaviors)}次操作自动识别的使用习惯',
                    content=json.dumps({
                        'peak_hours': [{'hour': h, 'count': c} for h, c in peak_hours],
                        'top_actions': [{'action': a, 'count': c} for a, c in top_actions],
                    }, ensure_ascii=False),
                    user_id=user_id,
                    source='auto_learn',
                )
                db.session.add(skill)
                new_skills.append(skill)

        # 4. 分析列映射偏好
        mapping_behaviors = UserBehavior.query.filter_by(
            user_id=user_id, action='query', target_type='task'
        ).order_by(UserBehavior.created_at.desc()).limit(30).all()

        if len(mapping_behaviors) >= 5:
            existing = AiSkill.query.filter_by(
                user_id=user_id, category='query', source='auto_learn',
                name='列映射偏好'
            ).first()

            if not existing:
                mapping_patterns = {}
                for b in mapping_behaviors:
                    if b.detail:
                        try:
                            detail = json.loads(b.detail) if isinstance(b.detail, str) else b.detail
                            if isinstance(detail, dict) and 'column_mapping' in detail:
                                for sql_col, excel_col in detail['column_mapping'].items():
                                    if excel_col and excel_col != '隐藏':
                                        key = f"{sql_col}->{excel_col}"
                                        mapping_patterns[key] = mapping_patterns.get(key, 0) + 1
                        except:
                            pass

                if mapping_patterns:
                    frequent_mappings = sorted(mapping_patterns.items(), key=lambda x: -x[1])[:10]
                    skill = AiSkill(
                        name='列映射偏好',
                        skill_type='user',
                        category='query',
                        description=f'基于{len(mapping_behaviors)}次查询自动识别的列映射偏好',
                        content=json.dumps({
                            'frequent_mappings': [{'mapping': k, 'count': v} for k, v in frequent_mappings],
                        }, ensure_ascii=False),
                        user_id=user_id,
                        source='auto_learn',
                    )
                    db.session.add(skill)
                    new_skills.append(skill)

        if new_skills:
            db.session.commit()
            logger.info(f'用户{user_id}自动学习生成{len(new_skills)}个Skills')

    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        logger.error(f'自动学习失败: {e}', exc_info=True)
