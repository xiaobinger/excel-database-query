"""开放API对外端点

- POST /v1/chat/completions  OpenAI兼容接口（支持 stream）
- GET  /v1/models            OpenAI兼容模型列表
- POST /api/v1/chat          自定义简洁接口（支持 stream）

认证: Authorization: Bearer sk-xxx（或 X-Api-Key），IP白名单校验。
全局设置控制总开关与暴露的端点模式（openai/custom/both）。
"""
import json
import time
import uuid

from flask import Blueprint, request, jsonify, Response

from app.services.open_api_service import (
    authenticate, get_client_ip, get_settings, chat_once, stream_chat,
    list_available_models,
)

openai_bp = Blueprint('openai_api', __name__, url_prefix='/v1')
custom_bp = Blueprint('custom_api', __name__, url_prefix='/api/v1')

SSE_HEADERS = {
    'Cache-Control': 'no-cache',
    'X-Accel-Buffering': 'no',
    'Connection': 'keep-alive',
}


def _parse_auth_token():
    """从 Authorization: Bearer xxx 或 X-Api-Key 头解析密钥"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return request.headers.get('X-Api-Key', '').strip()


def _parse_session_id(data):
    """提取调用方显式传入的会话ID：body 的 session_id 优先，其次 X-Session-Id 头。

    便于调用方（外部agent等）将多次调用归属到同一业务会话；
    未传时由服务端按首条user消息自动派生。返回 '' 表示未显式指定。
    """
    from app.services.open_api_service import sanitize_session_id
    raw = (data or {}).get('session_id') if isinstance(data, dict) else None
    if raw in (None, ''):
        raw = request.headers.get('X-Session-Id', '')
    return sanitize_session_id(raw)


def _authenticate_request():
    """认证请求，返回 (api_key, 错误响应, caller_ip)"""
    ip = get_client_ip()
    api_key, err = authenticate(_parse_auth_token(), ip)
    if err:
        return None, err, ip
    return api_key, None, ip


def _openai_error(message, status, err_type='invalid_request_error'):
    return jsonify({'error': {'message': message, 'type': err_type, 'code': status}}), status


def _validate_messages(messages):
    """校验messages格式，返回 (规范化的messages, 错误)"""
    if not isinstance(messages, list) or not messages:
        return None, 'messages 必须是非空数组'
    normalized = []
    for m in messages:
        if not isinstance(m, dict):
            return None, 'messages 中每项必须是对象'
        role = m.get('role', '')
        if role not in ('system', 'user', 'assistant', 'tool'):
            return None, f'不支持的角色: {role}'
        content = m.get('content', '')
        msg = {'role': role}
        if isinstance(content, str):
            msg['content'] = content
        elif isinstance(content, list):
            # 兼容多模态 content 数组，转纯文本
            msg['content'] = '\n'.join(str(p.get('text', '')) for p in content if isinstance(p, dict))
        elif content is None and role == 'assistant' and m.get('tool_calls'):
            # assistant 发起工具调用时 content 允许为空，保留 None
            msg['content'] = None
        else:
            msg['content'] = str(content)
        # 保留工具调用相关字段：外部agent传入 tool 消息时上游API要求必须带 tool_call_id
        if role == 'tool' and m.get('tool_call_id'):
            msg['tool_call_id'] = str(m['tool_call_id'])
        if role == 'assistant' and isinstance(m.get('tool_calls'), list):
            msg['tool_calls'] = m['tool_calls']
        if m.get('name'):
            msg['name'] = str(m['name'])[:100]
        normalized.append(msg)
    return normalized, None


# ============ OpenAI 兼容端点 ============

def _validate_request_extras(data):
    """提取并校验可选透传参数（tools/tool_choice/parallel_tool_calls/max_tokens/temperature）。
    外部agent依赖tools驱动工具调用，必须原样透传给上游。返回 (extras, err)"""
    extras = {}
    tools = data.get('tools')
    if tools is not None:
        if not isinstance(tools, list):
            return None, 'tools 必须是数组'
        if tools:  # 空数组视为无工具，忽略
            for t in tools:
                if not isinstance(t, dict) or t.get('type') != 'function' or not isinstance(t.get('function'), dict):
                    return None, 'tools 中每项必须是 {type: "function", function: {...}} 格式'
                if not t['function'].get('name'):
                    return None, '工具函数缺少 name'
            extras['tools'] = tools
    tool_choice = data.get('tool_choice')
    if tool_choice is not None:
        valid = tool_choice in ('auto', 'none', 'required') or (
            isinstance(tool_choice, dict) and tool_choice.get('type') == 'function'
        )
        if not valid:
            return None, 'tool_choice 必须是 auto/none/required 或 {type: "function", function: {...}}'
        extras['tool_choice'] = tool_choice
    if isinstance(data.get('max_tokens'), int) and data['max_tokens'] > 0:
        extras['max_tokens'] = data['max_tokens']
    if isinstance(data.get('temperature'), (int, float)):
        extras['temperature'] = data['temperature']
    if isinstance(data.get('parallel_tool_calls'), bool):
        extras['parallel_tool_calls'] = data['parallel_tool_calls']
    return extras, None


@openai_bp.route('/chat/completions', methods=['POST'])
def openai_chat_completions():
    settings = get_settings()
    if not settings['enabled']:
        return _openai_error('开放API未启用', 404, 'not_found')
    if settings['endpoint_mode'] not in ('openai', 'both'):
        return _openai_error('OpenAI兼容端点未开放', 404, 'not_found')

    api_key, err, ip = _authenticate_request()
    if err:
        status = 403 if '白名单' in err or '禁用' in err else 401
        return _openai_error(err, status, 'authentication_error')

    data = request.get_json(silent=True) or {}
    messages, msg_err = _validate_messages(data.get('messages'))
    if msg_err:
        return _openai_error(msg_err, 400)
    extras, extras_err = _validate_request_extras(data)
    if extras_err:
        return _openai_error(extras_err, 400)
    model_name = data.get('model') or 'auto'
    stream = bool(data.get('stream'))
    session_id = _parse_session_id(data)

    if stream:
        return _openai_stream_response(api_key, model_name, messages, ip, extras, session_id=session_id)
    return _openai_plain_response(api_key, model_name, messages, ip, extras, session_id=session_id)


def _openai_plain_response(api_key, model_name, messages, ip, extras=None, session_id=None):
    result = chat_once(api_key, 'openai', model_name, messages, ip, extras=extras, session_id=session_id)
    if not result.get('success'):
        return _openai_error(result.get('error', '调用失败'), 502, 'api_error')
    message = {'role': 'assistant', 'content': result.get('content') or ''}
    finish_reason = 'stop'
    if result.get('tool_calls'):
        # 工具调用透传：外部agent依赖tool_calls驱动执行
        message['tool_calls'] = result['tool_calls']
        finish_reason = 'tool_calls'
    return jsonify({
        'id': f'chatcmpl-{uuid.uuid4().hex[:24]}',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': result.get('model', ''),
        'choices': [{
            'index': 0,
            'message': message,
            'finish_reason': finish_reason,
        }],
        'usage': result.get('usage', {}),
        'system_fingerprint': 'excel-query-openapi',
    })


def _openai_stream_response(api_key, model_name, messages, ip, extras=None, session_id=None):
    completion_id = f'chatcmpl-{uuid.uuid4().hex[:24]}'
    created = int(time.time())
    # 生成器在响应头发出后才执行（请求上下文已弹出），需先在请求阶段取出 app
    from flask import current_app
    app = current_app._get_current_object()

    def generate():
        model_name_out = model_name
        for event, done, meta in stream_chat(api_key, 'openai', model_name, messages, ip, app=app, extras=extras, session_id=session_id):
            if done:
                if meta and meta.get('error'):
                    # 流已开始后出错：以OpenAI格式输出错误信息后结束
                    yield 'data: ' + json.dumps({
                        'id': completion_id, 'object': 'chat.completion.chunk',
                        'created': created, 'model': model_name_out,
                        'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                        'error': {'message': meta['error']},
                    }, ensure_ascii=False) + '\n\n'
                else:
                    model_name_out = (meta or {}).get('model', model_name_out)
                    yield 'data: ' + json.dumps({
                        'id': completion_id, 'object': 'chat.completion.chunk',
                        'created': created, 'model': model_name_out,
                        'choices': [{'index': 0, 'delta': {}, 'finish_reason': (meta or {}).get('finish_reason') or 'stop'}],
                    }, ensure_ascii=False) + '\n\n'
                    if meta and meta.get('usage'):
                        yield 'data: ' + json.dumps({
                            'id': completion_id, 'object': 'chat.completion.chunk',
                            'created': created, 'model': model_name_out,
                            'choices': [],
                            'usage': meta['usage'],
                        }, ensure_ascii=False) + '\n\n'
                yield 'data: [DONE]\n\n'
            elif event:
                if event['type'] == 'tool_calls':
                    # 工具调用增量片段原样透传，调用方SDK自行拼接
                    yield 'data: ' + json.dumps({
                        'id': completion_id, 'object': 'chat.completion.chunk',
                        'created': created, 'model': model_name_out,
                        'choices': [{'index': 0, 'delta': {'tool_calls': event['tool_calls']}}],
                    }, ensure_ascii=False) + '\n\n'
                elif event.get('text'):
                    yield 'data: ' + json.dumps({
                        'id': completion_id, 'object': 'chat.completion.chunk',
                        'created': created, 'model': model_name_out,
                        'choices': [{'index': 0, 'delta': {'content': event['text']}}],
                    }, ensure_ascii=False) + '\n\n'

    return Response(generate(), mimetype='text/event-stream', headers=SSE_HEADERS)


@openai_bp.route('/models', methods=['GET'])
def openai_list_models():
    settings = get_settings()
    if not settings['enabled'] or settings['endpoint_mode'] not in ('openai', 'both'):
        return _openai_error('OpenAI兼容端点未开放', 404, 'not_found')
    api_key, err, ip = _authenticate_request()
    if err:
        status = 403 if '白名单' in err or '禁用' in err else 401
        return _openai_error(err, status, 'authentication_error')
    models = list_available_models(api_key)
    return jsonify({
        'object': 'list',
        'data': [{'id': m, 'object': 'model', 'owned_by': 'excel-query-openapi'} for m in models],
    })


# ============ 自定义端点 ============

@custom_bp.route('/chat', methods=['POST'])
def custom_chat():
    settings = get_settings()
    if not settings['enabled']:
        return jsonify({'success': False, 'message': '开放API未启用'}), 404
    if settings['endpoint_mode'] not in ('custom', 'both'):
        return jsonify({'success': False, 'message': '自定义端点未开放'}), 404

    api_key, err, ip = _authenticate_request()
    if err:
        status = 403 if '白名单' in err or '禁用' in err else 401
        return jsonify({'success': False, 'message': err}), status

    data = request.get_json(silent=True) or {}
    messages, msg_err = _validate_messages(data.get('messages'))
    if msg_err:
        return jsonify({'success': False, 'message': msg_err}), 400
    extras, extras_err = _validate_request_extras(data)
    if extras_err:
        return jsonify({'success': False, 'message': extras_err}), 400
    model_name = data.get('model') or 'auto'
    stream = bool(data.get('stream'))
    session_id = _parse_session_id(data)

    if stream:
        # 生成器在响应头发出后才执行（请求上下文已弹出），需先在请求阶段取出 app
        from flask import current_app
        app = current_app._get_current_object()

        def generate():
            for event, done, meta in stream_chat(api_key, 'custom', model_name, messages, ip, app=app, extras=extras, session_id=session_id):
                if done:
                    if meta and meta.get('error'):
                        yield 'data: ' + json.dumps({'type': 'error', 'message': meta['error']}, ensure_ascii=False) + '\n\n'
                    else:
                        yield 'data: ' + json.dumps({'type': 'done', **(meta or {})}, ensure_ascii=False) + '\n\n'
                elif event:
                    if event['type'] == 'tool_calls':
                        # 工具调用增量片段原样透传，调用方SDK自行拼接
                        yield 'data: ' + json.dumps({'type': 'tool_calls', 'tool_calls': event['tool_calls']}, ensure_ascii=False) + '\n\n'
                    elif event.get('text'):
                        yield 'data: ' + json.dumps({'type': 'content', 'content': event['text']}, ensure_ascii=False) + '\n\n'

        return Response(generate(), mimetype='text/event-stream', headers=SSE_HEADERS)

    result = chat_once(api_key, 'custom', model_name, messages, ip, extras=extras, session_id=session_id)
    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('error', '调用失败')}), 502
    data_out = {
        'content': result.get('content', ''),
        'model': result.get('model', ''),
        'usage': result.get('usage', {}),
        'elapsed': result.get('elapsed', 0),
    }
    if result.get('tool_calls'):
        # 工具调用透传：外部agent依赖tool_calls驱动执行
        data_out['tool_calls'] = result['tool_calls']
        data_out['finish_reason'] = 'tool_calls'
    return jsonify({'success': True, 'data': data_out})
