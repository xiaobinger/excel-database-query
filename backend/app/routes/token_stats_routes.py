"""用户词元(Token)使用统计路由

口径说明：
- AI对话消耗：ai_chat_messages 表中 role='assistant' 的消息（token已由AiService记录），
  通过 chat_id 关联 ai_chats.user_id 归属到用户
- 工单消耗：tickets 表的 ai_*_tokens 字段（工单AI处理时由 accumulate_ai_token_usage 累加），
  归属到工单提交人 created_by
- 总消耗 = AI对话消耗 + 工单消耗
- 时间维度按 created_at（UTC存储）聚合，与缓存统计口径保持一致
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import db
from app.models.ai_chat import AiChat, AiChatMessage
from app.models.ticket import Ticket
from app.models.user import User
from app.utils.auth import login_required, permission_required, get_current_user

token_stats_bp = Blueprint('token_stats', __name__, url_prefix='/api/token-stats')

BEIJING_OFFSET = timedelta(hours=8)


def _parse_start_time():
    """解析查询参数 days（最近N天，0或不传表示全部），返回起始UTC时间或None"""
    days = request.args.get('days', type=int)
    if days is None or days <= 0:
        return None
    return datetime.utcnow() - timedelta(days=days)


def _beijing_today_start_utc():
    """北京时间今日0点对应的UTC时间"""
    beijing_now = datetime.utcnow() + BEIJING_OFFSET
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return beijing_today_start - BEIJING_OFFSET


def _ai_chat_agg(start=None, user_id=None):
    """AI对话token聚合（prompt/completion/总消耗/消息数）"""
    q = db.session.query(
        func.sum(AiChatMessage.prompt_tokens).label('prompt_tokens'),
        func.sum(AiChatMessage.completion_tokens).label('completion_tokens'),
        func.sum(AiChatMessage.tokens_used).label('total_tokens'),
        func.count(AiChatMessage.id).label('message_count'),
    ).join(AiChat, AiChatMessage.chat_id == AiChat.id).filter(
        AiChatMessage.role == 'assistant',
    )
    if user_id is not None:
        q = q.filter(AiChat.user_id == user_id)
    if start is not None:
        q = q.filter(AiChatMessage.created_at >= start)
    row = q.first()
    return {
        'prompt_tokens': int(row.prompt_tokens or 0),
        'completion_tokens': int(row.completion_tokens or 0),
        'total_tokens': int(row.total_tokens or 0),
        'message_count': int(row.message_count or 0),
    }


def _ticket_agg(start=None, user_id=None):
    """工单AI处理token聚合"""
    q = db.session.query(
        func.sum(Ticket.ai_prompt_tokens).label('prompt_tokens'),
        func.sum(Ticket.ai_completion_tokens).label('completion_tokens'),
        func.sum(Ticket.ai_total_tokens).label('total_tokens'),
        func.count(Ticket.id).label('ticket_count'),
    ).filter(Ticket.ai_total_tokens > 0)
    if user_id is not None:
        q = q.filter(Ticket.created_by == user_id)
    if start is not None:
        q = q.filter(Ticket.created_at >= start)
    row = q.first()
    return {
        'prompt_tokens': int(row.prompt_tokens or 0),
        'completion_tokens': int(row.completion_tokens or 0),
        'total_tokens': int(row.total_tokens or 0),
        'ticket_count': int(row.ticket_count or 0),
    }


@token_stats_bp.route('/overview', methods=['GET'])
@permission_required('token_stats')
def token_overview():
    """总览统计：总消耗、AI对话消耗、工单消耗（支持时间范围）"""
    start = _parse_start_time()
    ai_chat = _ai_chat_agg(start)
    ticket = _ticket_agg(start)
    total = ai_chat['total_tokens'] + ticket['total_tokens']
    return jsonify({
        'success': True,
        'data': {
            'total_tokens': total,
            'ai_chat_tokens': ai_chat['total_tokens'],
            'ticket_tokens': ticket['total_tokens'],
            'prompt_tokens': ai_chat['prompt_tokens'] + ticket['prompt_tokens'],
            'completion_tokens': ai_chat['completion_tokens'] + ticket['completion_tokens'],
            'ai_chat_prompt_tokens': ai_chat['prompt_tokens'],
            'ai_chat_completion_tokens': ai_chat['completion_tokens'],
            'ticket_prompt_tokens': ticket['prompt_tokens'],
            'ticket_completion_tokens': ticket['completion_tokens'],
            'chat_message_count': ai_chat['message_count'],
            'ticket_count': ticket['ticket_count'],
        }
    })


@token_stats_bp.route('/ranking', methods=['GET'])
@permission_required('token_stats')
def token_ranking():
    """用户使用量排名（支持时间范围），返回按总消耗降序的用户列表"""
    start = _parse_start_time()

    # AI对话按用户聚合
    ai_q = db.session.query(
        AiChat.user_id.label('user_id'),
        func.sum(AiChatMessage.tokens_used).label('ai_chat_tokens'),
        func.count(AiChatMessage.id).label('message_count'),
    ).join(AiChat, AiChatMessage.chat_id == AiChat.id).filter(
        AiChatMessage.role == 'assistant',
    )
    if start is not None:
        ai_q = ai_q.filter(AiChatMessage.created_at >= start)
    ai_rows = ai_q.group_by(AiChat.user_id).all()

    # 工单按提交人聚合
    tk_q = db.session.query(
        Ticket.created_by.label('user_id'),
        func.sum(Ticket.ai_total_tokens).label('ticket_tokens'),
        func.count(Ticket.id).label('ticket_count'),
    ).filter(Ticket.ai_total_tokens > 0)
    if start is not None:
        tk_q = tk_q.filter(Ticket.created_at >= start)
    tk_rows = tk_q.group_by(Ticket.created_by).all()

    # 合并两类数据
    merged = {}
    for r in ai_rows:
        u = merged.setdefault(r.user_id, {'ai_chat_tokens': 0, 'ticket_tokens': 0,
                                          'message_count': 0, 'ticket_count': 0})
        u['ai_chat_tokens'] = int(r.ai_chat_tokens or 0)
        u['message_count'] = int(r.message_count or 0)
    for r in tk_rows:
        u = merged.setdefault(r.user_id, {'ai_chat_tokens': 0, 'ticket_tokens': 0,
                                          'message_count': 0, 'ticket_count': 0})
        u['ticket_tokens'] = int(r.ticket_tokens or 0)
        u['ticket_count'] = int(r.ticket_count or 0)

    # 补充用户名信息
    user_ids = list(merged.keys())
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    ranking = []
    for uid, u in merged.items():
        total = u['ai_chat_tokens'] + u['ticket_tokens']
        ranking.append({
            'user_id': uid,
            'username': users[uid].username if uid in users else f'用户{uid}',
            'display_name': (users[uid].display_name if uid in users and users[uid].display_name
                             else (users[uid].username if uid in users else f'用户{uid}')),
            'ai_chat_tokens': u['ai_chat_tokens'],
            'ticket_tokens': u['ticket_tokens'],
            'total_tokens': total,
            'message_count': u['message_count'],
            'ticket_count': u['ticket_count'],
        })
    ranking.sort(key=lambda x: x['total_tokens'], reverse=True)

    grand_total = sum(r['total_tokens'] for r in ranking)
    for i, r in enumerate(ranking):
        r['rank'] = i + 1
        r['share'] = round(r['total_tokens'] / grand_total * 100, 2) if grand_total > 0 else 0

    return jsonify({'success': True, 'data': {'ranking': ranking[:100], 'grand_total': grand_total}})


@token_stats_bp.route('/trend', methods=['GET'])
@permission_required('token_stats')
def token_trend():
    """按日期维度的消耗趋势，粒度支持 day/week/month"""
    days = request.args.get('days', 30, type=int)
    granularity = request.args.get('granularity', 'day')
    if granularity not in ('day', 'week', 'month'):
        granularity = 'day'
    days = days if days and days > 0 else 30
    start = datetime.utcnow() - timedelta(days=days)

    # AI对话按天聚合
    ai_rows = db.session.query(
        func.date(AiChatMessage.created_at).label('date'),
        func.sum(AiChatMessage.tokens_used).label('tokens'),
    ).join(AiChat, AiChatMessage.chat_id == AiChat.id).filter(
        AiChatMessage.role == 'assistant',
        AiChatMessage.created_at >= start,
    ).group_by(func.date(AiChatMessage.created_at)).all()

    # 工单按天聚合
    tk_rows = db.session.query(
        func.date(Ticket.created_at).label('date'),
        func.sum(Ticket.ai_total_tokens).label('tokens'),
    ).filter(
        Ticket.ai_total_tokens > 0,
        Ticket.created_at >= start,
    ).group_by(func.date(Ticket.created_at)).all()

    # Python侧重分桶（day直接使用，week/month按日期归类）
    buckets = {}

    def bucket_of(date_str):
        d = date_str if isinstance(date_str, datetime) else datetime.strptime(str(date_str), '%Y-%m-%d')
        if granularity == 'month':
            return d.strftime('%Y-%m')
        if granularity == 'week':
            iso = d.isocalendar()
            return f'{iso[0]}-W{iso[1]:02d}'
        return d.strftime('%Y-%m-%d')

    for r in ai_rows:
        b = bucket_of(r.date)
        buckets.setdefault(b, {'ai_chat_tokens': 0, 'ticket_tokens': 0})
        buckets[b]['ai_chat_tokens'] += int(r.tokens or 0)
    for r in tk_rows:
        b = bucket_of(r.date)
        buckets.setdefault(b, {'ai_chat_tokens': 0, 'ticket_tokens': 0})
        buckets[b]['ticket_tokens'] += int(r.tokens or 0)

    # 日粒度补齐空缺日期，保证趋势图连续
    keys = sorted(buckets.keys())
    if granularity == 'day' and keys:
        cur = datetime.strptime(keys[0], '%Y-%m-%d')
        end = datetime.utcnow()
        while cur <= end:
            k = cur.strftime('%Y-%m-%d')
            if k not in buckets:
                buckets[k] = {'ai_chat_tokens': 0, 'ticket_tokens': 0}
            cur += timedelta(days=1)
        keys = sorted(buckets.keys())

    trend = [{
        'date': k,
        'ai_chat_tokens': buckets[k]['ai_chat_tokens'],
        'ticket_tokens': buckets[k]['ticket_tokens'],
        'total_tokens': buckets[k]['ai_chat_tokens'] + buckets[k]['ticket_tokens'],
    } for k in keys]

    return jsonify({'success': True, 'data': {'trend': trend, 'granularity': granularity}})


@token_stats_bp.route('/my', methods=['GET'])
@login_required
def my_token_stats():
    """当前用户自己的Token消耗指标（顶栏与个人中心展示用）"""
    user = get_current_user()
    uid = user.id

    total_ai = _ai_chat_agg(user_id=uid)
    total_tk = _ticket_agg(user_id=uid)

    # 今日消耗（北京时间今日0点起）
    today_start = _beijing_today_start_utc()
    today_ai = _ai_chat_agg(start=today_start, user_id=uid)
    today_tk = _ticket_agg(start=today_start, user_id=uid)

    # 近30天消耗
    start_30d = datetime.utcnow() - timedelta(days=30)
    recent_ai = _ai_chat_agg(start=start_30d, user_id=uid)
    recent_tk = _ticket_agg(start=start_30d, user_id=uid)

    return jsonify({
        'success': True,
        'data': {
            'total_tokens': total_ai['total_tokens'] + total_tk['total_tokens'],
            'ai_chat_tokens': total_ai['total_tokens'],
            'ticket_tokens': total_tk['total_tokens'],
            'today_tokens': today_ai['total_tokens'] + today_tk['total_tokens'],
            'last_30d_tokens': recent_ai['total_tokens'] + recent_tk['total_tokens'],
            'chat_message_count': total_ai['message_count'],
            'ticket_count': total_tk['ticket_count'],
        }
    })
