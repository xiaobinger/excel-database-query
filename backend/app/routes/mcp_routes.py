import json
import logging
from flask import Blueprint, request, jsonify
from app import db
from app.models.mcp_server import McpServer
from app.utils.auth import login_required, admin_required, permission_required, get_current_user

logger = logging.getLogger(__name__)
mcp_bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')

VALID_TRANSPORTS = ('stdio', 'sse', 'streamable_http')


def _validate_payload(data, partial=False):
    """校验请求参数，返回 (server字段dict, 错误信息)"""
    fields = {}
    if not partial or 'name' in data:
        name = (data.get('name') or '').strip()
        from app.services.mcp_service import SERVER_NAME_PATTERN
        if not SERVER_NAME_PATTERN.match(name):
            return None, '名称必须以字母开头，仅含字母、数字、下划线、中划线，且不能含连续下划线（用于工具名前缀 mcp__{名称}__{工具名}）'
        fields['name'] = name
    if not partial or 'transport_type' in data:
        tt = data.get('transport_type', 'stdio')
        if tt not in VALID_TRANSPORTS:
            return None, f'传输类型必须是 {"、".join(VALID_TRANSPORTS)} 之一'
        fields['transport_type'] = tt
    if not partial or 'command' in data:
        fields['command'] = (data.get('command') or '').strip() or None
    if not partial or 'url' in data:
        fields['url'] = (data.get('url') or '').strip() or None
    if 'description' in data:
        fields['description'] = data.get('description') or ''
    if 'timeout_seconds' in data:
        try:
            fields['timeout_seconds'] = max(5, min(int(data.get('timeout_seconds') or 60), 600))
        except (TypeError, ValueError):
            fields['timeout_seconds'] = 60
    if 'is_active' in data:
        fields['is_active'] = bool(data.get('is_active'))

    # 按传输类型校验必填项
    tt = fields.get('transport_type')
    if tt == 'stdio' and fields.get('command') is None and not partial:
        return None, 'stdio 类型必须填写启动命令'
    if tt in ('sse', 'streamable_http') and fields.get('url') is None and not partial:
        return None, '远程服务类型必须填写 URL'

    # env/headers：JSON对象，仅在提供时更新
    for key, setter in (('env', 'set_env'), ('headers', 'set_headers')):
        if key in data:
            raw = data.get(key)
            if raw in (None, ''):
                fields[setter] = (setter, None)
            else:
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        return None, f'{key} 必须是合法的JSON对象'
                if not isinstance(raw, dict):
                    return None, f'{key} 必须是JSON对象（键值均为字符串）'
                raw = {str(k): str(v) for k, v in raw.items()}
                fields[setter] = (setter, raw)
    return fields, None


def _apply_fields(server, fields):
    """将校验后的字段应用到 server 对象"""
    setters = fields.pop('set_env', None)
    headers_setter = fields.pop('set_headers', None)
    for k, v in fields.items():
        setattr(server, k, v)
    if setters:
        server.set_env(setters[1])
    if headers_setter:
        server.set_headers(headers_setter[1])


@mcp_bp.route('', methods=['GET'])
@login_required
def get_mcp_servers():
    """获取MCP Server列表（登录即可查看，供Agent编辑选择；敏感信息脱敏）"""
    servers = McpServer.query.order_by(McpServer.created_at.desc()).all()
    return jsonify({'success': True, 'data': [s.to_dict() for s in servers]})


@mcp_bp.route('', methods=['POST'])
@permission_required('system')
def create_mcp_server():
    """创建MCP Server"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    fields, err = _validate_payload(data)
    if err:
        return jsonify({'success': False, 'message': err}), 400

    if McpServer.query.filter_by(name=fields['name']).first():
        return jsonify({'success': False, 'message': f'名称 "{fields["name"]}" 已存在'}), 400

    try:
        current_user = get_current_user()
        server = McpServer(created_by=current_user.id if current_user else None)
        _apply_fields(server, dict(fields))
        db.session.add(server)
        db.session.commit()

        # 创建后自动尝试刷新工具清单缓存（best-effort：失败不影响创建，
        # 错误记入 last_error 提示管理员稍后手动刷新）
        from app.services.mcp_service import McpService
        try:
            McpService.refresh_tools_cache(server)
        except Exception as e:
            logger.warning(f'创建后自动刷新工具缓存失败(server={server.name}): {e}')

        return jsonify({'success': True, 'data': server.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'创建MCP Server失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@mcp_bp.route('/<int:server_id>', methods=['PUT'])
@permission_required('system')
def update_mcp_server(server_id):
    """更新MCP Server"""
    server = McpServer.query.get(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'MCP Server不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    fields, err = _validate_payload(data, partial=True)
    if err:
        return jsonify({'success': False, 'message': err}), 400

    if 'name' in fields and fields['name'] != server.name:
        if McpServer.query.filter(McpServer.name == fields['name'], McpServer.id != server_id).first():
            return jsonify({'success': False, 'message': f'名称 "{fields["name"]}" 已存在'}), 400

    try:
        # 配置变更后关闭旧会话，下次调用按新配置重建
        from app.services.mcp_service import McpClientManager
        McpClientManager.get_instance().close_session(server_id)
        _apply_fields(server, fields)
        db.session.commit()
        return jsonify({'success': True, 'data': server.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f'更新MCP Server失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


def _delete_server_with_cleanup(server):
    """删除单个MCP Server及其关联（关会话 + 从所有Agent的授予列表移除 + 删记录）。
    单条与批量删除共用，保证清理逻辑一致。
    """
    from app.services.mcp_service import McpClientManager
    from app.models.ai_agent import AiAgent
    # 关闭会话（含 stdio 子进程）
    McpClientManager.get_instance().close_session(server.id)
    # 从所有Agent的mcp_server_ids中移除，避免脏引用
    for a in AiAgent.query.all():
        ids = a.get_mcp_server_ids()
        if server.id in ids:
            ids.remove(server.id)
            a.set_mcp_server_ids(ids)
    db.session.delete(server)


@mcp_bp.route('/import', methods=['POST'])
@permission_required('system')
def import_mcp_servers():
    """JSON 批量导入 MCP Server。

    body: {config: "<JSON文本>", dry_run: bool}
    - dry_run=True: 仅解析预览，返回解析结果及名称冲突标记，不落库
    - dry_run=False: 执行导入，名称冲突的条目跳过
    兼容 Claude Desktop / Cursor / VS Code 的 mcpServers JSON 格式。
    """
    data = request.get_json()
    if not data or not data.get('config'):
        return jsonify({'success': False, 'message': '请提供JSON配置内容'}), 400

    from app.services.mcp_service import parse_mcp_config
    parsed = parse_mcp_config(data.get('config', ''))
    if not parsed.get('success'):
        return jsonify({'success': False, 'message': parsed.get('message', '解析失败')}), 400

    servers = parsed['servers']
    existing_names = {row.name for row in McpServer.query.with_entities(McpServer.name).all()}
    dry_run = bool(data.get('dry_run', True))

    current_user = get_current_user()
    result = []
    imported_count = 0
    try:
        for s in servers:
            conflict = s['name'] in existing_names
            item = {
                'name': s['name'],
                'transport_type': s['transport_type'],
                'command': s['command'],
                'url': s['url'],
                'env_keys': list(s['env'].keys()),
                'header_keys': list(s['headers'].keys()),
                'description': s['description'],
                'conflict': conflict,
            }
            if dry_run:
                item['imported'] = False
            elif conflict:
                item['imported'] = False
                item['reason'] = '名称已存在，已跳过'
            else:
                server = McpServer(
                    name=s['name'],
                    description=s['description'] or f'JSON 导入的 MCP 服务',
                    transport_type=s['transport_type'],
                    command=s['command'],
                    url=s['url'],
                    created_by=current_user.id if current_user else None,
                )
                if s['env']:
                    server.set_env(s['env'])
                if s['headers']:
                    server.set_headers(s['headers'])
                db.session.add(server)
                existing_names.add(s['name'])
                item['imported'] = True
                imported_count += 1
            result.append(item)

        if not dry_run:
            db.session.commit()
            return jsonify({
                'success': True,
                'data': result,
                'imported_count': imported_count,
                'message': f'成功导入 {imported_count} 个MCP服务'
                           + (f'，跳过 {len(servers) - imported_count} 个（名称冲突）' if imported_count < len(servers) else '')
                           + '。导入后请点击「刷新工具」获取工具清单',
            })
        return jsonify({'success': True, 'data': result, 'imported_count': 0})
    except Exception as e:
        db.session.rollback()
        logger.error(f'JSON导入MCP Server失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@mcp_bp.route('/marketplace', methods=['GET'])
@permission_required('system')
def get_mcp_marketplace():
    """获取MCP市场目录（支持外部市场拉取），自动标记已导入的服务

    查询参数：
    - source: smithery | official | static | all（默认all）
    """
    from app.services.mcp_marketplace import get_marketplace
    # 查询已导入的服务名称，用于标记
    existing_names = {row.name for row in McpServer.query.with_entities(McpServer.name).all()}
    source = request.args.get('source', 'all')
    if source not in ('smithery', 'official', 'static', 'all'):
        source = 'all'
    source = None if source == 'all' else source
    return jsonify({'success': True, 'data': get_marketplace(source=source, imported_names=existing_names)})


@mcp_bp.route('/marketplace/refresh', methods=['POST'])
@permission_required('system')
def refresh_mcp_marketplace():
    """强制刷新MCP市场目录（清除缓存并重新拉取外部市场）

    查询参数：
    - source: smithery | official | all（默认all）
    """
    from app.services.mcp_marketplace import get_marketplace, refresh_marketplace
    refresh_marketplace()
    existing_names = {row.name for row in McpServer.query.with_entities(McpServer.name).all()}
    source = request.args.get('source', 'all')
    if source not in ('smithery', 'official', 'all'):
        source = 'all'
    source = None if source == 'all' else source
    data = get_marketplace(source=source, imported_names=existing_names, force_refresh=True)
    return jsonify({'success': True, 'data': data, 'message': '市场已刷新'})


@mcp_bp.route('/marketplace/sources', methods=['GET'])
@permission_required('system')
def get_mcp_marketplace_sources():
    """获取各市场源状态（可用性/条目数/缓存状态）"""
    from app.services.mcp_marketplace import get_source_status
    return jsonify({'success': True, 'data': get_source_status()})


@mcp_bp.route('/<int:server_id>', methods=['DELETE'])
@permission_required('system')
def delete_mcp_server(server_id):
    """删除MCP Server（同时从Agent的授予列表中移除）"""
    server = McpServer.query.get(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'MCP Server不存在'}), 404

    try:
        _delete_server_with_cleanup(server)
        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'删除MCP Server失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@mcp_bp.route('/batch-delete', methods=['POST'])
@permission_required('system')
def batch_delete_mcp_servers():
    """批量删除MCP Server（与单条删除同样关会话+清Agent引用）"""
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400
    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400

    deleted = 0
    for sid in ids:
        server = McpServer.query.get(sid)
        if server:
            _delete_server_with_cleanup(server)
            deleted += 1
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted}个MCP Server', 'deleted_count': deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@mcp_bp.route('/<int:server_id>/test', methods=['POST'])
@permission_required('system')
def test_mcp_server(server_id):
    """测试连接并列出工具"""
    server = McpServer.query.get(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'MCP Server不存在'}), 404

    from app.services.mcp_service import McpService
    result = McpService.test_connection(server)
    server.last_error = None if result['success'] else result.get('message', '')[:1000]
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify(result)


@mcp_bp.route('/<int:server_id>/refresh-tools', methods=['POST'])
@permission_required('system')
def refresh_mcp_tools(server_id):
    """连接并刷新工具清单缓存"""
    server = McpServer.query.get(server_id)
    if not server:
        return jsonify({'success': False, 'message': 'MCP Server不存在'}), 404

    from app.services.mcp_service import McpService
    result = McpService.refresh_tools_cache(server)
    return jsonify(result)
