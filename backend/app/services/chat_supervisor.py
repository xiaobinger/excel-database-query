# -*- coding: utf-8 -*-
"""对话级AI监督者复核服务（hybrid模式：AI监督自动复核 + 人工兜底标记）

在AI完成一轮回复后，由监督者Agent对回复质量进行复核：
- approved：回复质量合格
- retry：回复存在明显问题，携带反馈要求主Agent重新生成
- flag_human：涉及高风险事项或无法判断对错，标记消息供人工复核

监督者Agent复用现有 AiAgent（agent_role='supervisor'）体系，
最大复核轮次读取其 max_supervisor_rounds 配置。
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

# 监督者复核提示模板（用户消息部分）
REVIEW_TEMPLATE = (
    '## 复核任务\n'
    '你是AI对话质量的监督者。下面是一次AI对话的完整记录：用户问题、主Agent的回复、'
    '以及主Agent调用工具的执行结果。\n'
    '请对主Agent的回复进行严格复核，重点检查：\n'
    '1. 是否完整、准确地回答了用户的问题（有无遗漏、答非所问）\n'
    '2. 工具调用是否成功；若工具报错，回复是否如实告知用户并给出下一步建议\n'
    '3. 回复中引用的数据是否与工具执行结果一致（严禁编造数据）\n'
    '4. 是否遵守了系统规则（如需要用户确认的操作是否擅自执行等）\n\n'
    '请只输出一个JSON对象（不要输出任何其他内容），格式如下：\n'
    '{{"verdict": "approved|retry|flag_human", "feedback": "简要说明"}}\n'
    '- approved：回复质量合格\n'
    '- retry：回复存在明显问题，feedback中写明具体问题和改进要求（将触发主Agent重新生成）\n'
    '- flag_human：涉及金额/权限等高风险事项或无法判断对错，需要人工复核，feedback中写明风险点\n\n'
    '## 对话记录\n'
    '用户问题：\n{user_content}\n\n'
    '主Agent回复：\n{assistant_content}\n\n'
    '工具执行记录：\n{tool_summary}\n'
)

MAX_TOOL_CHARS = 600  # 单个工具结果最大字符数（防止复核请求过大）
MAX_TOOLS = 10        # 最多携带的工具执行记录条数


def resolve_supervisor_agent(main_agent_id=None):
    """解析对话级监督者Agent。

    优先级：默认监督者（is_default=True）→ 任一活跃监督者。
    主Agent本身是监督者时返回None（自己监督自己无意义）。
    """
    from app.models.ai_agent import AiAgent
    sup = AiAgent.query.filter_by(is_active=True, agent_role='supervisor', is_default=True).first()
    if not sup:
        sup = AiAgent.query.filter_by(is_active=True, agent_role='supervisor').first()
    if not sup or sup.id == main_agent_id:
        return None
    return sup


def _summarize_tools(tool_results: list) -> str:
    """把工具执行记录压缩成简要文本"""
    if not tool_results:
        return '（本次回复未调用工具）'
    lines = []
    for tr in tool_results[:MAX_TOOLS]:
        name = tr.get('name', '')
        result = tr.get('result', {})
        if isinstance(result, dict):
            result_str = json.dumps(result, ensure_ascii=False)
        else:
            result_str = str(result)
        if len(result_str) > MAX_TOOL_CHARS:
            result_str = result_str[:MAX_TOOL_CHARS] + '…（已截断）'
        lines.append(f'- 工具 {name}: {result_str}')
    return '\n'.join(lines)


def _parse_verdict(content: str) -> dict:
    """解析监督者输出的判定JSON，解析失败时按关键词兜底"""
    verdict = {'verdict': 'approved', 'feedback': '', 'raw': content or ''}
    if not content:
        return verdict
    # 提取第一个JSON对象
    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            parsed = json.loads(m.group(0))
            v = str(parsed.get('verdict', '')).strip().lower()
            if v in ('approved', 'retry', 'flag_human', 'flag'):
                verdict['verdict'] = 'flag_human' if v == 'flag' else v
            verdict['feedback'] = str(parsed.get('feedback', '') or '').strip()
            return verdict
        except (json.JSONDecodeError, TypeError):
            pass
    # 关键词兜底
    if any(k in content for k in ('retry', '重新生成', '不通过', '不合格')):
        verdict['verdict'] = 'retry'
        verdict['feedback'] = content.strip()
    elif any(k in content for k in ('人工', 'flag_human', '人工复核')):
        verdict['verdict'] = 'flag_human'
        verdict['feedback'] = content.strip()
    else:
        verdict['verdict'] = 'approved'
        verdict['feedback'] = ''
    return verdict


def review_response(supervisor_prompt: str, user_content: str, assistant_content: str,
                    tool_results: list, configs: list) -> dict:
    """调用监督者Agent复核一次回复。

    Args:
        supervisor_prompt: 监督者Agent的系统提示词
        user_content: 用户原始问题
        assistant_content: 主Agent的回复正文
        tool_results: 工具执行记录列表 [{'name', 'result'}, ...]
        configs: 模型配置快照列表（dict: api_key/api_base/provider/model_name/...），支持故障转移

    Returns:
        {'verdict': 'approved'|'retry'|'flag_human', 'feedback': str, 'raw': str}
    """
    from app.services.ai_service import post_chat_completions, _apply_cache_control

    tool_summary = _summarize_tools(tool_results)
    review_user = REVIEW_TEMPLATE.format(
        user_content=(user_content or '')[:4000],
        assistant_content=(assistant_content or '')[:6000],
        tool_summary=tool_summary,
    )
    messages = [
        {'role': 'system', 'content': supervisor_prompt or '你是AI对话质量的监督者。'},
        {'role': 'user', 'content': review_user},
    ]

    last_error = None
    for cfg in configs:
        try:
            api_base = cfg['api_base']
            url = f"{api_base.rstrip('/')}/chat/completions"
            headers = {
                'Authorization': f"Bearer {cfg['api_key']}",
                'Content-Type': 'application/json',
            }
            cached_messages = _apply_cache_control(messages, cfg['provider'], api_base)
            payload = {
                'model': cfg['model_name'],
                'messages': cached_messages,
                'max_tokens': 1024,
                'temperature': 0.2,
            }
            resp = post_chat_completions(url, headers, payload, timeout=90)
            resp.raise_for_status()
            result = resp.json()
            content = ''
            if result.get('choices') and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '') or ''
            logger.info(f'监督者复核完成: model={cfg["model_name"]}, content_len={len(content)}')
            return _parse_verdict(content)
        except Exception as e:
            last_error = e
            logger.warning(f'监督者复核模型调用失败({cfg.get("name")}): {e}，尝试下一个')
            continue
    raise ValueError(f'监督者复核所有模型调用失败: {last_error}')


def mark_message(msg_id: int, verdict: dict, supervisor_agent_id=None) -> bool:
    """在消息metadata上打监督复核标记（flag_human时供前端/人工查看）"""
    from app import db
    from app.models.ai_chat import AiChatMessage
    msg = AiChatMessage.query.get(msg_id)
    if not msg:
        return False
    try:
        meta = json.loads(msg.msg_metadata) if msg.msg_metadata else {}
        if not isinstance(meta, dict):
            meta = {}
    except (json.JSONDecodeError, TypeError):
        meta = {}
    meta['supervision'] = {
        'verdict': verdict.get('verdict', ''),
        'feedback': verdict.get('feedback', ''),
        'supervisor_agent_id': supervisor_agent_id,
    }
    msg.msg_metadata = json.dumps(meta, ensure_ascii=False)
    db.session.commit()
    return True


# ── 工具确认卡片监督者自动评估 ──


# 工具确认评估提示模板
TOOL_CONFIRM_TEMPLATE = (
    '## 工具执行安全评估任务\n'
    '你是AI对话的监督者，需要评估一个待确认的工具操作是否安全、合理。\n\n'
    '## 用户原始需求\n{user_content}\n\n'
    '## 待确认的工具操作\n'
    '- 工具类型：{action_type}\n'
    '- 工具名称：{tool_name}\n'
    '- 操作描述：{confirm_message}\n'
    '- 参数详情：{params_detail}\n\n'
    '## 评估要求\n'
    '请从以下维度评估该操作：\n'
    '1. **安全性**：操作是否可能造成数据丢失、资金损失等不可逆影响\n'
    '2. **合理性**：操作参数是否与用户需求匹配，有无明显错误\n'
    '3. **完整性**：必填参数是否齐全，参数值是否合理\n\n'
    '请只输出一个JSON对象（不要输出任何其他内容），格式如下：\n'
    '{{"approved": true/false, "feedback": "简要评估意见"}}\n'
    '- approved=true：操作安全合理，可以执行\n'
    '- approved=false：操作存在风险或参数有误，feedback中写明原因\n'
)


def evaluate_tool_action(supervisor_prompt: str, user_content: str, tool_result: dict,
                         tool_name: str, configs: list) -> dict:
    """监督者评估待确认的工具操作是否安全合理。

    Args:
        supervisor_prompt: 监督者Agent的系统提示词
        user_content: 用户原始问题
        tool_result: 工具返回的结果（含 action_type, confirm_message, params 等）
        tool_name: 工具名称（request_export/request_query/request_system_task等）
        configs: 模型配置快照列表，支持故障转移

    Returns:
        {'approved': bool, 'feedback': str, 'raw': str}
    """
    from app.services.ai_service import post_chat_completions, _apply_cache_control

    action_type = tool_result.get('action_type', 'unknown')
    confirm_message = tool_result.get('confirm_message', '')
    params = tool_result.get('params', tool_result.get('params_values', {}))
    if isinstance(params, list):
        # params 是参数配置列表，提取 params_values
        params = tool_result.get('params_values', {})
    params_detail = json.dumps(params, ensure_ascii=False, indent=2) if params else '（无参数）'

    # 限制参数详情长度
    if len(params_detail) > 2000:
        params_detail = params_detail[:2000] + '\n...（已截断）'

    review_user = TOOL_CONFIRM_TEMPLATE.format(
        user_content=(user_content or '')[:2000],
        action_type=action_type,
        tool_name=tool_name,
        confirm_message=confirm_message[:500],
        params_detail=params_detail,
    )
    messages = [
        {'role': 'system', 'content': supervisor_prompt or '你是AI对话的监督者，负责评估工具操作的安全性。'},
        {'role': 'user', 'content': review_user},
    ]

    default_result = {'approved': False, 'feedback': '监督者评估失败，默认需要人工确认', 'raw': ''}
    last_error = None
    for cfg in configs:
        try:
            api_base = cfg['api_base']
            url = f"{api_base.rstrip('/')}/chat/completions"
            headers = {
                'Authorization': f"Bearer {cfg['api_key']}",
                'Content-Type': 'application/json',
            }
            cached_messages = _apply_cache_control(messages, cfg['provider'], api_base)
            payload = {
                'model': cfg['model_name'],
                'messages': cached_messages,
                'max_tokens': 512,
                'temperature': 0.1,
            }
            resp = post_chat_completions(url, headers, payload, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            content = ''
            if result.get('choices') and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '') or ''
            logger.info(f'监督者工具评估完成: model={cfg["model_name"]}, action_type={action_type}, content_len={len(content)}')
            return _parse_tool_eval(content)
        except Exception as e:
            last_error = e
            logger.warning(f'监督者工具评估模型调用失败({cfg.get("name")}): {e}，尝试下一个')
            continue
    logger.error(f'监督者工具评估所有模型调用失败: {last_error}')
    return default_result


def _parse_tool_eval(content: str) -> dict:
    """解析监督者工具评估输出的JSON，解析失败时按关键词兜底"""
    result = {'approved': False, 'feedback': '', 'raw': content or ''}
    if not content:
        return result
    # 提取第一个JSON对象
    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            parsed = json.loads(m.group(0))
            result['approved'] = bool(parsed.get('approved', False))
            result['feedback'] = str(parsed.get('feedback', '') or '').strip()
            return result
        except (json.JSONDecodeError, TypeError):
            pass
    # 关键词兜底
    content_lower = content.lower()
    if any(k in content_lower for k in ('approved', '可以执行', '安全', '通过', '允许')):
        result['approved'] = True
        result['feedback'] = content.strip()
    elif any(k in content_lower for k in ('rejected', '拒绝', '风险', '不建议', '禁止', '危险')):
        result['approved'] = False
        result['feedback'] = content.strip()
    else:
        # 默认不通过，需人工确认
        result['approved'] = False
        result['feedback'] = content.strip()
    return result
