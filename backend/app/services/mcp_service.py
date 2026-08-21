"""MCP Server 服务

- McpClientManager: 单例，后台事件循环线程 + MCP 会话池
  （官方 mcp SDK 为异步 API，Flask 为同步框架，通过 run_coroutine_threadsafe 桥接）
- 工具注入: get_agent_mcp_tools() 读取 tools_cache 转为 OpenAI function 格式
- 调用分发: call_tool_by_prefixed_name() 解析 mcp__{server}__{tool} 前缀
"""
import asyncio
import concurrent.futures
import json
import logging
import os
import re
import shlex
import threading
import time

logger = logging.getLogger(__name__)

# MCP 工具名前缀: mcp__{server_name}__{tool_name}
MCP_TOOL_PREFIX = 'mcp__'

# Server 名称格式（用于工具前缀，避免产生非法工具名；禁止连续下划线，
# 因为 __ 是 mcp__{server}__{tool} 的分隔符，服务名含 __ 会导致工具名无法回环解析）
SERVER_NAME_PATTERN = re.compile(r'^(?!.*__)[a-zA-Z][a-zA-Z0-9_-]{0,63}$')


def _sdk():
    """懒加载官方 mcp SDK，未安装时给出明确错误"""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.sse import sse_client
        # 兼容不同版本：新版SDK为 streamable_http_client，旧版为 streamablehttp_client
        try:
            from mcp.client.streamable_http import streamable_http_client as _http_client
        except ImportError:
            from mcp.client.streamable_http import streamablehttp_client as _http_client
        return {
            'ClientSession': ClientSession,
            'StdioServerParameters': StdioServerParameters,
            'stdio_client': stdio_client,
            'sse_client': sse_client,
            'streamablehttp_client': _http_client,
        }
    except ImportError as e:
        raise RuntimeError(f'mcp SDK 未安装，请执行: pip install mcp ({e})')


def _split_command(command: str) -> list:
    """解析stdio启动命令为参数数组，不经shell执行。

    Windows下shlex的posix模式会把反斜杠当转义符吞掉（如C:\\Users\\...路径），
    因此Windows用posix=False保留反斜杠，再剥除成对引号。
    """
    command = (command or '').strip()
    if not command:
        return []
    if os.name == 'nt':
        argv = []
        for token in shlex.split(command, posix=False):
            if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
                token = token[1:-1]
            if token:
                argv.append(token)
        return argv
    return shlex.split(command)


def _sanitize_server_name(base: str) -> str:
    """将任意字符串清洗为合法的 server 名称（字母开头、无连续下划线）"""
    name = re.sub(r'[^a-zA-Z0-9_-]', '-', (base or '').strip())
    name = name.strip('-')[:64]
    if not name or not name[0].isalpha():
        name = 'mcp-' + name if name else 'imported'
    if '__' in name:
        name = re.sub(r'_+', '_', name)
    return name


def _parse_mcp_entry(name: str, v: dict) -> dict:
    """解析单个 MCP server 配置条目，返回标准字段 dict 或 None"""
    if not isinstance(v, dict):
        return None
    entry_type = (v.get('type') or '').lower()

    # stdio：command (+args) (+env)，兼容 Claude Desktop / Cursor 格式
    if v.get('command'):
        parts = [str(v['command'])] + [str(a) for a in (v.get('args') or []) if a is not None]
        quoted = []
        for p in parts:
            if ' ' in p and not (p.startswith('"') or p.startswith("'")):
                p = f'"{p}"'
            quoted.append(p)
        return {
            'name': name,
            'transport_type': 'stdio',
            'command': ' '.join(quoted),
            'url': None,
            'env': {str(k): str(x) for k, x in (v.get('env') or {}).items() if x is not None},
            'headers': {},
            'description': str(v.get('description') or ''),
        }

    # 远程：url (+headers)，type 为 sse/http/streamable_http
    if v.get('url'):
        transport = 'sse' if entry_type == 'sse' else 'streamable_http'
        return {
            'name': name,
            'transport_type': transport,
            'command': None,
            'url': str(v['url']),
            'env': {},
            'headers': {str(k): str(x) for k, x in (v.get('headers') or {}).items() if x is not None},
            'description': str(v.get('description') or ''),
        }
    return None


def parse_mcp_config(text: str) -> dict:
    """解析 MCP JSON 配置文本，兼容主流客户端格式：

    1. {"mcpServers": {"name": {"command": ..., "args": [...], "env": {...}}}}
       — Claude Desktop / Cursor / VS Code 导出格式
    2. {"name1": {...}, "name2": {...}} — 顶层直接是服务映射
    3. {"command": ...} / {"url": ...} — 单个服务（无名称时自动推导）

    返回 {'success': True, 'servers': [标准字段dict]} 或 {'success': False, 'message': ...}
    """
    if not (text or '').strip():
        return {'success': False, 'message': '配置内容为空'}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return {'success': False, 'message': f'JSON 解析失败: {e}'}
    if not isinstance(data, dict):
        return {'success': False, 'message': '配置必须是 JSON 对象'}

    entries = None
    if isinstance(data.get('mcpServers'), dict):
        # Claude Desktop 导出格式
        entries = data['mcpServers']
    elif 'command' in data or 'url' in data:
        # 单个服务，名称自动推导
        base = None
        if data.get('command'):
            args = [str(data['command'])] + [str(a) for a in (data.get('args') or [])]
            base = args[-1].split('/')[-1].split('\\')[-1].split('@')[-1]
        elif data.get('url'):
            try:
                from urllib.parse import urlparse
                host = (urlparse(str(data['url'])).hostname or '')
                # mcp.context7.com -> mcp-context7（去掉TLD，点换中划线）
                base = host.rsplit('.', 1)[0].replace('.', '-') if host else None
            except Exception:
                base = None
        entries = {_sanitize_server_name(base): data}
    else:
        # 顶层服务映射：value 需为 dict 且像 server 配置
        entries = {k: v for k, v in data.items()
                   if isinstance(v, dict) and (v.get('command') or v.get('url'))}
        if not entries:
            return {'success': False, 'message': (
                '未识别的配置格式。支持：\n'
                '1. {"mcpServers": {"名称": {"command": ..., "args": [...], "env": {...}}}}（Claude Desktop/Cursor 导出）\n'
                '2. {"名称1": {"command": ...}, "名称2": {"url": ...}}\n'
                '3. {"command": ...} 或 {"url": ...}（单个服务）')}

    servers = []
    for name, v in entries.items():
        parsed = _parse_mcp_entry(_sanitize_server_name(name), v)
        if parsed:
            servers.append(parsed)

    if not servers:
        return {'success': False, 'message': '未解析到有效的 MCP server 配置（条目需包含 command 或 url）'}
    return {'success': True, 'servers': servers}


class _SessionEntry:
    """一个 MCP server 的会话条目（会话对象运行在后台事件循环中）"""

    def __init__(self):
        self.session = None            # mcp.ClientSession
        self.closed = None             # asyncio.Event，置位后 runner 退出并关闭连接
        self.dead = False              # 会话已失效

    @property
    def available(self):
        return self.session is not None and not self.dead


class McpClientManager:
    """MCP 客户端会话池（懒加载、失败重建、空闲回收）"""

    _instance = None
    _instance_lock = threading.Lock()

    # 会话空闲回收时间（秒）
    IDLE_TIMEOUT = 600
    # 回收检查间隔（秒）
    SWEEP_INTERVAL = 120

    def __init__(self):
        self._loop = None
        self._loop_started = threading.Event()
        self._sessions = {}            # server_id -> _SessionEntry
        self._sessions_lock = threading.Lock()
        self._last_used = {}           # server_id -> last_used timestamp
        self._create_locks = {}        # server_id -> threading.Lock（串行化会话创建，避免并发首建重复会话）
        self._create_locks_guard = threading.Lock()
        self._start_loop()
        t = threading.Thread(target=self._sweep_loop, daemon=True, name='mcp-client-sweeper')
        t.start()

    @classmethod
    def get_instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = McpClientManager()
            return cls._instance

    # ============ 事件循环管理 ============

    def _start_loop(self):
        t = threading.Thread(target=self._loop_main, daemon=True, name='mcp-client-loop')
        t.start()
        if not self._loop_started.wait(timeout=10):
            raise RuntimeError('MCP 后台事件循环启动失败')

    def _loop_main(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._loop_started.set()
        loop.run_forever()
        loop.close()

    # ============ 会话管理 ============

    def _create_lock_for(self, key):
        """获取指定 server 的创建锁（懒建）"""
        with self._create_locks_guard:
            lock = self._create_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._create_locks[key] = lock
            return lock

    def _get_session(self, server):
        """获取（或建立）server 的活动会话，线程安全。

        通过 per-server 创建锁 + 双重检查，避免并发首次调用时重复建会话
        （后建者覆盖先建者，先建者成为无人引用的泄漏会话/stdio子进程）。
        """
        key = server.id
        with self._sessions_lock:
            entry = self._sessions.get(key)
            if entry and entry.available:
                self._last_used[key] = time.time()
                return entry
        create_lock = self._create_lock_for(key)
        with create_lock:
            # 双重检查：可能在等锁期间被并发请求建好
            with self._sessions_lock:
                entry = self._sessions.get(key)
                if entry and entry.available:
                    self._last_used[key] = time.time()
                    return entry
            # 在调用方线程（有 Flask app context）预先解密凭证，
            # 后台事件循环线程没有 app context，不能在那里访问 current_app
            env = server.get_env() if server.transport_type == 'stdio' else None
            headers = server.get_headers() if server.transport_type != 'stdio' else None
            return self._create_session(server, env, headers)

    def _create_session(self, server, env=None, headers=None):
        """在后台事件循环中建立新会话，阻塞等待初始化完成。

        env/headers 由调用方线程解密后传入（不得在本协程内访问 ORM 加密字段，
        因为本协程运行在无 app context 的后台线程）。
        """
        sdk = _sdk()
        timeout = server.timeout_seconds or 60
        ready = concurrent.futures.Future()

        async def _runner():
            entry = _SessionEntry()
            entry.closed = asyncio.Event()
            try:
                if server.transport_type == 'stdio':
                    argv = _split_command(server.command or '')
                    if not argv:
                        raise ValueError('stdio 命令为空')
                    merged_env = {k: str(v) for k, v in {**os.environ, **(env or {})}.items()}
                    params = sdk['StdioServerParameters'](command=argv[0], args=argv[1:], env=merged_env)
                    cm = sdk['stdio_client'](params)
                elif server.transport_type == 'sse':
                    cm = sdk['sse_client'](url=server.url, headers=headers or None)
                elif server.transport_type == 'streamable_http':
                    cm = sdk['streamablehttp_client'](url=server.url, headers=headers or None)
                else:
                    raise ValueError(f'不支持的传输类型: {server.transport_type}')

                async with cm as transport:
                    if isinstance(transport, tuple):
                        read_stream, write_stream = transport[0], transport[1]
                    else:
                        read_stream, write_stream = transport
                    async with sdk['ClientSession'](read_stream, write_stream) as session:
                        await session.initialize()
                        entry.session = session
                        self._on_session_ready(server.id, entry, ready)
                        # 保持会话存活，直到被显式关闭或回收
                        await entry.closed.wait()
            except Exception as e:
                self._on_session_ready(server.id, None, ready, error=e)
            finally:
                entry.session = None
                entry.dead = True

        # 提交到后台循环
        future = asyncio.run_coroutine_threadsafe(_runner(), self._loop)

        try:
            # 等待 ready 信号（会话就绪/失败），而非 runner 协程完成（runner 会话存活期间永不结束）
            entry = ready.result(timeout=timeout + 5)
        except concurrent.futures.TimeoutError:
            # 尝试取消仍在运行的协程，避免超时后会话迟到登记造成泄漏
            future.cancel()
            raise TimeoutError(f'MCP server "{server.name}" 连接超时({timeout}s)')
        self._last_used[server.id] = time.time()
        return entry

    def _on_session_ready(self, server_id, entry, ready, error=None):
        """在循环线程回调：登记会话并唤醒等待者"""
        def _apply():
            with self._sessions_lock:
                if error is not None or entry is None:
                    self._sessions.pop(server_id, None)
                elif ready.done():
                    # 等待者已超时/被取消，迟到的会话无人引用：不登记并关闭
                    if entry.closed:
                        self._loop.call_soon_threadsafe(entry.closed.set)
                else:
                    self._sessions[server_id] = entry
            if not ready.done():
                if error is not None:
                    ready.set_exception(error)
                elif entry is None:
                    ready.set_exception(RuntimeError('MCP 会话建立失败'))
                else:
                    ready.set_result(entry)
        # 在事件循环线程中执行加锁登记，避免与回收线程竞争
        self._loop.call_soon_threadsafe(_apply)

    def _invalidate(self, server_id):
        """会话失效，下次调用时重建"""
        with self._sessions_lock:
            entry = self._sessions.pop(server_id, None)
            self._last_used.pop(server_id, None)
        if entry and entry.closed and self._loop:
            self._loop.call_soon_threadsafe(entry.closed.set)

    def close_session(self, server_id):
        """主动关闭指定 server 的会话"""
        self._invalidate(server_id)

    def shutdown(self):
        """关闭所有会话"""
        with self._sessions_lock:
            ids = list(self._sessions.keys())
            self._sessions.clear()
        for sid in ids:
            self.close_session(sid)

    def _sweep_loop(self):
        """定期回收空闲会话"""
        while True:
            time.sleep(self.SWEEP_INTERVAL)
            try:
                self._sweep_idle()
            except Exception as e:
                logger.warning(f'MCP会话回收异常: {e}')

    def _sweep_idle(self):
        """回收空闲会话"""
        now = time.time()
        stale = [sid for sid, ts in self._last_used.items() if now - ts > self.IDLE_TIMEOUT]
        for sid in stale:
            logger.info(f'MCP 会话空闲回收: server_id={sid}')
            self.close_session(sid)

    # ============ 同步调用接口 ============

    def _run(self, server, coro_factory, timeout=None):
        """在后台循环中执行会话操作，失败时失效会话"""
        timeout = timeout or server.timeout_seconds or 60
        entry = self._get_session(server)
        try:
            future = asyncio.run_coroutine_threadsafe(coro_factory(entry.session), self._loop)
            result = future.result(timeout=timeout + 5)
            # 调用完成保活，防止长调用期间被空闲回收误关
            self._last_used[server.id] = time.time()
            return result
        except Exception as e:
            # 会话可能已损坏，失效后下次重建
            self._invalidate(server.id)
            raise

    def list_tools(self, server) -> list:
        """列出 server 提供的工具（实时连接）"""
        result = self._run(server, lambda s: s.list_tools())
        tools = []
        for t in (result.tools or []):
            tools.append({
                'name': t.name,
                'description': t.description or '',
                'inputSchema': getattr(t, 'inputSchema', None) or {'type': 'object', 'properties': {}},
            })
        return tools

    def call_tool(self, server, tool_name: str, args: dict) -> dict:
        """调用 server 的指定工具（实时连接），返回可序列化结果"""
        def _call(s):
            return s.call_tool(tool_name, arguments=args or {})

        result = self._run(server, _call)
        return self._serialize_result(result)

    @staticmethod
    def _serialize_result(result) -> dict:
        """将 mcp SDK 的 CallToolResult 转为 dict"""
        output = {'is_error': bool(getattr(result, 'isError', False))}
        # 优先 structuredContent（MCP 2025-03-26+）
        structured = getattr(result, 'structuredContent', None)
        if structured is not None:
            output['structured'] = structured
        texts = []
        for item in (getattr(result, 'content', None) or []):
            item_type = getattr(item, 'type', '')
            if item_type == 'text':
                texts.append(getattr(item, 'text', ''))
            elif item_type == 'image':
                texts.append('[图片内容，已省略]')
            elif item_type == 'resource':
                texts.append(f"[资源: {getattr(getattr(item, 'resource', None), 'uri', '')}]")
        output['text'] = '\n'.join(texts) if texts else ''
        return output


class McpService:
    """MCP 工具注入与调用分发（供 ai_service / 路由调用）"""

    @staticmethod
    def prefixed_tool_name(server_name: str, tool_name: str) -> str:
        return f'{MCP_TOOL_PREFIX}{server_name}__{tool_name}'

    @staticmethod
    def parse_prefixed_name(name: str):
        """解析 mcp__{server}__{tool}，返回 (server_name, tool_name) 或 None"""
        if not name or not name.startswith(MCP_TOOL_PREFIX):
            return None
        parts = name.split('__')
        # ['mcp', server_name, tool...]，tool 名本身可能包含 __
        if len(parts) < 3:
            return None
        return parts[1], '__'.join(parts[2:])

    @staticmethod
    def get_agent_mcp_tools(agent) -> list:
        """获取 agent 被授予的 MCP 工具定义（OpenAI function 格式，读 tools_cache 不依赖实时连接）"""
        try:
            from app.models.mcp_server import McpServer
            ids = agent.get_mcp_server_ids() if agent else []
            if not ids:
                return []
            servers = McpServer.query.filter(McpServer.id.in_(ids), McpServer.is_active == True).all()
            tools = []
            for s in servers:
                for t in s.get_tools_cache():
                    schema = t.get('inputSchema')
                    if not isinstance(schema, dict):
                        schema = {'type': 'object', 'properties': {}}
                    desc = t.get('description') or ''
                    tools.append({
                        'type': 'function',
                        'function': {
                            'name': McpService.prefixed_tool_name(s.name, t.get('name', '')),
                            'description': f'[MCP工具，来源服务: {s.name}' + (f' - {s.description}] ' if s.description else '] ') + desc,
                            'parameters': schema,
                        },
                    })
            return tools
        except Exception:
            # 记录完整堆栈，避免真实 bug（如凭证解密失败）被伪装成「无工具」
            logger.exception('获取Agent MCP工具失败')
            return []

    @staticmethod
    def call_tool_by_prefixed_name(name: str, args: dict, agent_id: int = None) -> dict:
        """按 mcp__{server}__{tool} 名称调用工具（供 execute_tool_call 分发）。

        agent_id 不为 None 时进行授权复核：调用方 Agent 必须被授予该 server，
        防止模型幻觉/提示注入伪造 mcp__ 名称绕过授予关系。
        """
        parsed = McpService.parse_prefixed_name(name)
        if not parsed:
            return {'error': f'无效的MCP工具名: {name}'}
        server_name, tool_name = parsed

        from app.models.mcp_server import McpServer
        server = McpServer.query.filter_by(name=server_name, is_active=True).first()
        if not server:
            return {'error': f'MCP server "{server_name}" 不存在或已禁用'}

        # 授权复核
        if agent_id is not None:
            from app.models.ai_agent import AiAgent
            agent = AiAgent.query.get(agent_id)
            if not agent or server.id not in (agent.get_mcp_server_ids() or []):
                logger.warning(f'MCP工具授权复核失败: agent_id={agent_id}, tool={name}')
                return {'error': f'当前Agent未被授予MCP server "{server_name}"，无权调用其工具'}

        try:
            manager = McpClientManager.get_instance()
            result = manager.call_tool(server, tool_name, args or {})
            payload = {
                'mcp_server': server.name,
                'mcp_tool': tool_name,
                'result': result.get('structured') if result.get('structured') is not None else result.get('text', ''),
            }
            if result.get('is_error'):
                payload['error'] = result.get('text', '') or 'MCP 工具执行返回错误'
            return payload
        except Exception as e:
            logger.warning(f'MCP工具调用失败: {name}({args}): {e}')
            return {'mcp_server': server_name, 'mcp_tool': tool_name, 'error': f'MCP 工具调用失败: {e}'}

    @staticmethod
    def test_connection(server) -> dict:
        """测试连接并列出工具（不写库）"""
        try:
            manager = McpClientManager.get_instance()
            tools = manager.list_tools(server)
            return {'success': True, 'tools': tools, 'tools_count': len(tools)}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @staticmethod
    def refresh_tools_cache(server) -> dict:
        """连接并刷新工具清单缓存（需在 app context 中调用并 commit）"""
        from app import db
        try:
            manager = McpClientManager.get_instance()
            tools = manager.list_tools(server)
            server.set_tools_cache(tools)
            server.last_error = None
            db.session.commit()
            return {'success': True, 'tools': tools, 'tools_count': len(tools)}
        except Exception as e:
            server.last_error = str(e)[:1000]
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            return {'success': False, 'message': str(e)}
