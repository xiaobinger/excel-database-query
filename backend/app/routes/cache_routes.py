"""AI缓存管理路由"""
from flask import jsonify, request
from app.routes.ai_routes import ai_bp
from app.utils.auth import admin_required, get_current_user
from app import db
from app.models.ai_chat import AiChatMessage
from app.models.ai_agent import AiAgent
from sqlalchemy import func, desc
from datetime import datetime, timedelta


@ai_bp.route('/cache/stats', methods=['GET'])
@admin_required
def get_cache_stats():
    """获取缓存统计信息"""
    current_user = get_current_user()

    # 总体统计
    total_stats = db.session.query(
        func.sum(AiChatMessage.prompt_tokens).label('total_prompt_tokens'),
        func.sum(AiChatMessage.completion_tokens).label('total_completion_tokens'),
        func.sum(AiChatMessage.cache_creation_tokens).label('total_cache_creation_tokens'),
        func.sum(AiChatMessage.cache_read_tokens).label('total_cache_read_tokens'),
        func.count(AiChatMessage.id).label('total_messages'),
    ).filter(AiChatMessage.role == 'assistant').first()

    # 按Agent分组统计
    agent_stats = db.session.query(
        AiChatMessage.agent_id,
        AiAgent.name.label('agent_name'),
        func.sum(AiChatMessage.prompt_tokens).label('prompt_tokens'),
        func.sum(AiChatMessage.completion_tokens).label('completion_tokens'),
        func.sum(AiChatMessage.cache_creation_tokens).label('cache_creation_tokens'),
        func.sum(AiChatMessage.cache_read_tokens).label('cache_read_tokens'),
        func.count(AiChatMessage.id).label('message_count'),
    ).outerjoin(
        AiAgent, AiChatMessage.agent_id == AiAgent.id
    ).filter(
        AiChatMessage.role == 'assistant'
    ).group_by(
        AiChatMessage.agent_id, AiAgent.name
    ).all()

    # 按日期统计最近30天
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_stats = db.session.query(
        func.date(AiChatMessage.created_at).label('date'),
        func.sum(AiChatMessage.prompt_tokens).label('prompt_tokens'),
        func.sum(AiChatMessage.completion_tokens).label('completion_tokens'),
        func.sum(AiChatMessage.cache_creation_tokens).label('cache_creation_tokens'),
        func.sum(AiChatMessage.cache_read_tokens).label('cache_read_tokens'),
        func.count(AiChatMessage.id).label('message_count'),
    ).filter(
        AiChatMessage.role == 'assistant',
        AiChatMessage.created_at >= thirty_days_ago,
    ).group_by(
        func.date(AiChatMessage.created_at)
    ).order_by(
        func.date(AiChatMessage.created_at)
    ).all()

    # 计算缓存命中率
    total_prompt = total_stats.total_prompt_tokens or 0
    total_cache_read = total_stats.total_cache_read_tokens or 0
    cache_hit_rate = round(total_cache_read / total_prompt * 100, 2) if total_prompt > 0 else 0

    # 计算节省的token费用（缓存读取token价格通常是正常输入的50%或更低）
    # 这里只做统计展示，实际费用取决于各API提供商的定价
    total_cache_creation = total_stats.total_cache_creation_tokens or 0

    return jsonify({
        'success': True,
        'data': {
            'overview': {
                'total_prompt_tokens': total_prompt,
                'total_completion_tokens': total_stats.total_completion_tokens or 0,
                'total_cache_creation_tokens': total_cache_creation,
                'total_cache_read_tokens': total_cache_read,
                'total_messages': total_stats.total_messages or 0,
                'cache_hit_rate': cache_hit_rate,
            },
            'by_agent': [{
                'agent_id': s.agent_id,
                'agent_name': s.agent_name or '默认Agent',
                'prompt_tokens': s.prompt_tokens or 0,
                'completion_tokens': s.completion_tokens or 0,
                'cache_creation_tokens': s.cache_creation_tokens or 0,
                'cache_read_tokens': s.cache_read_tokens or 0,
                'message_count': s.message_count or 0,
            } for s in agent_stats],
            'daily': [{
                'date': str(s.date),
                'prompt_tokens': s.prompt_tokens or 0,
                'completion_tokens': s.completion_tokens or 0,
                'cache_creation_tokens': s.cache_creation_tokens or 0,
                'cache_read_tokens': s.cache_read_tokens or 0,
                'message_count': s.message_count or 0,
            } for s in daily_stats],
        }
    })


@ai_bp.route('/cache/agent/<int:agent_id>', methods=['GET'])
@admin_required
def get_agent_cache_stats(agent_id):
    """获取指定Agent的缓存统计详情"""

    agent = AiAgent.query.get(agent_id)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent不存在'}), 404

    # 该Agent的缓存统计
    stats = db.session.query(
        func.sum(AiChatMessage.prompt_tokens).label('prompt_tokens'),
        func.sum(AiChatMessage.completion_tokens).label('completion_tokens'),
        func.sum(AiChatMessage.cache_creation_tokens).label('cache_creation_tokens'),
        func.sum(AiChatMessage.cache_read_tokens).label('cache_read_tokens'),
        func.count(AiChatMessage.id).label('message_count'),
    ).filter(
        AiChatMessage.agent_id == agent_id,
        AiChatMessage.role == 'assistant',
    ).first()

    # 最近30天趋势
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily = db.session.query(
        func.date(AiChatMessage.created_at).label('date'),
        func.sum(AiChatMessage.prompt_tokens).label('prompt_tokens'),
        func.sum(AiChatMessage.completion_tokens).label('completion_tokens'),
        func.sum(AiChatMessage.cache_creation_tokens).label('cache_creation_tokens'),
        func.sum(AiChatMessage.cache_read_tokens).label('cache_read_tokens'),
        func.count(AiChatMessage.id).label('message_count'),
    ).filter(
        AiChatMessage.agent_id == agent_id,
        AiChatMessage.role == 'assistant',
        AiChatMessage.created_at >= thirty_days_ago,
    ).group_by(
        func.date(AiChatMessage.created_at)
    ).order_by(
        func.date(AiChatMessage.created_at)
    ).all()

    # 缓存命中率最高的对话
    top_chats = db.session.query(
        AiChatMessage.chat_id,
        func.sum(AiChatMessage.cache_read_tokens).label('cache_read'),
        func.sum(AiChatMessage.prompt_tokens).label('prompt'),
    ).filter(
        AiChatMessage.agent_id == agent_id,
        AiChatMessage.role == 'assistant',
        AiChatMessage.cache_read_tokens > 0,
    ).group_by(
        AiChatMessage.chat_id
    ).order_by(
        desc(func.sum(AiChatMessage.cache_read_tokens))
    ).limit(10).all()

    total_prompt = stats.prompt_tokens or 0
    total_cache_read = stats.cache_read_tokens or 0

    return jsonify({
        'success': True,
        'data': {
            'agent': agent.to_dict(),
            'stats': {
                'prompt_tokens': total_prompt,
                'completion_tokens': stats.completion_tokens or 0,
                'cache_creation_tokens': stats.cache_creation_tokens or 0,
                'cache_read_tokens': total_cache_read,
                'message_count': stats.message_count or 0,
                'cache_hit_rate': round(total_cache_read / total_prompt * 100, 2) if total_prompt > 0 else 0,
            },
            'daily': [{
                'date': str(d.date),
                'prompt_tokens': d.prompt_tokens or 0,
                'completion_tokens': d.completion_tokens or 0,
                'cache_creation_tokens': d.cache_creation_tokens or 0,
                'cache_read_tokens': d.cache_read_tokens or 0,
                'message_count': d.message_count or 0,
            } for d in daily],
            'top_chats': [{
                'chat_id': t.chat_id,
                'cache_read_tokens': t.cache_read or 0,
                'prompt_tokens': t.prompt or 0,
            } for t in top_chats],
        }
    })
