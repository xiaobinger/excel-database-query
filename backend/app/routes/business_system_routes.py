import json
import hashlib
import time
import hmac
import requests as http_requests
from flask import Blueprint, request, jsonify
from app import db
from app.models.business_system import BusinessSystem
from app.models.user import User
from app.utils.auth import login_required, admin_required, get_current_user

business_bp = Blueprint('business', __name__, url_prefix='/api/business')


@business_bp.route('/systems', methods=['GET'])
@login_required
def list_systems():
    """获取业务系统列表"""
    systems = BusinessSystem.query.filter_by(is_active=True).order_by(BusinessSystem.sort_order, BusinessSystem.id).all()
    return jsonify({'success': True, 'data': [s.to_dict() for s in systems]})


@business_bp.route('/systems/all', methods=['GET'])
@admin_required
def list_all_systems():
    """管理员获取所有业务系统（含停用）"""
    systems = BusinessSystem.query.order_by(BusinessSystem.sort_order, BusinessSystem.id).all()
    return jsonify({'success': True, 'data': [s.to_dict() for s in systems]})


@business_bp.route('/systems', methods=['POST'])
@admin_required
def create_system():
    """创建业务系统"""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('website_url'):
        return jsonify({'success': False, 'message': '名称和网址为必填项'}), 400

    system = BusinessSystem(
        name=data['name'],
        description=data.get('description', ''),
        logo_url=data.get('logo_url', ''),
        website_url=data['website_url'],
        category=data.get('category', ''),
        sort_order=data.get('sort_order', 0),
        is_active=data.get('is_active', True),
        sso_enabled=data.get('sso_enabled', False),
        sso_url=data.get('sso_url', ''),
        sso_method=data.get('sso_method', 'POST'),
        sso_phone_field=data.get('sso_phone_field', 'phone'),
        sso_token_field=data.get('sso_token_field', 'token'),
        sso_response_token_key=data.get('sso_response_token_key', 'token'),
        sso_token_pass_key=data.get('sso_token_pass_key', 'token'),
    )
    if 'sso_extra_params' in data:
        system.set_extra_params(data['sso_extra_params'])
    if data.get('sso_token_key'):
        system.set_sso_token_key(data['sso_token_key'])

    db.session.add(system)
    db.session.commit()
    return jsonify({'success': True, 'data': system.to_dict()})


@business_bp.route('/systems/<int:system_id>', methods=['PUT'])
@admin_required
def update_system(system_id):
    """更新业务系统"""
    system = BusinessSystem.query.get(system_id)
    if not system:
        return jsonify({'success': False, 'message': '系统不存在'}), 404

    data = request.get_json()
    simple_fields = ['name', 'description', 'logo_url', 'website_url', 'category',
                     'sort_order', 'is_active', 'sso_enabled', 'sso_url', 'sso_method',
                     'sso_phone_field', 'sso_token_field', 'sso_response_token_key', 'sso_token_pass_key']
    for key in simple_fields:
        if key in data:
            setattr(system, key, data[key])
    if 'sso_extra_params' in data:
        system.set_extra_params(data['sso_extra_params'])
    if 'sso_token_key' in data and data['sso_token_key']:
        system.set_sso_token_key(data['sso_token_key'])

    db.session.commit()
    return jsonify({'success': True, 'data': system.to_dict()})


@business_bp.route('/systems/<int:system_id>', methods=['DELETE'])
@admin_required
def delete_system(system_id):
    """删除业务系统"""
    system = BusinessSystem.query.get(system_id)
    if not system:
        return jsonify({'success': False, 'message': '系统不存在'}), 404
    db.session.delete(system)
    db.session.commit()
    return jsonify({'success': True})


@business_bp.route('/systems/<int:system_id>/sso', methods=['POST'])
@login_required
def generate_sso_url(system_id):
    """生成SSO登录URL并代理调用SSO接口"""
    system = BusinessSystem.query.get(system_id)
    if not system:
        return jsonify({'success': False, 'message': '系统不存在'}), 404
    if not system.sso_enabled:
        return jsonify({'success': False, 'message': '该系统未启用SSO'}), 400

    user = get_current_user()
    # 优先使用用户的phone字段，其次使用用户名
    phone = getattr(user, 'phone', None) or user.username or ''

    # 生成token
    timestamp = str(int(time.time()))
    token_key = system.get_sso_token_key() if system.sso_token_key else ''

    if token_key:
        # HMAC签名
        sign_str = f'{phone}{timestamp}'
        token = hmac.new(token_key.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    else:
        token = ''

    # 构建参数
    params = {}
    params[system.sso_phone_field] = phone
    if token:
        params[system.sso_token_field] = token
    params['timestamp'] = timestamp

    # 合并额外参数
    extra = system.get_extra_params()
    params.update(extra)

    # 构建URL
    sso_url = system.sso_url or system.website_url

    if system.sso_method == 'GET':
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        redirect_url = f'{sso_url}?{query}'
        return jsonify({'success': True, 'redirect_url': redirect_url, 'method': 'GET'})
    else:
        # POST方式：后端代理调用SSO登录接口，提取token后返回给前端
        try:
            sso_res = http_requests.post(sso_url, json=params, timeout=10, allow_redirects=False)
        except Exception as e:
            return jsonify({'success': False, 'message': f'SSO接口调用失败: {str(e)}'}), 500

        # 检查是否有302重定向（有些SSO系统登录后直接重定向）
        if sso_res.status_code in (301, 302, 303, 307, 308):
            redirect_url = sso_res.headers.get('Location', system.website_url)
            return jsonify({'success': True, 'redirect_url': redirect_url, 'method': 'GET'})

        # 尝试从响应中提取token
        sso_token = None
        try:
            resp_data = sso_res.json()
            # 按配置的路径提取token（支持 data.token 格式）
            token_path = (system.sso_response_token_key or 'token').split('.')
            current = resp_data
            for key in token_path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    current = None
                    break
            sso_token = str(current) if current is not None else None
        except:
            pass

        # 构建跳转URL（带token参数，作为localStorage写入失败时的回退）
        website_url = system.website_url
        website_url_with_token = website_url
        if sso_token:
            pass_key = system.sso_token_pass_key or 'token'
            separator = '&' if '?' in website_url else '?'
            website_url_with_token = f'{website_url}{separator}{pass_key}={sso_token}'

        return jsonify({
            'success': True,
            'method': 'POST',
            'sso_token': sso_token,
            'token_pass_key': system.sso_token_pass_key or 'token',
            'website_url': website_url,
            'website_url_with_token': website_url_with_token
        })


@business_bp.route('/categories', methods=['GET'])
@login_required
def get_categories():
    """获取系统分类列表"""
    categories = db.session.query(BusinessSystem.category).filter(
        BusinessSystem.is_active == True,
        BusinessSystem.category.isnot(None),
        BusinessSystem.category != ''
    ).distinct().all()
    return jsonify({'success': True, 'data': [c[0] for c in categories if c[0]]})
