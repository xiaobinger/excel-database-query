"""个性化插件服务

插件清单集中定义在这里，前端通过 /api/widgets 获取可用清单。
新增插件只需：后端 WIDGETS 增加定义 + 前端 widgetRegistry 注册组件。
"""
import ipaddress
import re
import socket
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests

from app.utils.helpers import format_beijing

WEATHER_CACHE_TTL = 600
NEWS_CACHE_TTL = 600
STOCKS_CACHE_TTL = 30
HTTP_TIMEOUT = 10
MAX_RESPONSE_BYTES = 3 * 1024 * 1024

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'

WIDGETS = [
    {
        'key': 'clock',
        'name': '时钟',
        'icon': 'fa-clock',
        'description': '当前时间、日期与星期',
        'default_settings': {},
    },
    {
        'key': 'almanac',
        'name': '黄历',
        'icon': 'fa-calendar-day',
        'description': '农历、干支与每日宜忌',
        'default_settings': {},
    },
    {
        'key': 'weather',
        'name': '天气',
        'icon': 'fa-cloud-sun',
        'description': '实时天气与今日温度',
        'default_settings': {'city': '深圳'},
    },
    {
        'key': 'news',
        'name': '支付圈新闻',
        'icon': 'fa-newspaper',
        'description': '可配置 RSS 资讯源',
        'default_settings': {'feed_url': 'https://www.36kr.com/feed'},
    },
    {
        'key': 'todo',
        'name': '系统待办',
        'icon': 'fa-list-check',
        'description': '待我处理的工单与待核实事项',
        'default_settings': {'limit': 5},
    },
    {
        'key': 'sticker',
        'name': '自定义贴图',
        'icon': 'fa-note-sticky',
        'description': '上传贴图或写一张便签',
        'default_settings': {'text': '', 'color': '#fff7e6', 'image': ''},
    },
    {
        'key': 'stocks',
        'name': '自选股行情',
        'icon': 'fa-chart-line',
        'description': '实时指数与自选股报价',
        'default_settings': {'symbols': 'sh000001,sz399001'},
    },
]

WIDGET_KEYS = [w['key'] for w in WIDGETS]
WIDGET_MAP = {w['key']: w for w in WIDGETS}

TICKET_STATUS_LABELS = {
    'draft': '草稿',
    'submitted': '已提交',
    'received': '已接收',
    'processing': '处理中',
    'pending_assignment': '待指派',
    'pending_confirmation': '待确认',
    'processed': '待核实',
    'rejected': '已驳回',
    'closed': '已结束',
}

_cache = {}


class WidgetError(Exception):
    """插件数据获取失败（返回给前端展示）"""


def get_allowed_widget_keys(user):
    """返回用户当前被授权的插件 key 列表"""
    if not user:
        return []
    if user.is_admin():
        return list(WIDGET_KEYS)
    if not user.role:
        return []
    perms = user.role.get_widget_permissions()
    if 'all' in perms:
        return list(WIDGET_KEYS)
    return [k for k in WIDGET_KEYS if k in perms]


def get_definitions(allowed_keys):
    return [dict(WIDGET_MAP[k]) for k in WIDGET_KEYS if k in allowed_keys]


def normalize_config(raw, allowed_keys):
    """把用户存储的配置归一化为合法结构，并与当前授权取交集"""
    raw = raw if isinstance(raw, dict) else {}
    raw_settings = raw.get('settings') if isinstance(raw.get('settings'), dict) else {}

    enabled = [k for k in (raw.get('enabled') or []) if k in allowed_keys]
    order = [k for k in (raw.get('order') or []) if k in allowed_keys]
    for key in allowed_keys:
        if key not in order:
            order.append(key)
    # 未配置过时默认启用全部已授权插件，管理员授权后即可直接看到
    if 'enabled' not in raw:
        enabled = list(allowed_keys)
    enabled = [k for k in order if k in enabled]

    settings = {}
    for key in allowed_keys:
        defaults = dict(WIDGET_MAP[key]['default_settings'])
        user_settings = raw_settings.get(key)
        if isinstance(user_settings, dict):
            for field in defaults:
                if field in user_settings:
                    defaults[field] = user_settings[field]
        settings[key] = _sanitize_settings(key, defaults)

    return {
        'enabled': enabled,
        'order': order,
        'settings': settings,
        'collapsed': bool(raw.get('collapsed', False)),
    }


def _sanitize_settings(key, settings):
    if key == 'weather':
        settings['city'] = str(settings.get('city') or '').strip()[:50] or '深圳'
    elif key == 'news':
        settings['feed_url'] = str(settings.get('feed_url') or '').strip()[:500]
    elif key == 'stocks':
        raw = str(settings.get('symbols') or '')
        symbols = [s.strip().lower() for s in raw.split(',') if s.strip()]
        settings['symbols'] = ','.join(symbols[:20]) or 'sh000001,sz399001'
    elif key == 'todo':
        try:
            settings['limit'] = max(1, min(20, int(settings.get('limit') or 5)))
        except (TypeError, ValueError):
            settings['limit'] = 5
    elif key == 'sticker':
        settings['text'] = str(settings.get('text') or '')[:1000]
        color = str(settings.get('color') or '#fff7e6')
        settings['color'] = color if re.match(r'^#[0-9a-fA-F]{6}$', color) else '#fff7e6'
        settings['image'] = str(settings.get('image') or '')[:200]
    return settings


def _cache_get(key):
    item = _cache.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > value[0]:
        return None
    return value[1]


def _cache_set(key, ttl, value):
    _cache[key] = (time.time(), (ttl, value))


def _is_safe_public_url(url):
    """仅允许 http/https 且不允许内网/本机地址，避免 SSRF"""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in ('localhost',):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def fetch_weather(city):
    city = (city or '').strip()[:50]
    if not city:
        raise WidgetError('请先在个人中心设置天气城市')
    cache_key = 'weather:' + city
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        geo_resp = requests.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': city, 'count': 1, 'language': 'zh', 'format': 'json'},
            timeout=HTTP_TIMEOUT,
            headers={'User-Agent': USER_AGENT},
        )
        geo_resp.raise_for_status()
        results = (geo_resp.json() or {}).get('results') or []
    except requests.RequestException as exc:
        raise WidgetError(f'城市查询失败：{exc}') from exc

    if not results:
        raise WidgetError(f'未找到城市「{city}」')

    place = results[0]
    try:
        weather_resp = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': place.get('latitude'),
                'longitude': place.get('longitude'),
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m',
                'daily': 'temperature_2m_max,temperature_2m_min,weather_code',
                'timezone': 'auto',
                'forecast_days': 1,
            },
            timeout=HTTP_TIMEOUT,
            headers={'User-Agent': USER_AGENT},
        )
        weather_resp.raise_for_status()
        payload = weather_resp.json() or {}
    except requests.RequestException as exc:
        raise WidgetError(f'天气获取失败：{exc}') from exc

    current = payload.get('current') or {}
    daily = payload.get('daily') or {}

    def _first(seq):
        return seq[0] if isinstance(seq, list) and seq else None

    data = {
        'city': place.get('name') or city,
        'region': ' '.join(filter(None, [place.get('admin1'), place.get('country')])),
        'temperature': current.get('temperature_2m'),
        'apparent_temperature': current.get('apparent_temperature'),
        'humidity': current.get('relative_humidity_2m'),
        'wind_speed': current.get('wind_speed_10m'),
        'weather_code': current.get('weather_code'),
        'high': _first(daily.get('temperature_2m_max')),
        'low': _first(daily.get('temperature_2m_min')),
        'updated_at': current.get('time') or '',
    }
    _cache_set(cache_key, WEATHER_CACHE_TTL, data)
    return data


def _strip_tags(value):
    return re.sub(r'<[^>]+>', '', value or '').strip()


def _local_name(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _find_child(node, name):
    for child in node:
        if _local_name(child.tag) == name:
            return child
    return None


def _fetch_feed_response(feed_url):
    """请求 RSS 源；手动处理重定向并逐跳校验地址，避免 SSRF"""
    url = feed_url
    for _ in range(4):
        if not _is_safe_public_url(url):
            raise WidgetError('RSS 地址不合法或不允许访问内网地址')
        try:
            resp = requests.get(
                url,
                timeout=HTTP_TIMEOUT,
                headers={
                    'User-Agent': USER_AGENT,
                    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
                },
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise WidgetError(f'资讯源请求失败：{exc}') from exc

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get('Location', '')
            if not location:
                raise WidgetError('资讯源重定向地址为空')
            url = urljoin(url, location)
            continue

        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise WidgetError(f'资讯源请求失败：{exc}') from exc
        return resp

    raise WidgetError('资讯源重定向次数过多')


def fetch_news(feed_url):
    feed_url = (feed_url or '').strip()
    if not feed_url:
        raise WidgetError('请先在个人中心配置 RSS 资讯源')

    cache_key = 'news:' + feed_url
    cached = _cache_get(cache_key)
    if cached:
        return cached

    resp = _fetch_feed_response(feed_url)

    content = resp.content[:MAX_RESPONSE_BYTES]
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise WidgetError('资讯源不是有效的 RSS/Atom 内容') from exc

    entries = [n for n in root.iter() if _local_name(n.tag) in ('item', 'entry')]
    items = []
    for entry in entries[:8]:
        title_node = _find_child(entry, 'title')
        title = _strip_tags(title_node.text if title_node is not None else '')
        if not title:
            continue

        link = ''
        link_node = _find_child(entry, 'link')
        if link_node is not None:
            link = (link_node.text or '').strip() or link_node.attrib.get('href', '').strip()
        if not link:
            guid_node = _find_child(entry, 'guid')
            if guid_node is not None and (guid_node.text or '').startswith('http'):
                link = guid_node.text.strip()

        date_node = _find_child(entry, 'pubDate')
        if date_node is None:
            date_node = _find_child(entry, 'published')
        if date_node is None:
            date_node = _find_child(entry, 'updated')
        published = (date_node.text or '').strip() if date_node is not None else ''

        items.append({'title': title, 'link': link, 'published': published})

    if not items:
        raise WidgetError('资讯源暂无可解析的内容')

    data = {'feed_url': feed_url, 'items': items}
    _cache_set(cache_key, NEWS_CACHE_TTL, data)
    return data


SYMBOL_RE = re.compile(r'^(sh|sz|bj)[0-9]{6}$', re.IGNORECASE)


def fetch_stocks(symbols):
    raw = (symbols or '').strip().lower()
    symbol_list = [s for s in raw.split(',') if s]
    if not symbol_list:
        raise WidgetError('请先在个人中心配置自选股代码')
    for symbol in symbol_list:
        if not SYMBOL_RE.match(symbol):
            raise WidgetError(f'股票代码格式不正确：{symbol}')

    cache_key = 'stocks:' + ','.join(symbol_list)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        resp = requests.get(
            'https://qt.gtimg.cn/q=' + ','.join(symbol_list),
            timeout=HTTP_TIMEOUT,
            headers={'User-Agent': USER_AGENT, 'Referer': 'https://gu.qq.com/'},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise WidgetError(f'行情获取失败：{exc}') from exc

    text = resp.content.decode('gbk', errors='ignore')
    quotes = []
    for line in text.splitlines():
        match = re.match(r'v_([a-zA-Z0-9.]+)="(.*)";?', line.strip())
        if not match:
            continue
        fields = match.group(2).split('~')
        if len(fields) < 35:
            continue
        try:
            quotes.append({
                'symbol': match.group(1),
                'name': fields[1],
                'code': fields[2],
                'price': float(fields[3]) if fields[3] else None,
                'prev_close': float(fields[4]) if fields[4] else None,
                'open': float(fields[5]) if fields[5] else None,
                'change': float(fields[31]) if fields[31] else 0.0,
                'change_pct': float(fields[32]) if fields[32] else 0.0,
                'high': float(fields[33]) if fields[33] else None,
                'low': float(fields[34]) if fields[34] else None,
                'time': fields[30],
            })
        except (ValueError, IndexError):
            continue

    if not quotes:
        raise WidgetError('未获取到行情数据，请检查股票代码')

    data = {'items': quotes, 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    _cache_set(cache_key, STOCKS_CACHE_TTL, data)
    return data


def fetch_todos(user, limit=5):
    from sqlalchemy import and_, or_
    from app.models.ticket import Ticket

    limit = max(1, min(20, int(limit or 5)))
    active_statuses = ('submitted', 'received', 'processing', 'pending_assignment')
    conditions = [
        and_(Ticket.assignee_type == 'user', Ticket.assignee_id == user.id, Ticket.status.in_(active_statuses)),
        and_(Ticket.created_by == user.id, Ticket.status.in_(('pending_confirmation', 'processed'))),
    ]
    tickets = (
        Ticket.query
        .filter(or_(*conditions))
        .order_by(Ticket.updated_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for ticket in tickets:
        if ticket.status == 'pending_confirmation':
            action = '待确认执行'
        elif ticket.created_by == user.id and ticket.status == 'processed':
            action = '待我核实'
        else:
            action = '待我处理'
        items.append({
            'id': ticket.id,
            'ticket_no': ticket.ticket_no,
            'title': ticket.title,
            'status': ticket.status,
            'status_label': TICKET_STATUS_LABELS.get(ticket.status, ticket.status),
            'action': action,
            'updated_at': format_beijing(ticket.updated_at, '%m-%d %H:%M') or '',
        })
    return {'items': items, 'count': len(items)}
