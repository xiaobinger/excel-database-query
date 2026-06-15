import json
import logging
import os
import time
import uuid
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app import db
from app.models.ai_config import AiConfig
from app.models.ai_skill import AiSkill
from app.models.user_behavior import UserBehavior
from app.models.ai_chat import AiChat, AiChatMessage
from app.utils.auth import login_required, admin_required, get_current_user, permission_required
import requests
logger = logging.getLogger(__name__)
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

# 活跃流式请求跟踪：{chat_id: {'aborted': bool, 'request_id': str}}
_active_streams = {}


# ============ AI Config ============
@ai_bp.route('/configs', methods=['GET'])
@permission_required('system')
def get_configs():
    configs = AiConfig.query.order_by(AiConfig.created_at.desc()).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in configs]})


@ai_bp.route('/active-models', methods=['GET'])
@login_required
def get_active_models():
    """Get all enabled AI models (accessible to all logged-in users for @mention)"""
    configs = AiConfig.query.filter_by(is_active=True).order_by(AiConfig.name).all()
    return jsonify({'success': True, 'data': [
        {'id': c.id, 'name': c.name, 'model_name': c.model_name, 'provider': c.provider, 'enable_thinking': c.enable_thinking or False, 'enable_streaming': c.enable_streaming if c.enable_streaming is not None else True}
        for c in configs
    ]})


@ai_bp.route('/configs', methods=['POST'])
@permission_required('system')
def create_config():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'message': '请输入配置名称'}), 400

    try:
        config = AiConfig(
            name=data['name'],
            provider=data.get('provider', 'openai'),
            api_base=data.get('api_base', ''),
            model_name=data.get('model_name', ''),
            is_default=data.get('is_default', False),
            is_active=data.get('is_active', True),
            max_tokens=data.get('max_tokens', 4096),
            temperature=data.get('temperature', 0.7),
            system_prompt=data.get('system_prompt', ''),
            description=data.get('description', ''),
            enable_thinking=data.get('enable_thinking', False),
            enable_streaming=data.get('enable_streaming', True),
        )
        if data.get('api_key'):
            config.set_api_key(data['api_key'])

        if config.is_default:
            AiConfig.query.filter_by(is_default=True).update({'is_default': False})

        db.session.add(config)
        db.session.commit()
        return jsonify({'success': True, 'data': config.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/configs/<int:config_id>', methods=['PUT'])
@permission_required('system')
def update_config(config_id):
    config = AiConfig.query.get(config_id)
    if not config:
        return jsonify({'success': False, 'message': '配置不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    try:
        simple_fields = ['name', 'provider', 'api_base', 'model_name', 'is_default',
                         'is_active', 'max_tokens', 'temperature', 'system_prompt', 'description',
                         'enable_thinking', 'enable_streaming']
        for key in simple_fields:
            if key in data:
                setattr(config, key, data[key])

        if 'api_key' in data and data['api_key']:
            config.set_api_key(data['api_key'])

        if config.is_default:
            AiConfig.query.filter(AiConfig.id != config_id, AiConfig.is_default == True).update({'is_default': False})

        db.session.commit()
        return jsonify({'success': True, 'data': config.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/configs/<int:config_id>', methods=['DELETE'])
@permission_required('system')
def delete_config(config_id):
    config = AiConfig.query.get(config_id)
    if not config:
        return jsonify({'success': False, 'message': '配置不存在'}), 404
    db.session.delete(config)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@ai_bp.route('/configs/batch-delete', methods=['POST'])
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
        config = AiConfig.query.get(config_id)
        if config:
            db.session.delete(config)
            deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个配置', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/configs/all', methods=['DELETE'])
@permission_required('system')
def delete_all_configs():
    try:
        deleted_count = AiConfig.query.delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个配置', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/configs/<int:config_id>/test', methods=['POST'])
@permission_required('system')
def test_config(config_id):
    config = AiConfig.query.get(config_id)
    if not config:
        return jsonify({'success': False, 'message': '配置不存在'}), 404

    try:
        from app.services.ai_service import AiService
        result = AiService.test_connection(config)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'连接测试失败: {str(e)}'}), 400


# ============ Skills ============
@ai_bp.route('/skills', methods=['GET'])
@login_required
def get_skills():
    current_user = get_current_user()
    category = request.args.get('category')
    skill_type = request.args.get('skill_type')

    query = AiSkill.query
    if not current_user.is_admin():
        query = query.filter((AiSkill.skill_type == 'system') | (AiSkill.user_id == current_user.id))
    if category:
        query = query.filter_by(category=category)
    if skill_type:
        query = query.filter_by(skill_type=skill_type)

    skills = query.filter_by(is_active=True).order_by(AiSkill.updated_at.desc()).all()
    return jsonify({'success': True, 'data': [s.to_dict() for s in skills]})


@ai_bp.route('/skills', methods=['POST'])
@login_required
def create_skill():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'message': '请输入技能名称'}), 400

    current_user = get_current_user()
    try:
        skill = AiSkill(
            name=data['name'],
            skill_type=data.get('skill_type', 'user'),
            category=data.get('category', 'workflow'),
            description=data.get('description', ''),
            content=json.dumps(data.get('content', {}), ensure_ascii=False) if isinstance(data.get('content'), dict) else data.get('content', ''),
            trigger_conditions=json.dumps(data.get('trigger_conditions', {}), ensure_ascii=False) if isinstance(data.get('trigger_conditions'), dict) else data.get('trigger_conditions', ''),
            user_id=current_user.id if not current_user.is_admin() else data.get('user_id'),
            source=data.get('source', 'manual'),
        )
        db.session.add(skill)
        db.session.commit()
        return jsonify({'success': True, 'data': skill.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/skills/<int:skill_id>', methods=['PUT'])
@login_required
def update_skill(skill_id):
    skill = AiSkill.query.get(skill_id)
    if not skill:
        return jsonify({'success': False, 'message': '技能不存在'}), 404

    current_user = get_current_user()
    if not current_user.is_admin() and skill.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权修改'}), 403

    data = request.get_json()
    try:
        simple_fields = ['name', 'skill_type', 'category', 'description', 'is_active', 'source']
        for key in simple_fields:
            if key in data:
                setattr(skill, key, data[key])

        if 'content' in data:
            skill.content = json.dumps(data['content'], ensure_ascii=False) if isinstance(data['content'], dict) else data['content']
        if 'trigger_conditions' in data:
            skill.trigger_conditions = json.dumps(data['trigger_conditions'], ensure_ascii=False) if isinstance(data['trigger_conditions'], dict) else data['trigger_conditions']

        skill.version = (skill.version or 0) + 1
        db.session.commit()
        return jsonify({'success': True, 'data': skill.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/skills/<int:skill_id>', methods=['DELETE'])
@login_required
def delete_skill(skill_id):
    skill = AiSkill.query.get(skill_id)
    if not skill:
        return jsonify({'success': False, 'message': '技能不存在'}), 404

    current_user = get_current_user()
    if not current_user.is_admin() and skill.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权删除'}), 403

    db.session.delete(skill)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@ai_bp.route('/skills/batch-delete', methods=['POST'])
@login_required
def batch_delete_skills():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    current_user = get_current_user()
    deleted_count = 0
    for skill_id in ids:
        skill = AiSkill.query.get(skill_id)
        if not skill:
            continue
        if not current_user.is_admin() and skill.user_id != current_user.id:
            continue
        db.session.delete(skill)
        deleted_count += 1

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个技能', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/skills/all', methods=['DELETE'])
@login_required
def delete_all_skills():
    current_user = get_current_user()
    try:
        if current_user.is_admin():
            deleted_count = AiSkill.query.delete()
        else:
            deleted_count = AiSkill.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个技能', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


# ============ Behavior Tracking ============
@ai_bp.route('/behaviors', methods=['POST'])
@login_required
def track_behavior():
    data = request.get_json()
    if not data or not data.get('action'):
        return jsonify({'success': False, 'message': '缺少行为类型'}), 400

    current_user = get_current_user()
    try:
        from app.utils.behavior_tracker import track_behavior as _track
        _track(current_user.id, data['action'], data.get('target_type'), data.get('target_id'), data.get('detail'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/behaviors', methods=['GET'])
@admin_required
def get_behaviors():
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action')
    limit = request.args.get('limit', 100, type=int)

    query = UserBehavior.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)

    behaviors = query.order_by(UserBehavior.created_at.desc()).limit(limit).all()
    return jsonify({'success': True, 'data': [b.to_dict() for b in behaviors]})


# ============ Chat ============
@ai_bp.route('/chats', methods=['GET'])
@login_required
def get_chats():
    current_user = get_current_user()
    chats = AiChat.query.filter_by(user_id=current_user.id, is_archived=False, is_deleted=False)\
        .order_by(AiChat.updated_at.desc()).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in chats]})


@ai_bp.route('/chats', methods=['POST'])
@login_required
def create_chat():
    current_user = get_current_user()
    data = request.get_json() or {}
    try:
        chat = AiChat(
            user_id=current_user.id,
            title=data.get('title', '新对话'),
        )
        db.session.add(chat)
        db.session.commit()
        return jsonify({'success': True, 'data': chat.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


# ============ Delete Chat (Soft Delete) ============
@ai_bp.route('/chats/<int:chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    # Soft delete
    chat.is_deleted = True
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


# ============ Clear Chat Messages ============
@ai_bp.route('/chats/<int:chat_id>/clear', methods=['POST'])
@login_required
def clear_chat_messages(chat_id):
    """清空对话消息：普通用户软删除，管理员可选彻底删除"""
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    data = request.get_json() or {}
    hard = data.get('hard', False)

    if hard and current_user.is_admin():
        # 管理员彻底删除
        AiChatMessage.query.filter_by(chat_id=chat_id).delete()
    else:
        # 普通用户软删除
        AiChatMessage.query.filter_by(chat_id=chat_id, is_deleted=False).update({'is_deleted': True})

    db.session.commit()
    return jsonify({'success': True, 'message': '已清空对话'})


# ============ Retry/Regenerate AI Response ============
@ai_bp.route('/chats/<int:chat_id>/messages/<int:message_id>/retry', methods=['POST'])
@login_required
def retry_message(chat_id, message_id):
    """重新生成AI回复：找到该回复对应的用户消息，返回其内容供前端重新发送（不删除任何消息）"""
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    msg = AiChatMessage.query.filter_by(id=message_id, chat_id=chat_id).first()
    if not msg:
        return jsonify({'success': False, 'message': '消息不存在'}), 404

    if msg.role != 'assistant':
        return jsonify({'success': False, 'message': '只能重试AI回复消息'}), 400

    # 找到该AI回复对应的用户消息（该消息之前的最后一条用户消息）
    user_msg = AiChatMessage.query.filter(
        AiChatMessage.chat_id == chat_id,
        AiChatMessage.role == 'user',
        AiChatMessage.is_deleted == False,
        AiChatMessage.created_at < msg.created_at,
    ).order_by(AiChatMessage.created_at.desc()).first()

    if not user_msg:
        return jsonify({'success': False, 'message': '未找到对应的用户消息'}), 400

    # 不删除任何消息，只返回用户消息内容供前端重新发送
    return jsonify({'success': True, 'data': {'user_content': user_msg.content}})


# ============ Hard Delete Chat (Admin Only) ============
@ai_bp.route('/chats/<int:chat_id>/hard', methods=['DELETE'])
@login_required
def hard_delete_chat(chat_id):
    current_user = get_current_user()
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403

    chat = AiChat.query.filter_by(id=chat_id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    # Physically delete messages and chat
    AiChatMessage.query.filter_by(chat_id=chat_id).delete()
    db.session.delete(chat)
    db.session.commit()
    return jsonify({'success': True, 'message': '永久删除成功'})


@ai_bp.route('/chats/batch-hard-delete', methods=['POST'])
@login_required
def batch_hard_delete_chats():
    """批量永久删除对话：仅管理员可操作"""
    current_user = get_current_user()
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403

    data = request.get_json()
    ids = data.get('ids', [])
    if not ids or not isinstance(ids, list):
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400

    deleted_count = 0
    for chat_id in ids:
        chat = AiChat.query.filter_by(id=chat_id).first()
        if chat:
            AiChatMessage.query.filter_by(chat_id=chat_id).delete()
            db.session.delete(chat)
            deleted_count += 1
    db.session.commit()
    return jsonify({'success': True, 'message': f'成功永久删除 {deleted_count} 个对话', 'deleted_count': deleted_count})


@ai_bp.route('/chats/all-hard', methods=['DELETE'])
@login_required
def hard_delete_all_chats():
    """永久删除全部对话：仅管理员可操作"""
    current_user = get_current_user()
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权限'}), 403

    count = AiChat.query.count()
    # 先删除所有消息
    chat_ids = [c.id for c in AiChat.query.with_entities(AiChat.id).all()]
    for chat_id in chat_ids:
        AiChatMessage.query.filter_by(chat_id=chat_id).delete()
    AiChat.query.delete()
    db.session.commit()
    return jsonify({'success': True, 'message': f'成功永久删除 {count} 个对话', 'deleted_count': count})


@ai_bp.route('/chats/<int:chat_id>/messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(chat_id, message_id):
    """软删除单条消息：普通用户只能软删除自己的消息"""
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    msg = AiChatMessage.query.filter_by(id=message_id, chat_id=chat_id).first()
    if not msg:
        return jsonify({'success': False, 'message': '消息不存在'}), 404

    msg.is_deleted = True
    db.session.commit()
    return jsonify({'success': True, 'message': '已删除'})


@ai_bp.route('/chats/<int:chat_id>/messages/<int:message_id>/hard', methods=['DELETE'])
@admin_required
def hard_delete_message(chat_id, message_id):
    """永久删除单条消息：仅管理员可操作"""
    msg = AiChatMessage.query.filter_by(id=message_id, chat_id=chat_id).first()
    if not msg:
        return jsonify({'success': False, 'message': '消息不存在'}), 404

    db.session.delete(msg)
    db.session.commit()
    return jsonify({'success': True, 'message': '已永久删除'})


@ai_bp.route('/upload-file', methods=['POST'])
@login_required
def upload_file():
    current_user = get_current_user()
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': '文件名为空'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    allowed_ext = current_app.config.get('ALLOWED_UPLOAD_EXTENSIONS', {'xlsx', 'xls', 'csv'})
    if ext not in allowed_ext:
        return jsonify({'success': False, 'message': f'仅支持 {", ".join(sorted(allowed_ext))} 格式的文件'}), 400

    try:
        from app.services.excel_service import ExcelService
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"ai_{uuid.uuid4().hex[:8]}_{file.filename}"
        input_path = os.path.join(upload_dir, filename)
        file.save(input_path)

        info = ExcelService.get_file_info(input_path)
        columns = info.get('column_names', [])

        return jsonify({
            'success': True,
            'data': {
                'file_path': input_path,
                'filename': file.filename,
                'row_count': info.get('data_rows', 0),
                'columns': columns,
                'preview': info.get('preview_rows', []),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@ai_bp.route('/match-query', methods=['POST'])
@login_required
def match_query():
    """根据上传的文件信息，自动匹配最合适的查询选项"""
    current_user = get_current_user()
    data = request.get_json()
    if not data or 'columns' not in data:
        return jsonify({'success': False, 'message': '缺少列信息'}), 400

    columns = data.get('columns', [])
    user_script_ids = set(current_user.get_script_ids()) if not current_user.is_admin() else None

    from app.models.script import Script
    scripts = Script.query.filter_by(type='query').all()
    if user_script_ids:
        scripts = [s for s in scripts if s.id in user_script_ids]

    # 简单匹配：根据名称匹配
    matches = []
    for s in scripts:
        score = 0
        name_lower = s.name.lower()
        desc_lower = (s.description or '').lower()
        for col in columns:
            col_lower = col.lower()
            if col_lower in name_lower or name_lower in col_lower:
                score += 3
            if col_lower in desc_lower:
                score += 1
        if score > 0:
            matches.append({
                'id': s.id,
                'name': s.name,
                'description': s.description or '',
                'score': score,
            })

    matches.sort(key=lambda x: x['score'], reverse=True)
    return jsonify({'success': True, 'data': {'matches': matches[:5]}})


@ai_bp.route('/chats/<int:chat_id>/messages', methods=['GET'])
@login_required
def get_messages(chat_id):
    current_user = get_current_user()
    # 管理员可以查看任何用户的会话，普通用户只能查看自己的
    if current_user.is_admin():
        chat = AiChat.query.filter_by(id=chat_id).first()
    else:
        chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    messages = AiChatMessage.query.filter_by(chat_id=chat_id, is_deleted=False)\
        .order_by(AiChatMessage.created_at.asc()).all()
    return jsonify({'success': True, 'data': [m.to_dict() for m in messages]})


@ai_bp.route('/chats/<int:chat_id>/send', methods=['POST'])
@login_required
def send_message(chat_id):
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400

    start_time = time.time()

    user_message = AiChatMessage(
        chat_id=chat_id,
        role='user',
        content=data['content'],
    )
    db.session.add(user_message)

    # Update chat title from first message
    if not chat.title or chat.title == '新对话':
        chat.title = data['content'][:50]

    db.session.commit()

    # Get ordered AI configs from strategy (with failover support)
    from app.services.ai_service import AiService

    # Check if user specified a particular model via @mention
    specified_config_id = data.get('ai_config_id')
    specified_config = None
    if specified_config_id:
        specified_config = AiConfig.query.filter_by(id=int(specified_config_id), is_active=True).first()

    ordered_configs = AiService.get_ordered_configs()

    # Use specified config if provided via @mention, otherwise use strategy
    if specified_config:
        ai_config = specified_config
        # Override ordered_configs to only use the specified one (no failover for @mention)
        ordered_configs = [specified_config]
        logger.info(f"User @mentioned model: {specified_config.name} ({specified_config.model_name})")
    elif ordered_configs:
        ai_config = ordered_configs[0]  # Primary config for system prompt
    else:
        assistant_message = AiChatMessage(
            chat_id=chat_id,
            role='assistant',
            content='AI服务未配置，请先在系统配置中添加AI模型配置。',
        )
        db.session.add(assistant_message)
        db.session.commit()
        return jsonify({'success': True, 'data': {
            'user_message': user_message.to_dict(),
            'assistant_message': assistant_message.to_dict(),
        }})

    # Build context with skills and behaviors
    try:
        context = AiService.build_chat_context(current_user.id, chat_id)

        # Get chat history
        history = AiChatMessage.query.filter_by(chat_id=chat_id)\
            .order_by(AiChatMessage.created_at.asc()).all()
        messages = []
        if ai_config.system_prompt:
            messages.append({'role': 'system', 'content': ai_config.system_prompt})
        else:
            sys_prompt = context + '\n\n## 重要规则\n' \
                '- 系统中有四种不同类型的任务，必须严格区分：\n' \
                '  1. 导出任务（export）：从数据库导出数据到Excel，调用 list_export_options / request_export\n' \
                '  2. 查询任务（query）：根据Excel文件中的主键数据去数据库批量查询匹配信息，需要上传Excel文件，调用 list_query_options / request_query\n' \
                '  3. 系统任务（system_task）：后台运维类操作（如数据清理、缓存刷新、终端解绑等），调用 list_system_tasks / request_system_task\n' \
                '  4. 信息查询（lookup）：根据用户提供的参数值快速查询数据库返回结果（如查询SN绑定状态、商户是否激活、订单是否出款等），结果直接在对话中展示，调用 list_lookup_options / request_lookup\n' \
                '- 当用户表达需要导出数据的意图时，调用 request_export 工具\n' \
                '- 当用户表达需要批量查询（上传Excel文件）的意图时，调用 request_query 工具\n' \
                '- 当用户表达需要执行系统任务的意图时，调用 request_system_task 工具\n' \
                '- 当用户询问某个实体的状态、信息、详情时（如"这个SN的绑定状态"、"这个商户是否激活"），调用 request_lookup 工具\n' \
                '- 重要：当用户的查询涉及多个不同维度的信息时（如"查一下SN123的绑定状态和交易信息"），应在同一次回复中同时调用多个 request_lookup 工具，分别查询不同维度的信息，然后将所有查询结果归总后统一回答用户\n' \
                '- 重要：当用户的意图是条件性的（如"查一下这个SN的绑定状态，如果已绑定就解绑"、"查商户是否激活，未激活则激活"），必须先调用 request_lookup 查询状态，拿到结果后根据条件判断是否需要调用 request_system_task，在二次回复中完成条件判断和后续操作\n' \
                '- 调用 request_export 时，务必从用户描述中提取所有参数值（如商户号、日期、渠道等）填入 params 对象\n' \
                '- 调用 request_system_task 时，务必从用户描述中提取所有参数值填入 params 对象，params的键名必须使用list_system_tasks返回的参数配置中的name字段值\n' \
                '- 重要：API类型的系统任务参数齐全时会自动执行并返回结果（包含mapping_summary映射摘要），请直接根据映射摘要用自然语言告诉用户执行结果\n' \
                '- 重要：如果用户同时要求对多个对象执行同样的API系统任务（如"解绑SN001、SN002、SN003"），请在同一次回复中同时调用多个 request_system_task，每个调用对应一个对象，系统会自动并行执行，你只需汇总所有结果用列表形式反馈给用户\n' \
                '- 调用 request_lookup 时，务必从用户描述中提取所有参数值填入 params 对象，params的键名必须使用list_lookup_options返回的参数配置中的name字段值\n' \
                '- 重要：调用 list_lookup_options 时，如果用户提供了具体的参数值（如SN号、商户号等），务必同时传入 params 参数，这样当匹配到唯一查询时系统可以自动执行，大幅加快响应速度\n' \
                '- 如果用户没有指定具体的导出选项名称，先调用 list_export_options 列出相关选项让用户选择\n' \
                '- 如果用户没有指定具体的查询选项名称，先调用 list_query_options 列出相关选项让用户选择\n' \
                '- 如果用户没有指定具体的系统任务名称，先调用 list_system_tasks 列出相关任务让用户选择\n' \
                '- 如果用户没有指定具体的信息查询名称，先调用 list_lookup_options 列出相关查询让用户选择\n' \
                '- 如果用户提供了参数值，务必在调用工具时传入正确的参数\n' \
                '- 如果缺少必填参数，在回复中向用户询问\n' \
                '- 当用户上传文件时，消息中会包含文件信息（行数和列名），根据列名自动匹配最合适的查询或导出选项\n'
            messages.append({'role': 'system', 'content': sys_prompt})

        for msg in history:
            messages.append({'role': msg.role, 'content': msg.content})

        # Call AI with failover support (use override if @mention)
        ai_response = AiService.chat_with_failover(messages, use_tools=True,
            override_configs=ordered_configs if specified_config else None)
        response_text = ai_response['content']
        tool_calls = ai_response['tool_calls']
        tokens = ai_response['tokens']
        prompt_tokens = ai_response.get('prompt_tokens', 0)
        completion_tokens = ai_response.get('completion_tokens', 0)

        # If AI wants to call tools, execute them
        tool_results = []
        if tool_calls:
            for tc in tool_calls:
                func_name = tc.get('function', {}).get('name', '')
                func_args = tc.get('function', {}).get('arguments', '')
                logger.info(f'AI调用工具: {func_name}({func_args})')
                result = AiService.execute_tool_call(func_name, func_args, current_user.id)
                # 解析参数供后续自动执行使用
                try:
                    args = json.loads(func_args) if func_args else {}
                except json.JSONDecodeError:
                    args = {}
                tool_results.append({
                    'tool_call_id': tc['id'],
                    'name': func_name,
                    'result': result,
                })

                # 智能处理：如果list_export_options返回唯一匹配，自动调用request_export
                # 注意：不再自动调用，让AI在二次回复时提取参数并调用
                if func_name == 'list_export_options' and result.get('total') == 1 and not result.get('error'):
                    script = result['scripts'][0]
                    logger.info(f'匹配到唯一导出选项: {script["name"]}，等待AI二次回复提取参数')
                    # 不再自动调用 request_export，让AI从用户消息中提取参数后调用
                # 多匹配 → 创建选择卡片
                elif func_name == 'list_export_options' and not result.get('error'):
                    if result.get('total', 0) > 1:
                        result['_select_mode'] = 'multi'
                        result['message'] = f'找到 {result["total"]} 个匹配的导出选项，请勾选需要的选项后点击确认执行'
                    elif result.get('total', 0) == 0:
                        # 无匹配，不创建选择卡片，交给AI回复
                        pass

                # 智能处理：如果list_query_options返回唯一匹配，自动调用request_query
                # 注意：不再自动调用，让AI在二次回复时提取参数并调用
                if func_name == 'list_query_options' and result.get('total') == 1 and not result.get('error'):
                    script = result['scripts'][0]
                    logger.info(f'匹配到唯一查询选项: {script["name"]}，等待AI二次回复')
                    # 不再自动调用 request_query，让AI处理
                # 多匹配 → 创建选择卡片
                elif func_name == 'list_query_options' and not result.get('error'):
                    if result.get('total', 0) > 1:
                        result['_select_mode'] = 'multi'
                        result['message'] = f'找到 {result["total"]} 个匹配的查询选项，请勾选后执行'
                    elif result.get('total', 0) == 0:
                        # 无匹配，不创建选择卡片，交给AI回复
                        pass

                # 系统任务列表处理
                if func_name == 'list_system_tasks' and result.get('total') == 1 and not result.get('error'):
                    task = result['tasks'][0]
                    logger.info(f'匹配到唯一系统任务: {task["name"]}，等待AI二次回复提取参数')
                    # 唯一匹配时不设置_select_mode，让AI二次回复调用request_system_task
                if func_name == 'list_system_tasks' and not result.get('error'):
                    if result.get('total', 0) > 1:
                        result['_select_mode'] = 'multi'
                        result['message'] = f'找到 {result["total"]} 个匹配的系统任务，请勾选后执行'
                    elif result.get('total', 0) == 0:
                        # 无匹配，不创建选择卡片，交给AI回复
                        pass

                # 信息查询列表处理
                if func_name == 'list_lookup_options' and not result.get('error'):
                    if result.get('total', 0) == 1:
                        # 唯一匹配：自动执行查询，省掉第二次AI调用
                        script = result['scripts'][0]
                        logger.info(f'匹配到唯一信息查询: {script["name"]}，自动执行查询')
                        # 优先使用AI传入的params，否则尝试从用户消息中提取
                        auto_params = args.get('params', {})
                        if not auto_params and script.get('params'):
                            auto_params = AiService.extract_params_from_message(
                                data['content'], script['params'])
                            if auto_params:
                                logger.info(f'从用户消息中提取到参数: {auto_params}')
                        auto_result = AiService._tool_request_lookup({
                            'lookup_name': script['name'],
                            'description': args.get('description', '') or data['content'][:200],
                            'params': auto_params,
                        }, current_user.id)
                        # 添加自动执行标记，告诉AI这是已完成的查询结果
                        auto_result['_auto_executed'] = True
                        auto_result['_hint'] = '此查询已自动执行完成，结果如下。请直接根据查询结果回答用户问题，不要再次调用request_lookup。'
                        # 替换原结果为查询结果
                        tool_results[-1] = {
                            'tool_call_id': tc['id'],
                            'name': 'request_lookup',
                            'result': auto_result,
                        }
                        # 同步更新tool_calls中的工具名，确保后续判断和AI二次回复正确
                        tc['function']['name'] = 'request_lookup'
                        tc['function']['arguments'] = json.dumps({
                            'lookup_name': script['name'],
                            'description': args.get('description', '') or data['content'][:200],
                            'params': auto_params,
                        }, ensure_ascii=False)
                    elif result.get('total', 0) > 1:
                        result['_select_mode'] = 'multi'
                        result['message'] = f'找到 {result["total"]} 个匹配的信息查询，请选择要使用的查询'
                    # total == 0: 无匹配，交给AI回复

            # Build tool result messages for AI to generate final response
            tool_messages = []
            for tr in tool_results:
                result = tr.get('result', {})
                # 对auto_executed的系统任务结果精简，避免过大导致AI无法处理
                if result.get('auto_executed') and result.get('action_type') == 'system_task':
                    concise_result = {
                        'action_type': 'system_task',
                        'task_name': result.get('task_name', ''),
                        'auto_executed': True,
                        'success': result.get('success', False),
                        'status_code': result.get('status_code'),
                        'mapping_summary': result.get('mapping_summary', ''),
                        'mapping_info': result.get('mapping_info', ''),
                    }
                    if result.get('error'):
                        concise_result['error'] = result['error']
                    # 如果mapping_summary为空，附上简化的response
                    if not result.get('mapping_summary') and isinstance(result.get('response'), dict):
                        concise_result['response'] = result['response']
                    tool_messages.append({
                        'role': 'tool',
                        'tool_call_id': tr['tool_call_id'],
                        'content': json.dumps(concise_result, ensure_ascii=False),
                    })
                else:
                    tool_messages.append({
                        'role': 'tool',
                        'tool_call_id': tr['tool_call_id'],
                        'content': json.dumps(result, ensure_ascii=False),
                    })

            # Ask AI to generate final response with tool results
            messages.append({
                'role': 'assistant',
                'content': response_text,
                'tool_calls': tool_calls,
            })
            messages.extend(tool_messages)

            # 检查工具类型：如果是操作型工具（导出/查询），跳过AI二次确认
            # 信息查询(request_lookup)：只有所有lookup都是show_all_fields=true时才跳过AI二次回复
            # API系统任务自动执行(auto_executed)：走AI二次回复流程，让AI根据映射结果反馈用户
            action_tools = {'request_export', 'request_query', 'request_system_task'}
            has_action = any(tc.get('function', {}).get('name', '') in action_tools for tc in tool_calls)
            # 检查是否有自动执行的API系统任务（需要AI二次回复反馈结果）
            has_auto_exec_system_task = any(
                tr.get('result', {}).get('auto_executed', False)
                for tr in tool_results
                if tr.get('result', {}).get('action_type') == 'system_task'
            )
            logger.info(f'普通路由-自动执行检测: has_auto_exec_system_task={has_auto_exec_system_task}, has_action={has_action}')
            # 如果所有system_task都是auto_executed，则不算action
            if has_auto_exec_system_task:
                all_system_task_auto = all(
                    tr.get('result', {}).get('auto_executed', False)
                    for tr in tool_results
                    if tr.get('result', {}).get('action_type') == 'system_task'
                )
                if all_system_task_auto:
                    has_action = False
            # 信息查询：检查是否有需要AI二次回复的lookup（show_all_fields=false的）
            lookup_tool_calls = [tc for tc in tool_calls if tc.get('function', {}).get('name', '') == 'request_lookup']
            has_lookup_needs_reply = any(
                not tr.get('result', {}).get('show_all_fields', False)
                for tr in tool_results
                if tr.get('result', {}).get('action_type') == 'lookup'
            ) if lookup_tool_calls else False
            # 选择卡片也视为 action
            has_select = any(tr.get('result', {}).get('_select_mode') for tr in tool_results)

            if has_action or has_select:
                # 操作型工具或选择卡片，直接返回，不请求AI二次回复
                response_text = ''
                tokens = tokens  # 保持原有 token 计数
            elif has_lookup_needs_reply or has_auto_exec_system_task or not lookup_tool_calls:
                # 需要AI二次回复：1)有lookup需要归总结果；2)API系统任务自动执行需要反馈结果；3)非操作型工具需要AI回复
                logger.info(f'普通路由-进入AI二次回复: has_lookup_needs_reply={has_lookup_needs_reply}, has_auto_exec_system_task={has_auto_exec_system_task}, lookup_tool_calls={len(lookup_tool_calls)}')
                try:
                    # 构建二次回复提示
                    reply_hints = []
                    if has_lookup_needs_reply:
                        reply_hints.append('上面的信息查询已经执行完成并返回了结果。请根据查询结果回答用户问题。如果用户意图是条件性的（如满足条件则执行系统任务），请根据查询结果判断是否需要调用request_system_task等工具。不要重复调用request_lookup。')
                    if has_auto_exec_system_task:
                        reply_hints.append('上面的API系统任务已经自动执行完成并返回了结果。请根据mapping_summary（映射摘要）直接用自然语言告诉用户执行结果，如果多个任务请用列表汇总。不要重复调用request_system_task。')
                    if reply_hints:
                        messages.append({
                            'role': 'system',
                            'content': '\n'.join(reply_hints)
                        })
                    ai_response2 = AiService.chat_with_failover(messages, use_tools=True,
                        override_configs=ordered_configs if specified_config else None)
                    response_text = ai_response2['content']
                    second_tool_calls = ai_response2['tool_calls']
                    tokens = ai_response2['tokens']
                    prompt_tokens += ai_response2.get('prompt_tokens', 0)
                    completion_tokens += ai_response2.get('completion_tokens', 0)
                    logger.info(f'普通路由-AI二次回复完成: response_text长度={len(response_text or "")}, second_tool_calls={len(second_tool_calls or [])}')

                    # 如果AI在二次回复中调用了工具，执行它们
                    if second_tool_calls:
                        second_tool_results = []
                        for tc2 in second_tool_calls:
                            func_name2 = tc2.get('function', {}).get('name', '')
                            func_args2 = tc2.get('function', {}).get('arguments', '')
                            logger.info(f'AI二次回复调用工具: {func_name2}({func_args2})')
                            result2 = AiService.execute_tool_call(func_name2, func_args2, current_user.id)
                            second_tool_results.append({
                                'tool_call_id': tc2['id'],
                                'name': func_name2,
                                'result': result2,
                            })

                        # 检查二次回复是否有操作型工具
                        second_has_action = any(tc2.get('function', {}).get('name', '') in action_tools for tc2 in second_tool_calls)
                        # 二次回复中API自动执行的系统任务不算action
                        second_has_auto_exec = any(
                            tr.get('result', {}).get('auto_executed', False)
                            for tr in second_tool_results
                            if tr.get('result', {}).get('action_type') == 'system_task'
                        )
                        if second_has_auto_exec:
                            second_all_auto = all(
                                tr.get('result', {}).get('auto_executed', False)
                                for tr in second_tool_results
                                if tr.get('result', {}).get('action_type') == 'system_task'
                            )
                            if second_all_auto:
                                second_has_action = False
                        second_has_select = any(tr.get('result', {}).get('_select_mode') for tr in second_tool_results)
                        second_lookup_tc_exists = any(tc2.get('function', {}).get('name', '') == 'request_lookup' for tc2 in second_tool_calls)
                        second_has_lookup_needs_reply = any(
                            not tr.get('result', {}).get('show_all_fields', False)
                            for tr in second_tool_results
                            if tr.get('result', {}).get('action_type') == 'lookup'
                        ) if second_lookup_tc_exists else False

                        if second_has_action or second_has_select or (second_lookup_tc_exists and not second_has_lookup_needs_reply):
                            # 操作型工具/选择卡片/所有lookup都是show_all_fields=true，直接返回
                            tool_results.extend(second_tool_results)
                            response_text = ''  # 有操作型工具结果，清空文本回复
                        else:
                            # 非操作型工具，构建完整消息链，再次请求AI生成最终回复
                            tool_messages2 = []
                            for tr2 in second_tool_results:
                                tool_messages2.append({
                                    'role': 'tool',
                                    'tool_call_id': tr2['tool_call_id'],
                                    'content': json.dumps(tr2['result'], ensure_ascii=False),
                                })

                            messages.append({
                                'role': 'assistant',
                                'content': response_text,
                                'tool_calls': second_tool_calls,
                            })
                            messages.extend(tool_messages2)

                            final_payload2 = {
                                'model': ai_config.model_name or 'gpt-3.5-turbo',
                                'messages': messages,
                                'max_tokens': ai_config.max_tokens or 4096,
                                'temperature': ai_config.temperature if ai_config.temperature is not None else 0.7,
                            }
                            api_key2 = ai_config.get_api_key()
                            api_base2 = ai_config.api_base or 'https://api.openai.com/v1'
                            url2 = f"{api_base2.rstrip('/')}/chat/completions"
                            headers2 = {
                                'Authorization': f'Bearer {api_key2}',
                                'Content-Type': 'application/json',
                            }
                            response2 = requests.post(url2, headers=headers2, json=final_payload2, timeout=120)
                            response2.raise_for_status()
                            result3 = response2.json()
                            response_text = result3['choices'][0].get('message', {}).get('content', '') if result3.get('choices') else ''
                            usage3 = result3.get('usage', {})
                            tokens = usage3.get('total_tokens', tokens)
                            prompt_tokens += usage3.get('prompt_tokens', 0)
                            completion_tokens += usage3.get('completion_tokens', 0)
                except Exception as e:
                    logger.error(f'AI二次回复失败: {e}', exc_info=True)
                    response_text = '处理失败，请稍后重试'

        # Build response payload
        response_payload = {
            'assistant_message': None,
            'tool_results': None,
        }

        # Save assistant message (skip if empty content AND there are tool results)
        if response_text.strip() or not tool_results:
            elapsed = round(time.time() - start_time, 2)
            if elapsed < 0.01:
                elapsed = 0.01
            assistant_message = AiChatMessage(
                chat_id=chat_id,
                role='assistant',
                content=response_text,
                tokens_used=tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                elapsed=elapsed,
            )
            db.session.add(assistant_message)
            db.session.flush()
            response_payload['assistant_message'] = assistant_message.to_dict()

        # If there are tool results, save each as a message and return IDs
        if tool_results:
            saved_tool_messages = []
            for tr in tool_results:
                result = tr['result']
                # 信息查询结果：只有show_all_fields=true时才创建卡片，否则交给AI二次回复
                if result and result.get('action_type') == 'lookup' and result.get('show_all_fields'):
                    lookup_meta = {
                        '_type': 'lookup',
                        'tool_data': result,
                        '_done': True,
                        '_failed': bool(result.get('error')),
                    }
                    if result.get('error'):
                        lookup_meta['_error_msg'] = result['error']
                    tool_msg = AiChatMessage(
                        chat_id=chat_id,
                        role='assistant',
                        content='',
                        msg_metadata=json.dumps(lookup_meta, ensure_ascii=False),
                    )
                    db.session.add(tool_msg)
                    db.session.flush()
                    saved_tool_messages.append({
                        'tool_call_id': tr['tool_call_id'],
                        'name': tr['name'],
                        'result': result,
                        'message_id': tool_msg.id,
                    })
                # 导出/查询/系统任务确认卡片（API自动执行的系统任务不创建卡片，由AI二次回复反馈）
                elif result and not result.get('error') and result.get('action_type') in ('export', 'query', 'system_task'):
                    if result.get('auto_executed'):
                        # API自动执行的系统任务，不创建确认卡片，结果由AI二次回复直接反馈
                        saved_tool_messages.append(tr)
                    else:
                        tool_msg = AiChatMessage(
                            chat_id=chat_id,
                            role='assistant',
                            content='',
                            msg_metadata=json.dumps({
                                '_type': 'tool',
                                'tool_data': result,
                            }, ensure_ascii=False),
                        )
                        db.session.add(tool_msg)
                        db.session.flush()
                        saved_tool_messages.append({
                            'tool_call_id': tr['tool_call_id'],
                            'name': tr['name'],
                            'result': result,
                            'message_id': tool_msg.id,
                        })
                # 选项选择卡片（_select_mode）
                elif result and result.get('_select_mode'):
                    # 确定 action_type
                    if tr['name'] == 'list_export_options':
                        action_type = 'export'
                    elif tr['name'] == 'list_query_options':
                        action_type = 'query'
                    elif tr['name'] == 'list_system_tasks':
                        action_type = 'system_task'
                    elif tr['name'] == 'list_lookup_options':
                        action_type = 'lookup'
                    else:
                        action_type = 'export'
                    tool_msg = AiChatMessage(
                        chat_id=chat_id,
                        role='assistant',
                        content=result.get('message', ''),
                        msg_metadata=json.dumps({
                            '_type': 'select_options',
                            '_select_mode': result['_select_mode'],
                            'scripts': result.get('scripts', result.get('tasks', [])),
                            'action_type': action_type,
                        }, ensure_ascii=False),
                    )
                    db.session.add(tool_msg)
                    db.session.flush()
                    saved_tool_messages.append({
                        'tool_call_id': tr['tool_call_id'],
                        'name': tr['name'],
                        'result': result,
                        'message_id': tool_msg.id,
                    })
                else:
                    saved_tool_messages.append(tr)
            response_payload['tool_results'] = saved_tool_messages

        db.session.commit()

        # 记录成功的工具调用记忆
        if tool_results:
            for tr in tool_results:
                result = tr.get('result', {})
                if result and not result.get('error') and tr.get('name') in ('request_lookup', 'request_export', 'request_query', 'request_system_task'):
                    try:
                        desc = result.get('description', '') or result.get('confirm_message', '')
                        if desc:
                            AiService.record_tool_memory(
                                user_id=current_user.id,
                                intent=desc[:200],
                                tool_name=tr['name'],
                                tool_args={'name': result.get('script_name') or result.get('task_name', '')},
                            )
                    except Exception as mem_err:
                        logger.warning(f'记录工具记忆失败: {mem_err}')

        # Track behavior
        from app.utils.behavior_tracker import track_behavior as _track
        _track(current_user.id, 'chat', 'ai_chat', chat_id, {'tokens': tokens})

        return jsonify({'success': True, 'data': response_payload})
    except Exception as e:
        logger.error(f'AI对话失败: {e}', exc_info=True)
        assistant_message = AiChatMessage(
            chat_id=chat_id,
            role='assistant',
            content='AI服务调用失败，请稍后重试',
        )
        db.session.add(assistant_message)
        db.session.commit()
        return jsonify({'success': True, 'data': {
            'user_message': user_message.to_dict(),
            'assistant_message': assistant_message.to_dict(),
        }})


@ai_bp.route('/chats/<int:chat_id>/send-stream', methods=['POST'])
@login_required
def send_message_stream(chat_id):
    """流式发送消息，支持深度思考模型的逐字输出"""
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400

    user_message = AiChatMessage(
        chat_id=chat_id,
        role='user',
        content=data['content'],
    )
    db.session.add(user_message)

    if not chat.title or chat.title == '新对话':
        chat.title = data['content'][:50]

    specified_config_id = data.get('ai_config_id')
    specified_config = None
    if specified_config_id:
        specified_config = AiConfig.query.filter_by(id=int(specified_config_id), is_active=True).first()

    from app.services.ai_service import AiService
    ordered_configs = AiService.get_ordered_configs()

    if specified_config:
        ai_config = specified_config
        ordered_configs = [specified_config]
    elif ordered_configs:
        ai_config = ordered_configs[0]
    else:
        db.session.commit()
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'content': 'AI服务未配置'}, ensure_ascii=False)}\n\n"
        return Response(stream_with_context(error_gen()), mimetype='text/event-stream')

    # 根据模型配置决定是否启用流式请求AI API
    config_enable_streaming = ai_config.enable_streaming if ai_config.enable_streaming is not None else True

    # 构建上下文
    try:
        context = AiService.build_chat_context(current_user.id, chat_id)
        history = AiChatMessage.query.filter_by(chat_id=chat_id)\
            .order_by(AiChatMessage.created_at.asc()).all()
        messages = []
        if ai_config.system_prompt:
            messages.append({'role': 'system', 'content': ai_config.system_prompt})
        else:
            sys_prompt = context + '\n\n## 重要规则\n' \
                '- 系统中有四种不同类型的任务，必须严格区分：\n' \
                '  1. 导出任务（export）：从数据库导出数据到Excel\n' \
                '  2. 查询任务（query）：根据Excel文件中的主键数据去数据库批量查询匹配信息\n' \
                '  3. 系统任务（system_task）：后台运维类操作\n' \
                '  4. 信息查询（lookup）：根据参数值快速查询数据库返回结果\n' \
                '- 重要：当用户的查询涉及多个不同维度的信息时（如"查一下SN123的绑定状态和交易信息"），应在同一次回复中同时调用多个 request_lookup 工具，分别查询不同维度的信息，然后将所有查询结果归总后统一回答用户\n' \
                '- 重要：当用户的意图是条件性的（如"查一下这个SN的绑定状态，如果已绑定就解绑"、"查商户是否激活，未激活则激活"），必须先调用 request_lookup 查询状态，拿到结果后根据条件判断是否需要调用 request_system_task，在二次回复中完成条件判断和后续操作\n' \
                '- 重要：API类型的系统任务参数齐全时会自动执行并返回结果（包含mapping_summary映射摘要），请直接根据映射摘要用自然语言告诉用户执行结果\n' \
                '- 重要：如果用户同时要求对多个对象执行同样的API系统任务（如"解绑SN001、SN002、SN003"），请在同一次回复中同时调用多个 request_system_task，每个调用对应一个对象，系统会自动并行执行，你只需汇总所有结果用列表形式反馈给用户\n' \
                '- 重要：调用 list_lookup_options 时，如果用户提供了具体的参数值（如SN号、商户号等），务必同时传入 params 参数，这样当匹配到唯一查询时系统可以自动执行，大幅加快响应速度\n'
            messages.append({'role': 'system', 'content': sys_prompt})

        for msg in history:
            messages.append({'role': msg.role, 'content': msg.content})

    except Exception as e:
        logger.error(f'构建上下文失败: {e}', exc_info=True)
        db.session.commit()
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'content': f'构建上下文失败'}, ensure_ascii=False)}\n\n"
        return Response(stream_with_context(error_gen()), mimetype='text/event-stream')

    db.session.commit()

    # 在请求上下文内保存需要的变量，避免在 generate() 闭包中访问过期的 SQLAlchemy session
    user_id = current_user.id
    user_message_content = data['content']
    config_api_key = ai_config.get_api_key()
    config_api_base = ai_config.api_base or 'https://api.openai.com/v1'
    config_model_name = ai_config.model_name or 'gpt-3.5-turbo'
    config_max_tokens = ai_config.max_tokens or 4096
    config_temperature = ai_config.temperature if ai_config.temperature is not None else 0.7
    config_enable_thinking = ai_config.enable_thinking or False

    def generate():
        full_content = ''
        thinking_content = ''
        tokens_used = 0
        prompt_tokens_used = 0
        completion_tokens_used = 0
        accumulated_tool_calls = {}  # {index: {id, function: {name, arguments}}}

        # 注册活跃流
        request_id = str(uuid.uuid4())
        _active_streams[chat_id] = {'aborted': False, 'request_id': request_id}
        start_time = time.time()

        # 先发送一个心跳事件，确认SSE连接已建立
        yield f"data: {json.dumps({'type': 'heartbeat'}, ensure_ascii=False)}\n\n"

        try:
            api_key = config_api_key
            api_base = config_api_base
            url = f"{api_base.rstrip('/')}/chat/completions"

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }

            payload = {
                'model': config_model_name,
                'messages': messages,
                'max_tokens': config_max_tokens,
                'temperature': config_temperature,
                'stream': config_enable_streaming,
            }

            # 添加工具定义
            from app.services.ai_service import AI_TOOLS
            payload['tools'] = AI_TOOLS
            payload['tool_choice'] = 'auto'

            if config_enable_streaming:
                # 流式请求AI API
                logger.info(f'流式请求开始: model={config_model_name}, url={url}')
                resp = requests.post(url, headers=headers, json=payload, timeout=180, stream=True)
                logger.info(f'流式请求响应状态: {resp.status_code}')
                resp.raise_for_status()
                # 确保使用UTF-8解码，避免中文乱码（部分API不返回charset头）
                resp.encoding = 'utf-8'

                chunk_count = 0
                for line in resp.iter_lines(decode_unicode=True):
                    # 检查是否被用户终止
                    if _active_streams.get(chat_id, {}).get('aborted'):
                        logger.info(f'流式请求被用户终止: chat_id={chat_id}')
                        break
                    if not line:
                        continue
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            logger.info(f'流式请求完成，共处理 {chunk_count} 个数据块')
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                # 处理思考内容（reasoning_content 或 thinking）
                                reasoning = delta.get('reasoning_content') or delta.get('thinking') or ''
                                if reasoning:
                                    thinking_content += reasoning
                                    chunk_count += 1
                                    if config_enable_thinking:
                                        yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning}, ensure_ascii=False)}\n\n"
                                # 处理正文内容
                                content_delta = delta.get('content', '') or ''
                                if content_delta:
                                    full_content += content_delta
                                    chunk_count += 1
                                    yield f"data: {json.dumps({'type': 'content', 'content': content_delta}, ensure_ascii=False)}\n\n"
                                # 累积工具调用
                                tool_calls_delta = delta.get('tool_calls')
                                if tool_calls_delta:
                                    for tc in tool_calls_delta:
                                        idx = tc.get('index', 0)
                                        if idx not in accumulated_tool_calls:
                                            accumulated_tool_calls[idx] = {
                                                'id': tc.get('id', ''),
                                                'type': tc.get('type', 'function'),
                                                'function': {'name': '', 'arguments': ''},
                                            }
                                        if tc.get('id'):
                                            accumulated_tool_calls[idx]['id'] = tc['id']
                                        if tc.get('type'):
                                            accumulated_tool_calls[idx]['type'] = tc['type']
                                        fn = tc.get('function', {})
                                        if fn.get('name'):
                                            accumulated_tool_calls[idx]['function']['name'] = fn['name']
                                        if fn.get('arguments'):
                                            accumulated_tool_calls[idx]['function']['arguments'] += fn['arguments']
                            # token 统计
                            if chunk.get('usage'):
                                tokens_used = chunk['usage'].get('total_tokens', 0)
                                prompt_tokens_used = chunk['usage'].get('prompt_tokens', 0)
                                completion_tokens_used = chunk['usage'].get('completion_tokens', 0)
                        except json.JSONDecodeError:
                            continue

            else:
                # 非流式请求AI API（enable_streaming=False）
                logger.info(f'非流式请求开始: model={config_model_name}, url={url}')
                resp = requests.post(url, headers=headers, json=payload, timeout=180)
                logger.info(f'非流式请求响应状态: {resp.status_code}')
                resp.raise_for_status()

                result = resp.json()
                choices = result.get('choices', [])
                if choices:
                    message = choices[0].get('message', {})
                    # 处理思考内容
                    reasoning = message.get('reasoning_content') or message.get('thinking') or ''
                    if reasoning:
                        thinking_content = reasoning
                        if config_enable_thinking:
                            yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning}, ensure_ascii=False)}\n\n"
                    # 处理正文内容
                    content_text = message.get('content', '') or ''
                    if content_text:
                        full_content = content_text
                        yield f"data: {json.dumps({'type': 'content', 'content': content_text}, ensure_ascii=False)}\n\n"
                    # 处理工具调用
                    tool_calls_resp = message.get('tool_calls', [])
                    for tc in tool_calls_resp:
                        idx = len(accumulated_tool_calls)
                        accumulated_tool_calls[idx] = {
                            'id': tc.get('id', ''),
                            'type': tc.get('type', 'function'),
                            'function': tc.get('function', {}),
                        }
                # token 统计
                if result.get('usage'):
                    tokens_used = result['usage'].get('total_tokens', 0)
                    prompt_tokens_used = result['usage'].get('prompt_tokens', 0)
                    completion_tokens_used = result['usage'].get('completion_tokens', 0)

            # 处理工具调用
            tool_results_list = []
            if _active_streams.get(chat_id, {}).get('aborted'):
                # 用户已终止请求，跳过工具调用
                logger.info(f'工具调用前检测到终止: chat_id={chat_id}')
                yield f"data: {json.dumps({'type': 'aborted', 'content': '任务已被用户手动终止'}, ensure_ascii=False)}\n\n"
            elif accumulated_tool_calls:
                from app.services.ai_service import AiService
                for idx in sorted(accumulated_tool_calls.keys()):
                    tc = accumulated_tool_calls[idx]
                    func_name = tc['function']['name']
                    func_args = tc['function']['arguments']
                    logger.info(f'流式AI调用工具: {func_name}({func_args})')
                    result = AiService.execute_tool_call(func_name, func_args, user_id)
                    # 解析参数供后续自动执行使用
                    try:
                        args = json.loads(func_args) if func_args else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_results_list.append({
                        'tool_call_id': tc['id'],
                        'name': func_name,
                        'result': result,
                    })

                    # 信息查询唯一匹配自动执行优化
                    if func_name == 'list_lookup_options' and not result.get('error'):
                        if result.get('total', 0) == 1:
                            script = result['scripts'][0]
                            logger.info(f'流式-匹配到唯一信息查询: {script["name"]}，自动执行查询')
                            auto_params = args.get('params', {})
                            if not auto_params and script.get('params'):
                                auto_params = AiService.extract_params_from_message(
                                    user_message_content, script['params'])
                                if auto_params:
                                    logger.info(f'流式-从用户消息中提取到参数: {auto_params}')
                            auto_result = AiService._tool_request_lookup({
                                'lookup_name': script['name'],
                                'description': args.get('description', '') or user_message_content[:200],
                                'params': auto_params,
                            }, user_id)
                            # 添加自动执行标记，告诉AI这是已完成的查询结果
                            auto_result['_auto_executed'] = True
                            auto_result['_hint'] = '此查询已自动执行完成，结果如下。请直接根据查询结果回答用户问题，不要再次调用request_lookup。'
                            tool_results_list[-1] = {
                                'tool_call_id': tc['id'],
                                'name': 'request_lookup',
                                'result': auto_result,
                            }
                            # 同步更新accumulated_tool_calls中的工具名，确保后续判断正确
                            accumulated_tool_calls[idx]['function']['name'] = 'request_lookup'
                            accumulated_tool_calls[idx]['function']['arguments'] = json.dumps({
                                'lookup_name': script['name'],
                                'description': args.get('description', '') or user_message_content[:200],
                                'params': auto_params,
                            }, ensure_ascii=False)
                        elif result.get('total', 0) > 1:
                            result['_select_mode'] = 'multi'
                            result['message'] = f'找到 {result["total"]} 个匹配的信息查询，请选择要使用的查询'

                # 处理工具结果（与普通send相同的逻辑）
                saved_tool_messages = []
                try:
                    for tr in tool_results_list:
                        result = tr['result']
                        # 信息查询：只有show_all_fields=true时才创建卡片，否则交给AI二次回复
                        if result and result.get('action_type') == 'lookup' and result.get('show_all_fields'):
                            lookup_meta = {
                                '_type': 'lookup', 'tool_data': result,
                                '_done': True, '_failed': bool(result.get('error')),
                            }
                            if result.get('error'):
                                lookup_meta['_error_msg'] = result['error']
                            tool_msg = AiChatMessage(
                                chat_id=chat_id, role='assistant', content='',
                                msg_metadata=json.dumps(lookup_meta, ensure_ascii=False),
                            )
                            db.session.add(tool_msg)
                            db.session.flush()
                            saved_tool_messages.append({
                                'tool_call_id': tr['tool_call_id'],
                                'name': tr['name'],
                                'result': result,
                                'message_id': tool_msg.id,
                            })
                        # 导出/查询/系统任务（API自动执行的不创建卡片，由AI二次回复反馈）
                        elif result and not result.get('error') and result.get('action_type') in ('export', 'query', 'system_task'):
                            if result.get('auto_executed'):
                                # API自动执行的系统任务，不创建确认卡片
                                saved_tool_messages.append(tr)
                            else:
                                tool_msg = AiChatMessage(
                                    chat_id=chat_id, role='assistant', content='',
                                    msg_metadata=json.dumps({
                                        '_type': 'tool', 'tool_data': result,
                                    }, ensure_ascii=False),
                                )
                                db.session.add(tool_msg)
                                db.session.flush()
                                saved_tool_messages.append({
                                    'tool_call_id': tr['tool_call_id'],
                                    'name': tr['name'],
                                    'result': result,
                                    'message_id': tool_msg.id,
                                })
                        # 选项选择卡片
                        elif result and result.get('_select_mode'):
                            if tr['name'] == 'list_export_options':
                                action_type = 'export'
                            elif tr['name'] == 'list_query_options':
                                action_type = 'query'
                            elif tr['name'] == 'list_system_tasks':
                                action_type = 'system_task'
                            elif tr['name'] == 'list_lookup_options':
                                action_type = 'lookup'
                            else:
                                action_type = 'export'
                            tool_msg = AiChatMessage(
                                chat_id=chat_id, role='assistant',
                                content=result.get('message', ''),
                                msg_metadata=json.dumps({
                                    '_type': 'select_options',
                                    '_select_mode': result['_select_mode'],
                                    'scripts': result.get('scripts', result.get('tasks', [])),
                                    'action_type': action_type,
                                }, ensure_ascii=False),
                            )
                            db.session.add(tool_msg)
                            db.session.flush()
                            saved_tool_messages.append({
                                'tool_call_id': tr['tool_call_id'],
                                'name': tr['name'],
                                'result': result,
                                'message_id': tool_msg.id,
                            })
                        else:
                            saved_tool_messages.append(tr)
                except Exception as db_err:
                    logger.error(f'流式响应保存工具消息失败: {db_err}', exc_info=True)
                    try:
                        db.session.rollback()
                    except:
                        pass

                # 发送工具结果给前端
                yield f"data: {json.dumps({'type': 'tool_results', 'tool_results': saved_tool_messages}, ensure_ascii=False)}\n\n"

                # 检查是否需要AI二次回复
                # 信息查询(request_lookup)：只有所有lookup都是show_all_fields=true时才跳过AI二次回复
                # API系统任务自动执行(auto_executed)：走AI二次回复流程，让AI根据映射结果反馈用户
                action_tools = {'request_export', 'request_query', 'request_system_task'}
                all_tool_calls = [accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())]
                has_action = any(tc['function']['name'] in action_tools for tc in all_tool_calls)
                # 检查是否有自动执行的API系统任务（需要AI二次回复反馈结果）
                has_auto_exec_system_task = any(
                    tr.get('result', {}).get('auto_executed', False)
                    for tr in tool_results_list
                    if tr.get('result', {}).get('action_type') == 'system_task'
                )
                logger.info(f'流式路由-自动执行检测: has_auto_exec_system_task={has_auto_exec_system_task}, has_action={has_action}')
                # 如果所有system_task都是auto_executed，则不算action
                if has_auto_exec_system_task:
                    all_system_task_auto = all(
                        tr.get('result', {}).get('auto_executed', False)
                        for tr in tool_results_list
                        if tr.get('result', {}).get('action_type') == 'system_task'
                    )
                    if all_system_task_auto:
                        has_action = False
                lookup_tc_exists = any(tc['function']['name'] == 'request_lookup' for tc in all_tool_calls)
                has_lookup_needs_reply = any(
                    not tr.get('result', {}).get('show_all_fields', False)
                    for tr in tool_results_list
                    if tr.get('result', {}).get('action_type') == 'lookup'
                ) if lookup_tc_exists else False
                has_select = any(tr.get('result', {}).get('_select_mode') for tr in tool_results_list)

                if not has_action and not has_select and (has_lookup_needs_reply or has_auto_exec_system_task or not lookup_tc_exists):
                    # 需要AI二次回复：1)有lookup需要归总结果；2)API系统任务自动执行需要反馈结果；3)非操作型工具需要AI回复
                    logger.info(f'流式路由-进入AI二次回复: has_lookup_needs_reply={has_lookup_needs_reply}, has_auto_exec_system_task={has_auto_exec_system_task}, lookup_tc_exists={lookup_tc_exists}')
                    tool_messages = []
                    for tr in tool_results_list:
                        result = tr.get('result', {})
                        # 对auto_executed的系统任务结果精简，避免过大导致AI无法处理
                        if result.get('auto_executed') and result.get('action_type') == 'system_task':
                            concise_result = {
                                'action_type': 'system_task',
                                'task_name': result.get('task_name', ''),
                                'auto_executed': True,
                                'success': result.get('success', False),
                                'status_code': result.get('status_code'),
                                'mapping_summary': result.get('mapping_summary', ''),
                                'mapping_info': result.get('mapping_info', ''),
                            }
                            if result.get('error'):
                                concise_result['error'] = result['error']
                            # 如果mapping_summary为空，附上简化的response
                            if not result.get('mapping_summary') and isinstance(result.get('response'), dict):
                                concise_result['response'] = result['response']
                            tool_messages.append({
                                'role': 'tool',
                                'tool_call_id': tr['tool_call_id'],
                                'content': json.dumps(concise_result, ensure_ascii=False),
                            })
                        else:
                            tool_messages.append({
                                'role': 'tool',
                                'tool_call_id': tr['tool_call_id'],
                                'content': json.dumps(result, ensure_ascii=False),
                            })

                    # 构建二次请求的消息列表
                    messages.append({
                        'role': 'assistant',
                        'content': full_content,
                        'tool_calls': [accumulated_tool_calls[idx] for idx in sorted(accumulated_tool_calls.keys())],
                    })
                    messages.extend(tool_messages)

                    # 请求AI二次回复
                    # 构建二次回复提示
                    reply_hints = []
                    if has_lookup_needs_reply:
                        reply_hints.append('上面的信息查询已经执行完成并返回了结果。请根据查询结果回答用户问题。如果用户意图是条件性的（如满足条件则执行系统任务），请根据查询结果判断是否需要调用request_system_task等工具。不要重复调用request_lookup。')
                    if has_auto_exec_system_task:
                        reply_hints.append('上面的API系统任务已经自动执行完成并返回了结果。请根据mapping_summary（映射摘要）直接用自然语言告诉用户执行结果，如果多个任务请用列表汇总。不要重复调用request_system_task。')
                    if reply_hints:
                        messages.append({
                            'role': 'system',
                            'content': '\n'.join(reply_hints)
                        })

                    payload2 = {
                        'model': config_model_name,
                        'messages': messages,
                        'max_tokens': config_max_tokens,
                        'temperature': config_temperature,
                        'stream': config_enable_streaming,
                        'tools': AI_TOOLS,
                        'tool_choice': 'auto',
                    }

                    second_full_content = ''
                    second_thinking_content = ''
                    second_accumulated_tool_calls = {}

                    if config_enable_streaming:
                        resp2 = requests.post(url, headers=headers, json=payload2, timeout=180, stream=True)
                        resp2.raise_for_status()
                        resp2.encoding = 'utf-8'
                        for line2 in resp2.iter_lines(decode_unicode=True):
                            if not line2:
                                continue
                            if line2.startswith('data: '):
                                data_str2 = line2[6:]
                                if data_str2.strip() == '[DONE]':
                                    break
                                try:
                                    chunk2 = json.loads(data_str2)
                                    choices2 = chunk2.get('choices', [])
                                    if choices2:
                                        delta2 = choices2[0].get('delta', {})
                                        reasoning2 = delta2.get('reasoning_content') or delta2.get('thinking') or ''
                                        if reasoning2:
                                            second_thinking_content += reasoning2
                                            if config_enable_thinking:
                                                yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning2}, ensure_ascii=False)}\n\n"
                                        content_delta2 = delta2.get('content', '') or ''
                                        if content_delta2:
                                            second_full_content += content_delta2
                                            full_content += content_delta2
                                            yield f"data: {json.dumps({'type': 'content', 'content': content_delta2}, ensure_ascii=False)}\n\n"
                                        tool_calls_delta2 = delta2.get('tool_calls')
                                        if tool_calls_delta2:
                                            for tc2 in tool_calls_delta2:
                                                idx2 = tc2.get('index', 0)
                                                if idx2 not in second_accumulated_tool_calls:
                                                    second_accumulated_tool_calls[idx2] = {
                                                        'id': tc2.get('id', ''),
                                                        'type': tc2.get('type', 'function'),
                                                        'function': {'name': '', 'arguments': ''},
                                                    }
                                                if tc2.get('id'):
                                                    second_accumulated_tool_calls[idx2]['id'] = tc2['id']
                                                if tc2.get('type'):
                                                    second_accumulated_tool_calls[idx2]['type'] = tc2['type']
                                                fn2 = tc2.get('function', {})
                                                if fn2.get('name'):
                                                    second_accumulated_tool_calls[idx2]['function']['name'] = fn2['name']
                                                if fn2.get('arguments'):
                                                    second_accumulated_tool_calls[idx2]['function']['arguments'] += fn2['arguments']
                                        if chunk2.get('usage'):
                                            tokens_used = chunk2['usage'].get('total_tokens', 0)
                                            prompt_tokens_used += chunk2['usage'].get('prompt_tokens', 0)
                                            completion_tokens_used += chunk2['usage'].get('completion_tokens', 0)
                                except json.JSONDecodeError:
                                    continue
                    else:
                        resp2 = requests.post(url, headers=headers, json=payload2, timeout=180)
                        resp2.raise_for_status()
                        result2 = resp2.json()
                        choices2 = result2.get('choices', [])
                        if choices2:
                            msg2 = choices2[0].get('message', {})
                            reasoning2 = msg2.get('reasoning_content') or msg2.get('thinking') or ''
                            if reasoning2:
                                second_thinking_content = reasoning2
                                thinking_content += reasoning2
                                if config_enable_thinking:
                                    yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning2}, ensure_ascii=False)}\n\n"
                            content_text2 = msg2.get('content', '') or ''
                            if content_text2:
                                second_full_content = content_text2
                                full_content += content_text2
                                yield f"data: {json.dumps({'type': 'content', 'content': content_text2}, ensure_ascii=False)}\n\n"
                            tool_calls_resp2 = msg2.get('tool_calls', [])
                            for tc2 in tool_calls_resp2:
                                idx2 = len(second_accumulated_tool_calls)
                                second_accumulated_tool_calls[idx2] = {
                                    'id': tc2.get('id', ''),
                                    'type': tc2.get('type', 'function'),
                                    'function': tc2.get('function', {}),
                                }
                        if result2.get('usage'):
                            tokens_used = result2['usage'].get('total_tokens', 0)
                            prompt_tokens_used += result2['usage'].get('prompt_tokens', 0)
                            completion_tokens_used += result2['usage'].get('completion_tokens', 0)

                    # 处理二次回复中的工具调用
                    if second_accumulated_tool_calls:
                        second_tool_results_list = []
                        for idx2 in sorted(second_accumulated_tool_calls.keys()):
                            tc2 = second_accumulated_tool_calls[idx2]
                            func_name2 = tc2['function']['name']
                            func_args2 = tc2['function']['arguments']
                            logger.info(f'流式AI二次回复调用工具: {func_name2}({func_args2})')
                            result2 = AiService.execute_tool_call(func_name2, func_args2, user_id)
                            second_tool_results_list.append({
                                'tool_call_id': tc2['id'],
                                'name': func_name2,
                                'result': result2,
                            })

                        # 保存二次工具消息
                        second_saved_tool_messages = []
                        try:
                            for tr2 in second_tool_results_list:
                                result2 = tr2['result']
                                # 信息查询：只有show_all_fields=true时才创建卡片
                                if result2 and result2.get('action_type') == 'lookup' and result2.get('show_all_fields'):
                                    lookup_meta2 = {
                                        '_type': 'lookup', 'tool_data': result2,
                                        '_done': True, '_failed': bool(result2.get('error')),
                                    }
                                    if result2.get('error'):
                                        lookup_meta2['_error_msg'] = result2['error']
                                    tool_msg2 = AiChatMessage(
                                        chat_id=chat_id, role='assistant', content='',
                                        msg_metadata=json.dumps(lookup_meta2, ensure_ascii=False),
                                    )
                                    db.session.add(tool_msg2)
                                    db.session.flush()
                                    second_saved_tool_messages.append({
                                        'tool_call_id': tr2['tool_call_id'],
                                        'name': tr2['name'],
                                        'result': result2,
                                        'message_id': tool_msg2.id,
                                    })
                                elif result2 and result2.get('action_type') == 'lookup':
                                    # show_all_fields=false，不创建卡片，由AI三次回复自然语言回答
                                    second_saved_tool_messages.append(tr2)
                                elif result2 and not result2.get('error') and result2.get('action_type') in ('export', 'query', 'system_task'):
                                    if result2.get('auto_executed'):
                                        # API自动执行的系统任务，不创建确认卡片
                                        second_saved_tool_messages.append(tr2)
                                    else:
                                        tool_msg2 = AiChatMessage(
                                            chat_id=chat_id, role='assistant', content='',
                                            msg_metadata=json.dumps({
                                                '_type': 'tool', 'tool_data': result2,
                                            }, ensure_ascii=False),
                                        )
                                        db.session.add(tool_msg2)
                                        db.session.flush()
                                        second_saved_tool_messages.append({
                                            'tool_call_id': tr2['tool_call_id'],
                                            'name': tr2['name'],
                                            'result': result2,
                                            'message_id': tool_msg2.id,
                                        })
                                elif result2 and result2.get('_select_mode'):
                                    if tr2['name'] == 'list_export_options':
                                        action_type2 = 'export'
                                    elif tr2['name'] == 'list_query_options':
                                        action_type2 = 'query'
                                    elif tr2['name'] == 'list_system_tasks':
                                        action_type2 = 'system_task'
                                    elif tr2['name'] == 'list_lookup_options':
                                        action_type2 = 'lookup'
                                    else:
                                        action_type2 = 'export'
                                    tool_msg2 = AiChatMessage(
                                        chat_id=chat_id, role='assistant',
                                        content=result2.get('message', ''),
                                        msg_metadata=json.dumps({
                                            '_type': 'select_options',
                                            '_select_mode': result2['_select_mode'],
                                            'scripts': result2.get('scripts', result2.get('tasks', [])),
                                            'action_type': action_type2,
                                        }, ensure_ascii=False),
                                    )
                                    db.session.add(tool_msg2)
                                    db.session.flush()
                                    second_saved_tool_messages.append({
                                        'tool_call_id': tr2['tool_call_id'],
                                        'name': tr2['name'],
                                        'result': result2,
                                        'message_id': tool_msg2.id,
                                    })
                                else:
                                    second_saved_tool_messages.append(tr2)
                        except Exception as db_err2:
                            logger.error(f'流式响应保存二次工具消息失败: {db_err2}', exc_info=True)
                            try:
                                db.session.rollback()
                            except:
                                pass

                        # 发送二次工具结果给前端
                        yield f"data: {json.dumps({'type': 'tool_results', 'tool_results': second_saved_tool_messages}, ensure_ascii=False)}\n\n"

                        # 如果二次工具调用也是非操作型的，还需要AI三次回复
                        second_all_tool_calls = [second_accumulated_tool_calls[idx2] for idx2 in sorted(second_accumulated_tool_calls.keys())]
                        second_has_action = any(tc2['function']['name'] in action_tools for tc2 in second_all_tool_calls)
                        second_has_select = any(tr2.get('result', {}).get('_select_mode') for tr2 in second_tool_results_list)
                        second_lookup_tc_exists = any(tc2['function']['name'] == 'request_lookup' for tc2 in second_all_tool_calls)
                        second_has_lookup_needs_reply = any(
                            not tr2.get('result', {}).get('show_all_fields', False)
                            for tr2 in second_tool_results_list
                            if tr2.get('result', {}).get('action_type') == 'lookup'
                        ) if second_lookup_tc_exists else False

                        if not second_has_action and not second_has_select and (second_has_lookup_needs_reply or not second_lookup_tc_exists):
                            if second_has_lookup_needs_reply:
                                # 有lookup需要归总，必须请求AI三次回复
                                try:
                                    tool_messages2 = []
                                    for tr2 in second_tool_results_list:
                                        tool_messages2.append({
                                            'role': 'tool',
                                            'tool_call_id': tr2['tool_call_id'],
                                            'content': json.dumps(tr2['result'], ensure_ascii=False),
                                        })
                                    messages.append({
                                        'role': 'assistant',
                                        'content': second_full_content,
                                        'tool_calls': [second_accumulated_tool_calls[idx2] for idx2 in sorted(second_accumulated_tool_calls.keys())],
                                    })
                                    messages.extend(tool_messages2)
                                    payload3 = {
                                        'model': config_model_name,
                                        'messages': messages,
                                        'max_tokens': config_max_tokens,
                                        'temperature': config_temperature,
                                    }
                                    resp3 = requests.post(url, headers=headers, json=payload3, timeout=120)
                                    resp3.raise_for_status()
                                    result3 = resp3.json()
                                    final_text = result3.get('choices', [{}])[0].get('message', {}).get('content', '')
                                    if final_text:
                                        full_content += final_text
                                        yield f"data: {json.dumps({'type': 'content', 'content': final_text}, ensure_ascii=False)}\n\n"
                                    if result3.get('usage'):
                                        tokens_used = result3['usage'].get('total_tokens', 0)
                                        prompt_tokens_used += result3['usage'].get('prompt_tokens', 0)
                                        completion_tokens_used += result3['usage'].get('completion_tokens', 0)
                                except Exception as e3:
                                    logger.error(f'流式AI三次回复失败: {e3}', exc_info=True)
                            elif second_full_content:
                                # 非lookup工具调用，AI已经在二次回复中生成了文本，直接使用
                                pass
                            else:
                                # 需要AI三次回复（简化处理：直接请求非流式）
                                try:
                                    tool_messages2 = []
                                    for tr2 in second_tool_results_list:
                                        tool_messages2.append({
                                            'role': 'tool',
                                            'tool_call_id': tr2['tool_call_id'],
                                            'content': json.dumps(tr2['result'], ensure_ascii=False),
                                        })
                                    messages.append({
                                        'role': 'assistant',
                                        'content': second_full_content,
                                        'tool_calls': [second_accumulated_tool_calls[idx2] for idx2 in sorted(second_accumulated_tool_calls.keys())],
                                    })
                                    messages.extend(tool_messages2)
                                    payload3 = {
                                        'model': config_model_name,
                                        'messages': messages,
                                        'max_tokens': config_max_tokens,
                                        'temperature': config_temperature,
                                    }
                                    resp3 = requests.post(url, headers=headers, json=payload3, timeout=120)
                                    resp3.raise_for_status()
                                    result3 = resp3.json()
                                    final_text = result3.get('choices', [{}])[0].get('message', {}).get('content', '')
                                    if final_text:
                                        full_content += final_text
                                        yield f"data: {json.dumps({'type': 'content', 'content': final_text}, ensure_ascii=False)}\n\n"
                                    if result3.get('usage'):
                                        tokens_used = result3['usage'].get('total_tokens', 0)
                                        prompt_tokens_used += result3['usage'].get('prompt_tokens', 0)
                                        completion_tokens_used += result3['usage'].get('completion_tokens', 0)
                                except Exception as e3:
                                    logger.error(f'流式AI三次回复失败: {e3}', exc_info=True)

            # 流式结束，保存消息
            try:
                elapsed = round(time.time() - start_time, 2)
                if elapsed < 0.01:
                    elapsed = 0.01
                assistant_message = AiChatMessage(
                    chat_id=chat_id,
                    role='assistant',
                    content=full_content,
                    tokens_used=tokens_used,
                    prompt_tokens=prompt_tokens_used,
                    completion_tokens=completion_tokens_used,
                    elapsed=elapsed,
                )
                if thinking_content:
                    assistant_message.msg_metadata = json.dumps({
                        'thinking_content': thinking_content,
                    }, ensure_ascii=False)
                db.session.add(assistant_message)
                db.session.commit()
                msg_id = assistant_message.id

                # 记录成功的工具调用记忆
                if tool_results_list:
                    for tr in tool_results_list:
                        result = tr.get('result', {})
                        if result and not result.get('error') and tr.get('name') in ('request_lookup', 'request_export', 'request_query', 'request_system_task'):
                            try:
                                desc = result.get('description', '') or result.get('confirm_message', '')
                                if desc:
                                    AiService.record_tool_memory(
                                        user_id=user_id,
                                        intent=desc[:200],
                                        tool_name=tr['name'],
                                        tool_args={'name': result.get('script_name') or result.get('task_name', '')},
                                    )
                            except Exception as mem_err:
                                logger.warning(f'记录工具记忆失败: {mem_err}')
            except Exception as db_err:
                logger.error(f'流式响应保存AI消息失败: {db_err}', exc_info=True)
                try:
                    db.session.rollback()
                except:
                    pass
                msg_id = None

            # 清理活跃流
            _active_streams.pop(chat_id, None)

            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done', 'message_id': msg_id, 'tokens': tokens_used, 'prompt_tokens': prompt_tokens_used, 'completion_tokens': completion_tokens_used, 'elapsed': elapsed}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f'流式响应异常: {e}', exc_info=True)
            # 保存错误消息
            try:
                if full_content:
                    assistant_message = AiChatMessage(
                        chat_id=chat_id,
                        role='assistant',
                        content=full_content,
                    )
                    db.session.add(assistant_message)
                    db.session.commit()
            except Exception as db_err:
                logger.error(f'流式响应保存消息失败: {db_err}', exc_info=True)
                try:
                    db.session.rollback()
                except:
                    pass
            yield f"data: {json.dumps({'type': 'error', 'content': f'AI服务调用失败: {str(e)}'}, ensure_ascii=False)}\n\n"

        finally:
            # 确保清理活跃流
            _active_streams.pop(chat_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


# ============ Abort AI Request ============
@ai_bp.route('/chats/<int:chat_id>/abort', methods=['POST'])
@login_required
def abort_chat_request(chat_id):
    """终止正在进行的AI请求"""
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    stream_info = _active_streams.get(chat_id)
    if stream_info and not stream_info.get('aborted'):
        stream_info['aborted'] = True
        logger.info(f'用户终止AI请求: chat_id={chat_id}, request_id={stream_info.get("request_id")}')
        return jsonify({'success': True, 'message': '请求已终止'})
    return jsonify({'success': True, 'message': '无活跃请求'})


# ============ Update Message Metadata ============
@ai_bp.route('/chats/<int:chat_id>/messages/<int:msg_id>', methods=['PUT'])
@login_required
def update_message(chat_id, msg_id):
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    msg = AiChatMessage.query.filter_by(id=msg_id, chat_id=chat_id).first()
    if not msg:
        return jsonify({'success': False, 'message': '消息不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    if 'metadata' in data:
        new_meta = data['metadata']
        existing = {}
        if msg.msg_metadata:
            try:
                existing = json.loads(msg.msg_metadata)
            except:
                pass
        # 合并元数据，保留原有字段
        existing.update(new_meta)
        msg.msg_metadata = json.dumps(existing, ensure_ascii=False)
        db.session.commit()

    return jsonify({'success': True, 'data': msg.to_dict()})


# ============ Create Message (for saving result feedback) ============
@ai_bp.route('/chats/<int:chat_id>/messages', methods=['POST'])
@login_required
def create_message(chat_id):
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400

    msg = AiChatMessage(
        chat_id=chat_id,
        role='assistant',
        content=data['content'],
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'data': msg.to_dict()})


# ============ Admin: List All Users' Sessions ============
@ai_bp.route('/admin/chats', methods=['GET'])
@admin_required
def admin_list_chats():
    user_id = request.args.get('user_id', type=int)
    include_deleted = request.args.get('include_deleted', 'false') == 'true'

    query = AiChat.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if not include_deleted:
        query = query.filter_by(is_deleted=False)

    chats = query.order_by(AiChat.updated_at.desc()).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in chats]})


# ============ Admin: Restore Deleted Chat ============
@ai_bp.route('/admin/chats/<int:chat_id>/restore', methods=['PUT'])
@admin_required
def admin_restore_chat(chat_id):
    chat = AiChat.query.filter_by(id=chat_id, is_deleted=True).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在或未被删除'}), 404

    chat.is_deleted = False
    db.session.commit()
    return jsonify({'success': True, 'message': '恢复成功'})


@ai_bp.route('/admin/chats/batch-restore', methods=['POST'])
@admin_required
def batch_restore_chats():
    """批量恢复已删除对话"""
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids or not isinstance(ids, list):
        return jsonify({'success': False, 'message': '请提供要恢复的ID列表'}), 400

    restored_count = 0
    for chat_id in ids:
        chat = AiChat.query.filter_by(id=chat_id, is_deleted=True).first()
        if chat:
            chat.is_deleted = False
            restored_count += 1
    db.session.commit()
    return jsonify({'success': True, 'message': f'成功恢复 {restored_count} 个对话', 'restored_count': restored_count})


@ai_bp.route('/admin/chats/restore-all', methods=['PUT'])
@admin_required
def restore_all_chats():
    """恢复全部已删除对话"""
    count = AiChat.query.filter_by(is_deleted=True).update({'is_deleted': False})
    db.session.commit()
    return jsonify({'success': True, 'message': f'成功恢复 {count} 个对话', 'restored_count': count})
