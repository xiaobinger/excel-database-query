import json
import logging
import os
import uuid
from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from app import db
from app.models.ai_config import AiConfig
from app.models.ai_skill import AiSkill
from app.models.user_behavior import UserBehavior
from app.models.ai_chat import AiChat, AiChatMessage
from app.utils.auth import login_required, admin_required, get_current_user

logger = logging.getLogger(__name__)
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


# ============ AI Config ============
@ai_bp.route('/configs', methods=['GET'])
@admin_required
def get_configs():
    configs = AiConfig.query.order_by(AiConfig.created_at.desc()).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in configs]})


@ai_bp.route('/configs', methods=['POST'])
@admin_required
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
@admin_required
def update_config(config_id):
    config = AiConfig.query.get(config_id)
    if not config:
        return jsonify({'success': False, 'message': '配置不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    try:
        simple_fields = ['name', 'provider', 'api_base', 'model_name', 'is_default',
                         'is_active', 'max_tokens', 'temperature', 'system_prompt', 'description']
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
@admin_required
def delete_config(config_id):
    config = AiConfig.query.get(config_id)
    if not config:
        return jsonify({'success': False, 'message': '配置不存在'}), 404
    db.session.delete(config)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@ai_bp.route('/configs/<int:config_id>/test', methods=['POST'])
@admin_required
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
    chats = AiChat.query.filter_by(user_id=current_user.id, is_archived=False)\
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


@ai_bp.route('/chats/<int:chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    current_user = get_current_user()
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    AiChatMessage.query.filter_by(chat_id=chat_id).delete()
    db.session.delete(chat)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


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
    allowed_ext = {'xlsx', 'xls', 'csv'}
    if ext not in allowed_ext:
        return jsonify({'success': False, 'message': f'仅支持 {", ".join(allowed_ext)} 格式的文件'}), 400

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
                'row_count': info.get('row_count', 0),
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
    chat = AiChat.query.filter_by(id=chat_id, user_id=current_user.id).first()
    if not chat:
        return jsonify({'success': False, 'message': '对话不存在'}), 404

    messages = AiChatMessage.query.filter_by(chat_id=chat_id)\
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

    # Get AI config
    ai_config = AiConfig.query.filter_by(is_default=True, is_active=True).first()
    if not ai_config:
        ai_config = AiConfig.query.filter_by(is_active=True).first()

    if not ai_config:
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
        from app.services.ai_service import AiService
        context = AiService.build_chat_context(current_user.id, chat_id)

        # Get chat history
        history = AiChatMessage.query.filter_by(chat_id=chat_id)\
            .order_by(AiChatMessage.created_at.asc()).all()
        messages = []
        if ai_config.system_prompt:
            messages.append({'role': 'system', 'content': ai_config.system_prompt})
        else:
            sys_prompt = context + '\n\n## 重要规则\n' \
                '- 当用户表达需要导出数据的意图时，调用 request_export 工具\n' \
                '- 当用户表达需要查询数据的意图时，调用 request_query 工具\n' \
                '- 如果用户没有指定具体的导出选项名称，先调用 list_export_options 列出相关选项让用户选择\n' \
                '- 如果用户提供了参数值，务必在调用工具时传入正确的参数\n' \
                '- 如果缺少必填参数，在回复中向用户询问\n' \
                '- 当用户上传文件时，消息中会包含文件信息（行数和列名），根据列名自动匹配最合适的查询或导出选项\n'
            messages.append({'role': 'system', 'content': sys_prompt})

        for msg in history:
            messages.append({'role': msg.role, 'content': msg.content})

        # Call AI with function calling
        ai_response = AiService.chat_with_tools(ai_config, messages)
        response_text = ai_response['content']
        tool_calls = ai_response['tool_calls']
        tokens = ai_response['tokens']

        # If AI wants to call tools, execute them
        tool_results = []
        if tool_calls:
            for tc in tool_calls:
                func_name = tc.get('function', {}).get('name', '')
                func_args = tc.get('function', {}).get('arguments', '')
                logger.info(f'AI调用工具: {func_name}({func_args})')
                result = AiService.execute_tool_call(func_name, func_args, current_user.id)
                tool_results.append({
                    'tool_call_id': tc['id'],
                    'name': func_name,
                    'result': result,
                })

            # Build tool result messages for AI to generate final response
            tool_messages = []
            for tr in tool_results:
                tool_messages.append({
                    'role': 'tool',
                    'tool_call_id': tr['tool_call_id'],
                    'content': json.dumps(tr['result'], ensure_ascii=False),
                })

            # Ask AI to generate final response with tool results
            messages.append({
                'role': 'assistant',
                'content': response_text,
                'tool_calls': tool_calls,
            })
            messages.extend(tool_messages)

            # 检查工具类型：如果是操作型工具（导出/查询），跳过AI二次确认，直接返回结果给前端显示卡片
            action_tools = {'request_export', 'request_query'}
            has_action = any(tc.get('function', {}).get('name', '') in action_tools for tc in tool_calls)

            if has_action:
                # 直接返回，不请求AI二次回复
                response_text = ''
                tokens = tokens  # 保持原有 token 计数
            else:
                # 非操作型工具（如列出选项），请求AI生成回复
                final_payload = {
                    'model': ai_config.model_name or 'gpt-3.5-turbo',
                    'messages': messages,
                    'max_tokens': ai_config.max_tokens or 4096,
                    'temperature': ai_config.temperature if ai_config.temperature is not None else 0.7,
                }
                api_key = ai_config.get_api_key()
                api_base = ai_config.api_base or 'https://api.openai.com/v1'
                url = f"{api_base.rstrip('/')}/chat/completions"
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                }
                import requests
                response = requests.post(url, headers=headers, json=final_payload, timeout=120)
                response.raise_for_status()
                result2 = response.json()
                response_text = result2['choices'][0].get('message', {}).get('content', '') if result2.get('choices') else ''
                tokens = result2.get('usage', {}).get('total_tokens', tokens)

        # Build response payload
        response_payload = {
            'assistant_message': None,
            'tool_results': None,
        }

        # Save assistant message (skip if empty content AND there are tool results)
        if response_text.strip() or not tool_results:
            assistant_message = AiChatMessage(
                chat_id=chat_id,
                role='assistant',
                content=response_text,
                tokens_used=tokens,
            )
            db.session.add(assistant_message)
            db.session.flush()
            response_payload['assistant_message'] = assistant_message.to_dict()

        # If there are tool results, save each as a message and return IDs
        if tool_results:
            saved_tool_messages = []
            for tr in tool_results:
                result = tr['result']
                if result and not result.get('error') and result.get('action_type') in ('export', 'query'):
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
                else:
                    saved_tool_messages.append(tr)
            response_payload['tool_results'] = saved_tool_messages

        db.session.commit()

        # Track behavior
        from app.utils.behavior_tracker import track_behavior as _track
        _track(current_user.id, 'chat', 'ai_chat', chat_id, {'tokens': tokens})

        return jsonify({'success': True, 'data': response_payload})
    except Exception as e:
        logger.error(f'AI对话失败: {e}', exc_info=True)
        assistant_message = AiChatMessage(
            chat_id=chat_id,
            role='assistant',
            content=f'AI服务调用失败: {str(e)}',
        )
        db.session.add(assistant_message)
        db.session.commit()
        return jsonify({'success': True, 'data': {
            'user_message': user_message.to_dict(),
            'assistant_message': assistant_message.to_dict(),
        }})


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
