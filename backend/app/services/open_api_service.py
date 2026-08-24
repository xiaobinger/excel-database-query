"""开放API服务

- 认证: Bearer sk-xxx (ApiKey 哈希查询) + IP白名单（精确IP/CIDR）
- 模型解析: 外部名匹配 ApiKey.model_mapping → 指定模型；auto/未匹配 → 系统模型路由策略(含failover)
- 调用: 非流式/流式，每次调用写 ApiCallLog（内容/耗时/token/缓存token/实际模型/IP）
- 设置: SystemConfig 存储 open_api_enabled / open_api_endpoint_mode
"""
import hashlib
import ipaddress
import json
import logging
import time
import uuid
from datetime import datetime

import requests as req_lib
from flask import request

from app import db

logger = logging.getLogger(__name__)

# 全局设置键
OPEN_API_ENABLED_KEY = 'open_api_enabled'
OPEN_API_ENDPOINT_MODE_KEY = 'open_api_endpoint_mode'
VALID_ENDPOINT_MODES = ('openai', 'custom', 'both')


def _normalize_ip(raw) -> str:
    """规范化IP字符串：剥IPv4-mapped IPv6(::ffff:1.2.3.4→1.2.3.4)，非合法返回''"""
    if not raw:
        return ''
    s = str(raw).strip()
    if not s:
        return ''
    # 去掉端口：'1.2.3.4:5678' → '1.2.3.4'（处理Werkzeug/反代偶发带端口）
    if s.count(':') == 1 and s[0].isdigit():
        host, _, port = s.partition(':')
        if port.isdigit():
            s = host
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return ''
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return str(ip.ipv4_mapped)
    # 链路本地IPv6（fe80::/10）通常无业务意义，过滤；返回 '' 后由调用方回退到下一候选
    if isinstance(ip, ipaddress.IPv6Address) and (ip.is_link_local or ip.is_loopback):
        return ''
    if isinstance(ip, ipaddress.IPv4Address) and ip.is_loopback:
        return ''
    return str(ip)


def get_client_ip() -> str:
    """获取调用方真实IP（按可信度顺序取首个合法IP）：
    X-Forwarded-For（多级反代由调用方依次追加）> X-Real-IP > remote_addr。
    跳过链路本地/loopback等无业务意义的地址，支持 IPv4-mapped IPv6 转 IPv4。
    """
    candidates = []
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        candidates.extend(p.strip() for p in xff.split(',') if p.strip())
    xri = request.headers.get('X-Real-IP', '').strip()
    if xri:
        candidates.append(xri)
    if request.remote_addr:
        candidates.append(request.remote_addr)
    for c in candidates:
        ip = _normalize_ip(c)
        if ip:
            return ip
    return ''


def get_settings() -> dict:
    """读取开放API全局设置"""
    from app.models.system_config import SystemConfig
    enabled_cfg = SystemConfig.query.filter_by(config_key=OPEN_API_ENABLED_KEY).first()
    mode_cfg = SystemConfig.query.filter_by(config_key=OPEN_API_ENDPOINT_MODE_KEY).first()
    mode = mode_cfg.config_value if mode_cfg and mode_cfg.config_value in VALID_ENDPOINT_MODES else 'both'
    try:
        enabled = enabled_cfg and str(enabled_cfg.config_value).lower() in ('1', 'true', 'yes')
    except Exception:
        enabled = False
    return {'enabled': bool(enabled), 'endpoint_mode': mode}


def save_settings(enabled: bool, endpoint_mode: str) -> dict:
    """保存开放API全局设置"""
    if endpoint_mode not in VALID_ENDPOINT_MODES:
        raise ValueError(f'endpoint_mode 必须是 {"、".join(VALID_ENDPOINT_MODES)} 之一')
    from app.models.system_config import SystemConfig
    for key, value in ((OPEN_API_ENABLED_KEY, 'true' if enabled else 'false'),
                       (OPEN_API_ENDPOINT_MODE_KEY, endpoint_mode)):
        cfg = SystemConfig.query.filter_by(config_key=key).first()
        if cfg:
            cfg.config_value = value
        else:
            db.session.add(SystemConfig(config_key=key, description='开放API设置', config_value=value))
    db.session.commit()
    return get_settings()


def ip_allowed(api_key, ip: str) -> bool:
    """IP白名单校验：空白名单不限；条目支持精确IP与CIDR"""
    whitelist = api_key.get_ip_whitelist()
    if not whitelist:
        return True
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in whitelist:
        entry = str(entry).strip()
        if not entry:
            continue
        try:
            if '/' in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def authenticate(key_str: str, ip: str):
    """认证并校验，返回 (ApiKey, 错误信息)"""
    from app.models.api_key import ApiKey
    if not key_str:
        return None, '缺少API密钥'
    key_hash = hashlib.sha256(key_str.encode('utf-8')).hexdigest()
    api_key = ApiKey.query.filter_by(api_key_hash=key_hash).first()
    if not api_key:
        return None, 'API密钥无效'
    if not api_key.is_active:
        return None, 'API密钥已禁用'
    if not ip_allowed(api_key, ip):
        return None, f'IP {ip} 不在白名单内'
    return api_key, None


def resolve_model(api_key, model_name: str):
    """解析请求模型：返回 (AiConfig或None, 匹配的外部名)。None表示走系统路由策略(auto)"""
    from app.models.ai_config import AiConfig
    model_name = (model_name or '').strip()
    if model_name and model_name.lower() != 'auto':
        for m in api_key.get_model_mapping():
            if m.get('external') == model_name:
                try:
                    config = AiConfig.query.filter_by(id=int(m.get('config_id')), is_active=True).first()
                    if config:
                        return config, model_name
                except (TypeError, ValueError):
                    continue
        # 有名称但未匹配映射 → 走auto（不报错，保持灵活）
    return None, None


def _ordered_configs():
    from app.services.ai_service import AiService
    return AiService.get_ordered_configs(scope='open_api')


def _extract_usage(usage: dict):
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)
    cache_creation = usage.get('cache_creation_input_tokens', 0) or 0
    cache_read = usage.get('cache_read_input_tokens', 0) or 0
    details = usage.get('prompt_tokens_details', {})
    if isinstance(details, dict) and details.get('cached_tokens'):
        cache_read = details['cached_tokens']
    return prompt_tokens, completion_tokens, cache_creation, cache_read


def _truncate_bytes(text: str, max_bytes: int) -> str:
    """按字节安全截断字符串（避免从多字节UTF-8字符中间截断导致乱码）"""
    if not text:
        return text
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    # 按字节截断后回退到完整字符边界
    return encoded[:max_bytes].decode('utf-8', errors='ignore')


def _apply_extras(payload: dict, extras: dict):
    """将调用方透传的可选参数应用到上游payload（覆盖配置默认值）。
    外部agent依赖tools驱动工具调用，必须原样透传。"""
    extras = extras or {}
    if extras.get('max_tokens'):
        payload['max_tokens'] = extras['max_tokens']
    if extras.get('temperature') is not None:
        payload['temperature'] = extras['temperature']
    if extras.get('tools'):
        payload['tools'] = extras['tools']
    if 'tool_choice' in extras:
        payload['tool_choice'] = extras['tool_choice']
    if 'parallel_tool_calls' in extras:
        payload['parallel_tool_calls'] = extras['parallel_tool_calls']


def _merge_tool_calls(accum: dict, delta_list: list):
    """流式tool_calls增量片段按index聚合（首片带id/name，后续片只有arguments增量）"""
    for tc in delta_list:
        if not isinstance(tc, dict):
            continue
        idx = tc.get('index', 0)
        cur = accum.setdefault(idx, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
        if tc.get('id'):
            cur['id'] = tc['id']
        fn = tc.get('function') or {}
        if fn.get('name'):
            cur['function']['name'] = fn['name']
        if fn.get('arguments'):
            cur['function']['arguments'] += fn['arguments']


def _content_with_tool_calls(content: str, tool_calls) -> str:
    """调用记录用：content + tool_calls JSON（工具调用响应content常为空）"""
    if not tool_calls:
        return content or ''
    merged = json.dumps(tool_calls, ensure_ascii=False)
    if content:
        return f'{content}\n\n[tool_calls]\n{merged}'
    return f'[tool_calls]\n{merged}'


def sanitize_session_id(raw) -> str:
    """规范化调用方显式传入的会话ID：仅保留安全字符，超长截断，非法返回空串"""
    if raw is None:
        return ''
    s = str(raw).strip()
    if not s:
        return ''
    s = ''.join(c if (c.isalnum() or c in '-_.') else '-' for c in s)
    return s[:64]


def compute_session_id(api_key_id, messages) -> str:
    """自动派生会话ID（调用方未显式传sessionId时）。

    OpenAI兼容协议无会话概念，调用方通常每次携带完整上下文，
    因此以「密钥ID + 首条user消息内容」的哈希作为会话指纹：
    同一会话的多次调用首条user消息相同 → 聚合到同一会话。
    无user消息时按整体消息哈希兜底。
    """
    seed = None
    if isinstance(messages, list):
        for m in messages:
            if isinstance(m, dict) and m.get('role') == 'user':
                seed = f'{api_key_id}:{m.get("content") or ""}'
                break
        if seed is None:
            try:
                seed = f'{api_key_id}:{json.dumps(messages, ensure_ascii=False)[:4096]}'
            except (TypeError, ValueError):
                seed = f'{api_key_id}:'
    else:
        seed = f'{api_key_id}:'
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()[:32]


def _chat_single(cfg, messages: list, extras: dict = None):
    """单模型非流式调用（支持工具调用透传）。
    返回 (content, tool_calls, finish_reason, tokens, p, c, cc, cr)"""
    from app.services.ai_service import post_chat_completions, _apply_cache_control
    api_key_val = cfg.get_api_key()
    if not api_key_val:
        raise ValueError('API密钥未配置')
    api_base = cfg.api_base or 'https://api.openai.com/v1'
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {'Authorization': f'Bearer {api_key_val}', 'Content-Type': 'application/json'}
    base_messages = _apply_cache_control(messages, cfg.provider, api_base)
    payload = {
        'model': cfg.model_name or 'gpt-3.5-turbo',
        'messages': base_messages,
        'max_tokens': cfg.max_tokens or 4096,
        'temperature': cfg.temperature if cfg.temperature is not None else 0.7,
    }
    _apply_extras(payload, extras)
    r = post_chat_completions(url, headers, payload, timeout=120)
    r.raise_for_status()
    result = r.json()
    choice = (result.get('choices') or [{}])[0]
    message = choice.get('message') or {}
    content = message.get('content') or ''
    tool_calls = message.get('tool_calls') or []
    finish_reason = choice.get('finish_reason') or 'stop'
    usage = result.get('usage') or {}
    p_tokens, c_tokens, cc, cr = _extract_usage(usage)
    tokens = usage.get('total_tokens') or (p_tokens + c_tokens)
    return content, tool_calls, finish_reason, tokens, p_tokens, c_tokens, cc, cr


def _log_call(app, api_key, endpoint, model_requested, model_used, caller_ip,
              messages, response_content, tokens, p_tokens, c_tokens, cc, cr,
              elapsed, is_success, error_msg=None, session_id=None):
    """写调用记录（可在任意线程，自带 app context）。

    超长内容按字节安全截断；写入失败时降级（去掉内容重试）确保统计不丢。
    """
    with app.app_context():
        try:
            from app.models.api_call_log import ApiCallLog
            from app.models.api_key import ApiKey
            log = ApiCallLog(
                api_key_id=api_key.id,
                api_key_name=api_key.name,
                endpoint=endpoint,
                model_requested=model_requested,
                model_used=model_used,
                session_id=session_id or compute_session_id(api_key.id, messages),
                caller_ip=caller_ip,
                messages=_truncate_bytes(json.dumps(messages, ensure_ascii=False), 15 * 1024 * 1024) if messages else None,
                response_content=_truncate_bytes(response_content, 15 * 1024 * 1024) or None,
                tokens_used=tokens or 0,
                prompt_tokens=p_tokens or 0,
                completion_tokens=c_tokens or 0,
                cache_creation_tokens=cc or 0,
                cache_read_tokens=cr or 0,
                elapsed=round(elapsed, 2),
                is_success=is_success,
                error_msg=_truncate_bytes(error_msg, 2000) if error_msg else None,
            )
            db.session.add(log)
            # 更新最近使用时间
            key_obj = ApiKey.query.get(api_key.id)
            if key_obj:
                key_obj.last_used_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            logger.warning(f'写开放API调用记录失败: {e}')
            try:
                db.session.rollback()
                # 降级：去掉大内容字段重试，保证统计/审计记录不丢
                log = ApiCallLog(
                    api_key_id=api_key.id,
                    api_key_name=api_key.name,
                    endpoint=endpoint,
                    model_requested=model_requested,
                    model_used=model_used,
                    session_id=session_id or compute_session_id(api_key.id, messages),
                    caller_ip=caller_ip,
                    messages=None,
                    response_content=None,
                    tokens_used=tokens or 0,
                    prompt_tokens=p_tokens or 0,
                    completion_tokens=c_tokens or 0,
                    cache_creation_tokens=cc or 0,
                    cache_read_tokens=cr or 0,
                    elapsed=round(elapsed, 2),
                    is_success=is_success,
                    error_msg=_truncate_bytes(f'{error_msg or ""}|日志降级保存（内容过大）: {e}', 2000),
                )
                db.session.add(log)
                key_obj = ApiKey.query.get(api_key.id)
                if key_obj:
                    key_obj.last_used_at = datetime.utcnow()
                db.session.commit()
            except Exception as e2:
                logger.warning(f'开放API调用记录降级保存也失败: {e2}')
                try:
                    db.session.rollback()
                except Exception:
                    pass


def chat_once(api_key, endpoint, model_name, messages, caller_ip, extras=None, session_id=None):
    """非流式对话（支持工具调用透传）。
    返回 dict: {success, content, tool_calls, finish_reason, model, usage, elapsed} 或 {success, error}"""
    from flask import current_app
    app = current_app._get_current_object()
    start = time.time()
    model_requested = (model_name or 'auto').strip() or 'auto'
    config, matched = resolve_model(api_key, model_requested)
    session_id = sanitize_session_id(session_id) or None

    content = ''
    tool_calls = []
    finish_reason = 'stop'
    model_used = ''
    tokens = p_tokens = c_tokens = cc = cr = 0
    error = None

    try:
        if config:
            configs = [config]
        else:
            configs = _ordered_configs()
            if not configs:
                raise ValueError('没有可用的AI模型配置')

        last_err = None
        for cfg in configs:
            try:
                content, tool_calls, finish_reason, tokens, p_tokens, c_tokens, cc, cr = \
                    _chat_single(cfg, messages, extras)
                model_used = cfg.model_name or ''
                last_err = None
                break
            except Exception as e:
                last_err = e
                logger.warning(f'开放API模型 {cfg.name} 调用失败: {e}')
                if config:
                    break  # 指定模型不failover
                continue
        if last_err is not None and not content and not tool_calls:
            raise last_err

        elapsed = time.time() - start
        _log_call(app, api_key, endpoint, model_requested, model_used, caller_ip,
                  messages, _content_with_tool_calls(content, tool_calls),
                  tokens, p_tokens, c_tokens, cc, cr, elapsed, True, session_id=session_id)
        return {
            'success': True,
            'content': content,
            'tool_calls': tool_calls,
            'finish_reason': finish_reason,
            'model': model_used,
            'usage': {
                'prompt_tokens': p_tokens,
                'completion_tokens': c_tokens,
                'total_tokens': tokens,
                'cache_creation_tokens': cc,
                'cache_read_tokens': cr,
            },
            'elapsed': round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.time() - start
        _log_call(app, api_key, endpoint, model_requested, model_used, caller_ip,
                  messages, '', 0, 0, 0, 0, 0, elapsed, False, str(e), session_id=session_id)
        return {'success': False, 'error': str(e)}


def stream_chat(api_key, endpoint, model_name, messages, caller_ip, app=None, extras=None, session_id=None):
    """流式对话生成器（支持工具调用透传）：逐段 yield (event, done, meta)。

    event 为 None（结束帧）或 dict：
      - {'type': 'content', 'text': str}                  文本增量
      - {'type': 'tool_calls', 'tool_calls': [...]}        工具调用增量片段（原样透传，调用方SDK自行拼接）
    上游为 OpenAI 兼容 SSE；在收到首个内容chunk之前允许failover换模型，
    开始输出后不再切换。结束时写调用记录。
    注意：生成器在响应头发出后才执行（此时请求上下文已弹出），
    因此 app 必须由调用方在请求阶段通过 current_app._get_current_object() 取出后传入。
    """
    from flask import current_app
    if app is None:
        app = current_app._get_current_object()
    # 生成器在响应头发出后才执行（请求上下文已弹出），而主体内含 DB 查询、
    # 加密解密等需要 app context 的操作，因此整个主体包在 app context 中执行
    with app.app_context():
        start = time.time()
        model_requested = (model_name or 'auto').strip() or 'auto'
        config, matched = resolve_model(api_key, model_requested)
        session_id = sanitize_session_id(session_id) or None

        full_content = []
        tool_calls_accum = {}  # 流式tool_calls按index聚合（存调用记录用）
        tokens = p_tokens = c_tokens_out = cc = cr = 0
        model_used = ''
        resp = None
        finish_reason = 'stop'

        try:
            if config:
                configs = [config]
            else:
                configs = _ordered_configs()
                if not configs:
                    raise ValueError('没有可用的AI模型配置')

            from app.services.ai_service import post_chat_completions, _apply_cache_control

            last_err = None
            for idx, cfg in enumerate(configs):
                try:
                    api_key_val = cfg.get_api_key()
                    if not api_key_val:
                        raise ValueError('API密钥未配置')
                    api_base = cfg.api_base or 'https://api.openai.com/v1'
                    url = f"{api_base.rstrip('/')}/chat/completions"
                    headers = {'Authorization': f'Bearer {api_key_val}', 'Content-Type': 'application/json'}
                    base_messages = _apply_cache_control(messages, cfg.provider, api_base)
                    payload = {
                        'model': cfg.model_name or 'gpt-3.5-turbo',
                        'messages': base_messages,
                        'max_tokens': cfg.max_tokens or 4096,
                        'temperature': cfg.temperature if cfg.temperature is not None else 0.7,
                        'stream': True,
                        'stream_options': {'include_usage': True},
                    }
                    # 调用方透传参数（tools/tool_choice等）覆盖配置默认值
                    _apply_extras(payload, extras)
                    r = post_chat_completions(url, headers, payload, timeout=120, stream=True)
                    if r.status_code == 400 and 'stream_options' in (r.text or ''):
                        # 旧API不支持stream_options，去掉后重试
                        r.close()
                        payload.pop('stream_options', None)
                        r = post_chat_completions(url, headers, payload, timeout=120, stream=True)
                    r.raise_for_status()
                    # 确保使用UTF-8解码，避免中文乱码（部分API不返回charset头时requests默认按latin-1解码）
                    r.encoding = 'utf-8'
                    # 首个chunk前校验可用性：读取第一个data行。
                    # 注意：必须保存迭代器复用——requests 的 iter_lines 每次调用返回
                    # 新迭代器并重新缓冲底层流，重复调用会丢失已缓冲的数据
                    line_iter = r.iter_lines(decode_unicode=True)
                    first = None
                    for line in line_iter:
                        if line and line.startswith('data:'):
                            first = line[5:].strip()
                            break
                    if first is None:
                        raise ValueError('上游未返回流式数据')
                    if first != '[DONE]':
                        try:
                            chunk = json.loads(first)
                            if chunk.get('error'):
                                raise ValueError(str(chunk['error']))
                        except json.JSONDecodeError:
                            pass
                    resp = r
                    resp._line_iter = line_iter
                    resp._first_line = first
                    model_used = cfg.model_name or ''
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f'开放API流式模型 {getattr(cfg, "name", "?")} 建立失败: {e}')
                    if config:
                        break  # 指定模型不failover
                    continue

            if resp is None:
                raise last_err or RuntimeError('流式连接建立失败')

            # 输出首个chunk的内容（已在建连时读出）
            if resp._first_line and resp._first_line != '[DONE]':
                try:
                    chunk = json.loads(resp._first_line)
                    choices = chunk.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta', {}) or {}
                        text = delta.get('content') or ''
                        if text:
                            full_content.append(text)
                            yield {'type': 'content', 'text': text}, False, None
                        tc_delta = delta.get('tool_calls')
                        if tc_delta:
                            _merge_tool_calls(tool_calls_accum, tc_delta)
                            yield {'type': 'tool_calls', 'tool_calls': tc_delta}, False, None
                        if choices[0].get('finish_reason'):
                            finish_reason = choices[0]['finish_reason']
                    usage = chunk.get('usage')
                    if usage:
                        p_tokens, c_tokens_out, cc, cr = _extract_usage(usage)
                        tokens = usage.get('total_tokens', 0)
                except json.JSONDecodeError:
                    pass

            # 继续读取后续chunk（复用建连时保存的迭代器，避免丢失已缓冲数据）
            for line in resp._line_iter:
                if not line or not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                usage = chunk.get('usage')
                if usage:
                    p_tokens, c_tokens_out, cc, cr = _extract_usage(usage)
                    tokens = usage.get('total_tokens', 0)
                choices = chunk.get('choices') or []
                if not choices:
                    continue
                delta = choices[0].get('delta', {}) or {}
                text = delta.get('content') or ''
                if text:
                    full_content.append(text)
                    yield {'type': 'content', 'text': text}, False, None
                tc_delta = delta.get('tool_calls')
                if tc_delta:
                    # 工具调用增量片段：透传给调用方，同时聚合存调用记录
                    _merge_tool_calls(tool_calls_accum, tc_delta)
                    yield {'type': 'tool_calls', 'tool_calls': tc_delta}, False, None
                if choices[0].get('finish_reason'):
                    finish_reason = choices[0]['finish_reason']
            try:
                resp.close()
            except Exception:
                pass

            elapsed = time.time() - start
            content = ''.join(full_content)
            tool_calls = [tool_calls_accum[k] for k in sorted(tool_calls_accum)]
            _log_call(app, api_key, endpoint, model_requested, model_used, caller_ip,
                      messages, _content_with_tool_calls(content, tool_calls),
                      tokens, p_tokens, c_tokens_out, cc, cr, elapsed, True, session_id=session_id)
            yield '', True, {
                'model': model_used,
                'finish_reason': finish_reason,
                'tool_calls': tool_calls,
                'usage': {
                    'prompt_tokens': p_tokens,
                    'completion_tokens': c_tokens_out,
                    'total_tokens': tokens,
                    'cache_creation_tokens': cc,
                    'cache_read_tokens': cr,
                },
                'elapsed': round(elapsed, 2),
            }
        except Exception as e:
            error = str(e)
            elapsed = time.time() - start
            _log_call(app, api_key, endpoint, model_requested, model_used, caller_ip,
                      messages, _content_with_tool_calls(''.join(full_content),
                      [tool_calls_accum[k] for k in sorted(tool_calls_accum)]),
                      tokens, p_tokens, c_tokens_out, cc, cr, elapsed, False, error, session_id=session_id)
            yield '', True, {'error': error}


def list_available_models(api_key) -> list:
    """列出该key可用的外部模型名（映射 + auto + 路由策略模型）"""
    from app.models.ai_config import AiConfig
    models = []
    for m in api_key.get_model_mapping():
        if m.get('external'):
            models.append(str(m['external']))
    if 'auto' not in models:
        models.append('auto')
    return models
