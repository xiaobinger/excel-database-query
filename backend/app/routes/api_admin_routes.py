"""开放API管理接口（仅系统权限）"""
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from sqlalchemy import func

from app import db
from app.models.api_key import ApiKey
from app.models.api_call_log import ApiCallLog
from app.utils.auth import permission_required, get_current_user

logger = logging.getLogger(__name__)
open_api_admin_bp = Blueprint('open_api_admin', __name__, url_prefix='/api/open-api')


# ============ 全局设置 ============

@open_api_admin_bp.route('/settings', methods=['GET'])
@permission_required('system')
def get_open_api_settings():
    from app.services.open_api_service import get_settings
    return jsonify({'success': True, 'data': get_settings()})


@open_api_admin_bp.route('/settings', methods=['PUT'])
@permission_required('system')
def save_open_api_settings():
    from app.services.open_api_service import save_settings
    data = request.get_json() or {}
    try:
        result = save_settings(bool(data.get('enabled')), data.get('endpoint_mode', 'both'))
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400


# ============ ApiKey 管理 ============

def _validate_key_payload(data, partial=False):
    """校验并规范化 ApiKey 字段"""
    fields = {}
    if not partial or 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return None, '名称不能为空'
        fields['name'] = name[:100]
    if 'model_mapping' in data:
        mapping = data.get('model_mapping')
        if mapping in (None, ''):
            fields['model_mapping'] = []
        else:
            if isinstance(mapping, str):
                import json
                try:
                    mapping = json.loads(mapping)
                except json.JSONDecodeError:
                    return None, 'model_mapping 必须是JSON数组'
            if not isinstance(mapping, list):
                return None, 'model_mapping 必须是数组'
            cleaned = []
            from app.models.ai_config import AiConfig
            valid_ids = {c.id for c in AiConfig.query.filter_by(is_active=True).all()}
            for item in mapping:
                if not isinstance(item, dict):
                    return None, 'model_mapping 每项必须是 {external, config_id}'
                ext = str(item.get('external') or '').strip()
                try:
                    cid = int(item.get('config_id'))
                except (TypeError, ValueError):
                    return None, 'model_mapping 中 config_id 无效'
                if not ext or ext.lower() == 'auto':
                    return None, '外部模型名不能为空且不能是 auto'
                if ext != str(ext).strip() or ' ' in ext:
                    return None, f'外部模型名不能含空格: {ext}'
                if cid not in valid_ids:
                    return None, f'映射的内部模型不存在或已禁用: {ext}'
                cleaned.append({'external': ext, 'config_id': cid})
            fields['model_mapping'] = cleaned
    if 'ip_whitelist' in data:
        ips = data.get('ip_whitelist')
        if ips in (None, ''):
            fields['ip_whitelist'] = []
        else:
            if isinstance(ips, str):
                # 按行/逗号分隔解析
                ips = [x.strip() for x in ips.replace(',', '\n').split('\n') if x.strip()]
            if not isinstance(ips, list):
                return None, 'ip_whitelist 必须是数组'
            import ipaddress
            for entry in ips:
                try:
                    if '/' in str(entry):
                        ipaddress.ip_network(str(entry), strict=False)
                    else:
                        ipaddress.ip_address(str(entry))
                except ValueError:
                    return None, f'IP白名单条目无效: {entry}'
            fields['ip_whitelist'] = [str(i) for i in ips]
    if 'is_active' in data:
        fields['is_active'] = bool(data.get('is_active'))
    return fields, None


@open_api_admin_bp.route('/keys', methods=['GET'])
@permission_required('system')
def list_keys():
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return jsonify({'success': True, 'data': [k.to_dict() for k in keys]})


@open_api_admin_bp.route('/keys', methods=['POST'])
@permission_required('system')
def create_key():
    data = request.get_json() or {}
    fields, err = _validate_key_payload(data)
    if err:
        return jsonify({'success': False, 'message': err}), 400
    try:
        current_user = get_current_user()
        key = ApiKey(created_by=current_user.id if current_user else None)
        key.name = fields['name']
        key.set_model_mapping(fields.get('model_mapping', []))
        key.set_ip_whitelist(fields.get('ip_whitelist', []))
        key.is_active = fields.get('is_active', True)
        key.set_api_key(ApiKey.generate_key_string())
        db.session.add(key)
        db.session.commit()
        return jsonify({'success': True, 'data': key.to_dict(include_key=True)}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'创建ApiKey失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@open_api_admin_bp.route('/keys/<int:key_id>', methods=['PUT'])
@permission_required('system')
def update_key(key_id):
    key = ApiKey.query.get(key_id)
    if not key:
        return jsonify({'success': False, 'message': 'ApiKey不存在'}), 404
    data = request.get_json() or {}
    fields, err = _validate_key_payload(data, partial=True)
    if err:
        return jsonify({'success': False, 'message': err}), 400
    try:
        if 'name' in fields:
            key.name = fields['name']
        if 'model_mapping' in fields:
            key.set_model_mapping(fields['model_mapping'])
        if 'ip_whitelist' in fields:
            key.set_ip_whitelist(fields['ip_whitelist'])
        if 'is_active' in fields:
            key.is_active = fields['is_active']
        db.session.commit()
        return jsonify({'success': True, 'data': key.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@open_api_admin_bp.route('/keys/<int:key_id>', methods=['DELETE'])
@permission_required('system')
def delete_key(key_id):
    key = ApiKey.query.get(key_id)
    if not key:
        return jsonify({'success': False, 'message': 'ApiKey不存在'}), 404
    try:
        # 保留调用记录（历史快照），仅删key本身
        db.session.delete(key)
        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@open_api_admin_bp.route('/keys/<int:key_id>/regenerate', methods=['POST'])
@permission_required('system')
def regenerate_key(key_id):
    """重新生成密钥（旧密钥立即失效）"""
    key = ApiKey.query.get(key_id)
    if not key:
        return jsonify({'success': False, 'message': 'ApiKey不存在'}), 404
    try:
        key.set_api_key(ApiKey.generate_key_string())
        db.session.commit()
        return jsonify({'success': True, 'data': key.to_dict(include_key=True)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@open_api_admin_bp.route('/keys/<int:key_id>/reveal', methods=['POST'])
@permission_required('system')
def reveal_key(key_id):
    """查看密钥明文（仅系统权限）"""
    key = ApiKey.query.get(key_id)
    if not key:
        return jsonify({'success': False, 'message': 'ApiKey不存在'}), 404
    return jsonify({'success': True, 'data': {'api_key': key.get_api_key()}})


@open_api_admin_bp.route('/keys/<int:key_id>/test', methods=['POST'])
@permission_required('system')
def test_key(key_id):
    """测试key：校验配置有效性并解析模型映射（不发实际AI请求）"""
    key = ApiKey.query.get(key_id)
    if not key:
        return jsonify({'success': False, 'message': 'ApiKey不存在'}), 404
    from app.models.ai_config import AiConfig
    mapping = key.get_model_mapping()
    details = []
    ok = True
    for m in mapping:
        cfg = AiConfig.query.filter_by(id=m.get('config_id'), is_active=True).first()
        valid = cfg is not None
        ok = ok and valid
        details.append({
            'external': m.get('external'),
            'config_id': m.get('config_id'),
            'valid': valid,
            'model_name': cfg.model_name if cfg else '',
        })
    ordered = True
    try:
        from app.services.ai_service import AiService
        if not AiService.get_ordered_configs():
            ordered = False
    except Exception:
        ordered = False
    return jsonify({'success': True, 'data': {
        'key_active': key.is_active,
        'mapping': details,
        'strategy_available': ordered,
        'ip_whitelist': key.get_ip_whitelist(),
        'ok': ok and ordered and key.is_active,
    }})


# ============ 调用记录与统计 ============

@open_api_admin_bp.route('/logs', methods=['GET'])
@permission_required('system')
def list_logs():
    """调用记录列表（分页+筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    query = ApiCallLog.query
    api_key_id = request.args.get('api_key_id', type=int)
    if api_key_id:
        query = query.filter_by(api_key_id=api_key_id)
    model = request.args.get('model', '').strip()
    if model:
        query = query.filter(ApiCallLog.model_used.like(f'%{model}%'))
    status = request.args.get('status', '').strip()
    if status == 'success':
        query = query.filter_by(is_success=True)
    elif status == 'failed':
        query = query.filter_by(is_success=False)
    start_time = request.args.get('start_time', '').strip()
    if start_time:
        try:
            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)  # DB存的是UTC naive时间
            query = query.filter(ApiCallLog.created_at >= dt)
        except (ValueError, TypeError):
            pass
    end_time = request.args.get('end_time', '').strip()
    if end_time:
        try:
            dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            query = query.filter(ApiCallLog.created_at <= dt)
        except (ValueError, TypeError):
            pass

    total = query.count()
    logs = query.order_by(ApiCallLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({'success': True, 'data': [l.to_dict() for l in logs], 'total': total,
                    'page': page, 'per_page': per_page})


@open_api_admin_bp.route('/logs/<int:log_id>', methods=['GET'])
@permission_required('system')
def get_log_detail(log_id):
    log = ApiCallLog.query.get(log_id)
    if not log:
        return jsonify({'success': False, 'message': '记录不存在'}), 404
    return jsonify({'success': True, 'data': log.to_dict(include_content=True)})


@open_api_admin_bp.route('/stats', methods=['GET'])
@permission_required('system')
def get_stats():
    """汇总统计：总量/成功率/token/缓存/耗时 + 按模型与按key分组"""
    base = ApiCallLog.query
    total = base.count()
    if total == 0:
        return jsonify({'success': True, 'data': {
            'total': 0, 'success_rate': 0, 'total_tokens': 0, 'cache_tokens': 0,
            'avg_elapsed': 0, 'by_model': [], 'by_key': [],
        }})
    success_count = base.filter_by(is_success=True).count()
    agg = db.session.query(
        func.coalesce(func.sum(ApiCallLog.tokens_used), 0),
        func.coalesce(func.sum(ApiCallLog.cache_creation_tokens), 0),
        func.coalesce(func.sum(ApiCallLog.cache_read_tokens), 0),
        func.coalesce(func.avg(ApiCallLog.elapsed), 0),
    ).filter(ApiCallLog.is_success == True).first()

    by_model = db.session.query(
        ApiCallLog.model_used,
        func.count(ApiCallLog.id),
        func.coalesce(func.sum(ApiCallLog.tokens_used), 0),
    ).group_by(ApiCallLog.model_used).all()

    by_key = db.session.query(
        ApiCallLog.api_key_id,
        ApiCallLog.api_key_name,
        func.count(ApiCallLog.id),
        func.coalesce(func.sum(ApiCallLog.tokens_used), 0),
    ).group_by(ApiCallLog.api_key_id, ApiCallLog.api_key_name).all()

    return jsonify({'success': True, 'data': {
        'total': total,
        'success_count': success_count,
        'success_rate': round(success_count / total * 100, 1),
        'total_tokens': int(agg[0] or 0),
        'cache_creation_tokens': int(agg[1] or 0),
        'cache_read_tokens': int(agg[2] or 0),
        'avg_elapsed': round(float(agg[3] or 0), 2),
        'by_model': [{'model': m or '(未知)', 'count': c, 'tokens': int(t)} for m, c, t in by_model],
        'by_key': [{'api_key_id': kid, 'name': n or f'#{kid}', 'count': c, 'tokens': int(t)} for kid, n, c, t in by_key],
    }})
