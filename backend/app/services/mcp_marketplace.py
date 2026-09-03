"""MCP 精选市场目录

内置热门 MCP server 目录，供"从市场快速引入"。条目字段：
- name/title/category/description: 展示信息（name 同时是引入时的建议服务名）
- transport_type: stdio / streamable_http / sse
- command / url: 连接配置（command 中的路径/参数占位由用户引入后修改）
- env_keys: 需要配置的环境变量（[{key, required, description}]）
- note: 引入时的额外提示

说明：stdio 服务要求服务器已安装对应运行时（npx 需 Node.js、uvx 需 uv）。
"""

MARKET_ITEMS = [
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
    },
    {
        'name': 'memory',
        'title': 'Memory',
        'category': '知识与记忆',
        'description': '基于知识图谱的持久化记忆（实体/关系/观察的增删改查）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-memory',
        'url': None,
        'env_keys': [],
        'note': None,
    },
    {
        'name': 'sequentialthinking',
        'title': 'Sequential Thinking',
        'category': '知识与记忆',
        'description': '结构化的逐步思考与思维链修订工具，适合复杂推理任务',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-sequentialthinking',
        'url': None,
        'env_keys': [],
        'note': None,
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
    },
    {
        'name': 'sqlite',
        'title': 'SQLite',
        'category': '数据库',
        'description': '操作 SQLite 数据库（查询/建表/写入，需服务器安装 uv）',
        'transport_type': 'stdio',
        'command': 'uvx mcp-server-sqlite --db-path C:\\data\\app.db',
        'url': None,
        'env_keys': [],
        'note': '请将 --db-path 替换为实际数据库文件路径',
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
    },

    # ============ 浏览器自动化 ============
    {
        'name': 'puppeteer',
        'title': 'Puppeteer',
        'category': '浏览器自动化',
        'description': '浏览器自动化（导航/截图/点击/填表/执行 JS）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-puppeteer',
        'url': None,
        'env_keys': [],
        'note': '服务器需要可用的浏览器运行环境',
    },
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
    },

    # ============ 搜索与知识 ============
    {
        'name': 'brave-search',
        'title': 'Brave Search',
        'category': '网络与搜索',
        'description': 'Brave 网络搜索与本地搜索（网页/图片/新闻）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-brave-search',
        'url': None,
        'env_keys': [
            {'key': 'BRAVE_API_KEY', 'required': True, 'description': 'Brave Search API 密钥'},
        ],
        'note': None,
    },
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
    },

    # ============ 协作办公 ============
    {
        'name': 'slack',
        'title': 'Slack',
        'category': '协作',
        'description': '访问 Slack（频道消息收发/历史/用户信息）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-slack',
        'url': None,
        'env_keys': [
            {'key': 'SLACK_BOT_TOKEN', 'required': True, 'description': 'Slack Bot 用户令牌 (xoxp-...)'},
            {'key': 'SLACK_TEAM_ID', 'required': True, 'description': 'Slack 团队 ID (T 开头)'},
        ],
        'note': None,
    },
    {
        'name': 'google-maps',
        'title': 'Google Maps',
        'category': '工具与效率',
        'description': '地理位置服务（地图/路线/地点搜索/距离）',
        'transport_type': 'stdio',
        'command': 'npx -y @modelcontextprotocol/server-google-maps',
        'url': None,
        'env_keys': [
            {'key': 'GOOGLE_MAPS_API_KEY', 'required': True, 'description': 'Google Maps API 密钥'},
        ],
        'note': None,
    },
]


def get_marketplace(imported_names: set = None) -> list:
    """返回市场目录（按分类排序）。

    imported_names: 已导入的服务名称集合，用于标记已导入的条目。
    """
    imported_names = imported_names or set()
    items = []
    for item in sorted(MARKET_ITEMS, key=lambda x: (x['category'], x['title'])):
        item_copy = dict(item)
        item_copy['imported'] = item['name'] in imported_names
        items.append(item_copy)
    return items
