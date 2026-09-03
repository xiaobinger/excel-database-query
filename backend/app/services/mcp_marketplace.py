"""MCP 精选市场目录

支持从外部 MCP 市场 API 实时拉取热门服务：
- Smithery Registry (https://registry.smithery.ai)
- Official MCP Registry (https://registry.modelcontextprotocol.io)

内置静态条目作为兜底和补充。

条目字段：
- name/title/category/description: 展示信息
- transport_type: stdio / streamable_http / sse
- command / url: 连接配置
- env_keys: 需要配置的环境变量 [{key, required, description}]
- note: 引入时的额外提示
- source: 数据来源 'smithery' | 'official' | 'static'
- icon_url: 图标 URL
- use_count: 使用次数（Smithery）
"""

import json
import logging
import os
import time
from datetime import datetime
from functools import lru_cache
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# ============ 市场源配置 ============

SMITHERY_API = "https://registry.smithery.ai/servers?limit=50"
OFFICIAL_API = "https://registry.modelcontextprotocol.io/v0/servers?limit=30"

# 市场源定义
MARKET_SOURCES = {
    'smithery': {
        'name': 'Smithery',
        'url': SMITHERY_API,
        'fetch_func': '_fetch_smithery',
    },
    'official': {
        'name': '官方注册表',
        'url': OFFICIAL_API,
        'fetch_func': '_fetch_official',
    },
}

# 内置静态条目（兜底）
STATIC_ITEMS = [
    # ============ 官方参考实现 ============
    {
        'name': 'filesystem',
        'title': 'Filesystem',
        'category': '文件与数据',
        'description': '让模型以受限方式访问本地文件系统（读写文件、搜索、目录管理）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-filesystem C:\\data',
        'url': None,
        'env_keys': [],
        'note': '请将命令末尾的路径替换为实际允许访问的目录，可配置多个目录',
        'source': 'static',
    },
    {
        'name': 'fetch',
        'title': 'Fetch',
        'category': '网络与搜索',
        'description': '抓取网页内容并转换为 Markdown 供模型阅读（需服务器安装 uv）',
        'transport_type': 'stdio',
        'command': 'uvx mcp-server-fetch',
        'url': None,
        'env_keys': [],
        'note': None,
        'source': 'static',
    },
    {
        'name': 'time',
        'title': 'Time',
        'category': '工具与效率',
        'description': '获取当前时间和时区转换（需服务器安装 uv）',
        'transport_type': 'stdio',
        'command': 'uvx mcp-server-time',
        'url': None,
        'env_keys': [],
        'note': None,
        'source': 'static',
    },
    {
        'name': 'everything',
        'title': 'Everything',
        'category': '工具与效率',
        'description': '官方测试服务器，覆盖 MCP 所有能力（工具/资源/提示词），适合验证集成',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-everything',
        'url': None,
        'env_keys': [],
        'note': None,
        'source': 'static',
    },
    # ============ 开发与数据库 ============
    {
        'name': 'github',
        'title': 'GitHub',
        'category': '开发',
        'description': '访问 GitHub 仓库、issue、PR、代码搜索与文件操作',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-github',
        'url': None,
        'env_keys': [
            {'key': 'GITHUB_PERSONAL_ACCESS_TOKEN', 'required': True, 'description': 'GitHub 个人访问令牌'},
        ],
        'note': None,
        'source': 'static',
    },
    {
        'name': 'git',
        'title': 'Git',
        'category': '开发',
        'description': '操作本地 Git 仓库（状态/分支/日志/diff/提交等，需服务器安装 uv）',
        'transport_type': 'stdio',
        'command': 'uvx mcp-server-git --repository C:\\repo',
        'url': None,
        'env_keys': [],
        'note': '请将 --repository 替换为实际仓库路径',
        'source': 'static',
    },
    {
        'name': 'postgres',
        'title': 'PostgreSQL',
        'category': '数据库',
        'description': '只读访问 PostgreSQL 数据库（表结构查询与只读 SQL）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-postgres postgresql://user:pass@localhost:5432/dbname',
        'url': None,
        'env_keys': [],
        'note': '请将命令末尾替换为实际连接串',
        'source': 'static',
    },
    {
        'name': 'sentry',
        'title': 'Sentry',
        'category': '开发',
        'description': '查询 Sentry 的 issue、错误堆栈与项目信息',
        'transport_type': 'stdio',
        'command': 'npx -y @sentry/mcp-server',
        'url': None,
        'env_keys': [
            {'key': 'SENTRY_ACCESS_TOKEN', 'required': True, 'description': 'Sentry 访问令牌'},
        ],
        'note': None,
        'source': 'static',
    },
    # ============ 浏览器自动化 ============
    {
        'name': 'playwright',
        'title': 'Playwright',
        'category': '浏览器自动化',
        'description': 'Playwright 浏览器自动化（快照交互、多标签页、网络拦截）',
        'transport_type': 'stdio',
        'command': 'npx -y @playwright/mcp@latest',
        'url': None,
        'env_keys': [],
        'note': None,
        'source': 'static',
    },
    # ============ 搜索与知识 ============
    {
        'name': 'context7',
        'title': 'Context7',
        'category': '知识与记忆',
        'description': '获取各类库/框架的最新官方文档与代码示例，减少模型过时幻觉',
        'transport_type': 'streamable_http',
        'command': None,
        'url': 'https://mcp.context7.com/mcp',
        'env_keys': [],
        'note': '也可改用 stdio 方式：npx -y @upstash/context7-mcp',
        'source': 'static',
    },
    {
        'name': 'deepwiki',
        'title': 'DeepWiki',
        'category': '知识与记忆',
        'description': '查询 GitHub 仓库的自动生成 Wiki（架构/设计/使用方式）',
        'transport_type': 'streamable_http',
        'command': None,
        'url': 'https://mcp.deepwiki.com/mcp',
        'env_keys': [],
        'note': None,
        'source': 'static',
    },
]


def _http_get(url, timeout=10):
    """HTTP GET 请求，返回 JSON"""
    req = Request(url)
    req.add_header('User-Agent', 'MCP-Marketplace/1.0')
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (URLError, HTTPError, TimeoutError) as e:
        logger.warning(f"API 请求失败: {url} - {e}")
        return None


def _fetch_smithery():
    """从 Smithery Registry 拉取热门 MCP 服务"""
    data = _http_get(SMITHERY_API)
    if not data or 'servers' not in data:
        logger.warning("Smithery API 返回数据异常")
        return []

    items = []
    for srv in data['servers']:
        try:
            # 跳过 inactive / unlisted 的服务
            if srv.get('inactive') or srv.get('unlisted'):
                continue

            qualified_name = srv.get('qualifiedName', '')
            # 解析 category（根据名称或描述简单分类）
            cat = _infer_category(srv)

            # 获取 env_keys（从 connections.configSchema）
            env_keys = []
            connections = srv.get('connections', [])
            for conn in connections:
                if conn.get('type') == 'http':
                    schema = conn.get('configSchema', {})
                    required = schema.get('required', [])
                    properties = schema.get('properties', {})
                    for prop_name, prop_info in properties.items():
                        env_keys.append({
                            'key': prop_name.upper(),
                            'required': prop_name in required,
                            'description': prop_info.get('description', prop_info.get('title', '')),
                        })

            item = {
                'name': qualified_name,
                'title': srv.get('displayName', qualified_name),
                'category': cat,
                'description': srv.get('description', ''),
                'transport_type': 'streamable_http' if srv.get('remote') else 'stdio',
                'url': srv.get('deploymentUrl'),
                'command': None if srv.get('remote') else f'npm install -g {qualified_name} && {qualified_name}',
                'env_keys': env_keys,
                'note': srv.get('homepage'),
                'source': 'smithery',
                'icon_url': srv.get('iconUrl'),
                'use_count': srv.get('useCount', 0),
                'verified': srv.get('verified', False),
            }
            items.append(item)
        except Exception as e:
            logger.warning(f"Smithery 解析条目失败 {srv.get('qualifiedName')}: {e}")
            continue

    # 按使用量排序
    items.sort(key=lambda x: x.get('use_count', 0), reverse=True)
    return items


def _fetch_official():
    """从官方 MCP Registry 拉取服务"""
    data = _http_get(OFFICIAL_API)
    if not data or 'servers' not in data:
        logger.warning("Official Registry API 返回数据异常")
        return []

    items = []
    seen = set()
    for entry in data['servers']:
        try:
            srv = entry.get('server', {})
            name = srv.get('name', '')
            if not name or name in seen:
                continue
            seen.add(name)

            # 获取 HTTP URL
            urls = []
            for remote in srv.get('remotes', []):
                if remote.get('type') in ('streamable-http', 'sse'):
                    urls.append(remote.get('url'))

            # 获取 npm 包信息
            packages = srv.get('packages', {})
            npm_id = None
            for reg_type, pkg_list in packages.items():
                if isinstance(pkg_list, list) and pkg_list:
                    npm_id = pkg_list[0].get('identifier')
                    break
                elif isinstance(pkg_list, dict):
                    npm_id = pkg_list.get('identifier')

            cat = _infer_category_from_name(name)

            item = {
                'name': name,
                'title': srv.get('title') or name.split('/')[-1],
                'category': cat,
                'description': srv.get('description', ''),
                'transport_type': 'streamable_http' if urls else 'stdio',
                'url': urls[0] if urls else None,
                'command': f'npx -y {npm_id}' if npm_id else None,
                'env_keys': [],
                'note': f'NPM: {npm_id}' if npm_id else None,
                'source': 'official',
                'verified': entry.get('_meta', {}).get('io.modelcontextprotocol.registry/official', {}).get('status') == 'active',
            }
            items.append(item)
        except Exception as e:
            logger.warning(f"Official Registry 解析条目失败 {name}: {e}")
            continue

    return items


def _infer_category(srv):
    """根据 Smithery 服务推断分类"""
    desc = (srv.get('description', '') + ' ' + srv.get('displayName', '')).lower()
    name = srv.get('qualifiedName', '').lower()

    if any(kw in desc for kw in ['search', 'weather', 'news', 'calendar']):
        return '网络与搜索'
    if any(kw in desc for kw in ['github', 'git', 'docker', 'k8s']):
        return '开发'
    if any(kw in desc for kw in ['database', 'sql', 'postgres', 'sqlite']):
        return '数据库'
    if any(kw in desc for kw in ['gmail', 'slack', 'email', 'calendar', 'drive', 'sheet']):
        return '协作办公'
    if any(kw in desc for kw in ['file', 'wiki', 'memory', 'knowledge']):
        return '知识与记忆'
    return '其他'


def _infer_category_from_name(name):
    """根据名称推断分类"""
    if 'search' in name or 'weather' in name or 'news' in name:
        return '网络与搜索'
    if 'github' in name or 'git' in name or 'docker' in name:
        return '开发'
    if 'db' in name or 'postgres' in name or 'sql' in name:
        return '数据库'
    if 'mail' in name or 'slack' in name or 'calendar' in name:
        return '协作办公'
    return '其他'


def get_marketplace(source=None, imported_names: set = None) -> list:
    """返回市场目录。

    source: 'smithery' | 'official' | None（拉取所有源）
    imported_names: 已导入的服务名称集合，用于标记已导入的条目。
    """
    imported_names = imported_names or set()

    # 拉取远程市场
    remote_items = []
    if source is None or source == 'smithery':
        try:
            remote_items.extend(_fetch_smithery())
        except Exception as e:
            logger.warning(f"拉取 Smithery 市场失败: {e}")

    if source is None or source == 'official':
        try:
            remote_items.extend(_fetch_official())
        except Exception as e:
            logger.warning(f"拉取官方注册表失败: {e}")

    # 合并静态条目
    static_items = [dict(item) for item in STATIC_ITEMS]

    # 去重（按 name）
    all_items = remote_items + static_items
    seen = set()
    unique_items = []
    for item in all_items:
        if item['name'] not in seen:
            seen.add(item['name'])
            unique_items.append(item)

    # 标记已导入
    result = []
    for item in unique_items:
        item_copy = dict(item)
        item_copy['imported'] = item['name'] in imported_names
        result.append(item_copy)

    return result


def refresh_marketplace():
    """清除所有缓存，下次调用时重新拉取"""
    _clear_cache()
    return {'success': True, 'message': '市场缓存已清除，下次请求将重新拉取'}


def get_source_status():
    """获取各市场源的缓存状态"""
    status = {}
    for src in ['smithery', 'official']:
        cache_key = f"marketplace_{src}"
        entry = _market_cache.get(cache_key)
        now = time.monotonic()

        if entry and now - entry['time'] < CACHE_TTL:
            status[src] = {
                'available': True,
                'count': len(entry['data']),
                'cached': True,
                'last_updated': entry['time'],
            }
        else:
            try:
                url = SMITHERY_API if src == 'smithery' else OFFICIAL_API
                data = _http_get(url, timeout=5)
                count = len(data.get('servers', [])) if data else 0
                status[src] = {'available': True, 'count': count, 'cached': False}
            except:
                status[src] = {'available': False, 'count': 0, 'cached': False}
    return status


def clear_cache(source=None):
    """清除指定或所有市场缓存"""
    _clear_cache(source)
    return {'success': True}
