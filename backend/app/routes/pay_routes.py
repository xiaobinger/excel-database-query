"""代付提现路由

- 渠道配置 CRUD（系统配置-代付配置 tab）
- 执行代付/查询（业务中心-代付提现页面，上传 Excel）
"""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.pay_config import PayConfig
from app.utils.auth import login_required, permission_required
import app.services.pay_service as pay_service

pay_bp = Blueprint('pay', __name__, url_prefix='/api/pay')

# 渠道元数据（前端下拉用）
CHANNELS = [
    {'channel': 'helipay', 'name': '合利宝', 'interface_types': ['代付'], 'real_time': False, 'execute_types': []},
    {'channel': 'dianyin', 'name': '电银', 'interface_types': ['代付', '查询'], 'real_time': False, 'execute_types': []},
    {'channel': 'lepass', 'name': '乐商通PLUS', 'interface_types': ['代付', '查询'], 'real_time': True, 'execute_types': []},
    {'channel': 'kls', 'name': '快乐刷', 'interface_types': ['代付', '查询'], 'real_time': True,
     'execute_types': ['创建代付', '查询代付', '发起提现']},
]


@pay_bp.route('/channels', methods=['GET'])
@login_required
def channels():
    """渠道元数据（下拉选项）"""
    return jsonify({'success': True, 'data': CHANNELS})


# ---------------------------------------------------------------------------
# 渠道配置 CRUD
# ---------------------------------------------------------------------------

@pay_bp.route('/configs', methods=['GET'])
@login_required
def list_configs():
    items = PayConfig.query.order_by(PayConfig.sort_order, PayConfig.id).all()
    return jsonify({'success': True, 'data': [c.to_dict() for c in items]})


@pay_bp.route('/configs/<int:config_id>', methods=['GET'])
@login_required
def get_config(config_id):
    cfg = PayConfig.query.get_or_404(config_id)
    return jsonify({'success': True, 'data': cfg.to_dict()})


@pay_bp.route('/configs', methods=['POST'])
@login_required
@permission_required('system_config')
def create_config():
    data = request.get_json() or {}
    channel = (data.get('channel') or '').strip()
    if not channel:
        return jsonify({'success': False, 'message': '渠道标识不能为空'}), 400
    if PayConfig.query.filter_by(channel=channel).first():
        return jsonify({'success': False, 'message': f'渠道 {channel} 已存在'}), 400
    cfg = PayConfig(channel=channel, name=data.get('name') or channel,
                    description=data.get('description'), is_active=data.get('is_active', True),
                    sort_order=data.get('sort_order', 0))
    _apply_fields(cfg, data)
    db.session.add(cfg)
    db.session.commit()
    return jsonify({'success': True, 'data': cfg.to_dict(), 'message': '创建成功'}), 201


@pay_bp.route('/configs/<int:config_id>', methods=['PUT'])
@login_required
@permission_required('system_config')
def update_config(config_id):
    cfg = PayConfig.query.get_or_404(config_id)
    data = request.get_json() or {}
    _apply_fields(cfg, data)
    db.session.commit()
    return jsonify({'success': True, 'data': cfg.to_dict(), 'message': '更新成功'})


@pay_bp.route('/configs/<int:config_id>', methods=['DELETE'])
@login_required
@permission_required('system_config')
def delete_config(config_id):
    cfg = PayConfig.query.get_or_404(config_id)
    db.session.delete(cfg)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


def _apply_fields(cfg, data):
    if 'name' in data:
        cfg.name = data['name']
    if 'description' in data:
        cfg.description = data['description']
    if 'is_active' in data:
        cfg.is_active = bool(data['is_active'])
    if 'sort_order' in data:
        cfg.sort_order = data['sort_order'] or 0
    if 'online_bank_type' in data:
        cfg.online_bank_type = data['online_bank_type']
    if 'bank_code' in data:
        cfg.bank_code = data['bank_code']
    if 'transfer_mode' in data:
        cfg.transfer_mode = data['transfer_mode']
    if 'busi_type' in data:
        cfg.busi_type = data['busi_type']
    if 'channel_code' in data:
        cfg.channel_code = data['channel_code']
    if 'pro_config' in data:
        cfg.set_pro_config(data['pro_config'])
    if 'test_config' in data:
        cfg.set_test_config(data['test_config'])


# ---------------------------------------------------------------------------
# 执行代付/查询
# ---------------------------------------------------------------------------

@pay_bp.route('/execute', methods=['POST'])
@login_required
@permission_required('pay_withdraw')
def execute():
    """上传 Excel 并执行代付/查询，返回结果 Excel 下载 URL + 日志 + 汇总"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': '文件名为空'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.xls', '.xlsx'):
        return jsonify({'success': False, 'message': f'不支持的文件类型: {ext}'}), 400

    channel = request.form.get('channel', '')
    environment = request.form.get('environment', 'test')
    params = {
        'interface_type': request.form.get('interface_type', '代付'),
        'real_time': request.form.get('real_time', '是'),
        'execute_type': request.form.get('execute_type', '创建代付'),
    }

    cfg_db = PayConfig.query.filter_by(channel=channel).first()
    if not cfg_db:
        return jsonify({'success': False, 'message': f'渠道 {channel} 未配置'}), 400

    cfg = cfg_db.get_pro_config() if environment == 'pro' else cfg_db.get_test_config()
    if not cfg:
        return jsonify({'success': False, 'message': f'渠道 {channel} 的 {environment} 环境未配置'}), 400

    # 渠道参数
    params['bank_code'] = cfg_db.bank_code or 'CCB'
    params['online_bank_type'] = cfg_db.online_bank_type or 'B2C'
    params['transfer_mode'] = cfg_db.transfer_mode or ('6' if channel == 'kls' else '7')
    params['busi_type'] = cfg_db.busi_type or '144'
    params['channel_code'] = cfg_db.channel_code or ('kls' if channel == 'kls' else 'lepass')

    # 保存上传文件
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'pay')
    os.makedirs(upload_dir, exist_ok=True)
    saved_name = f"pay_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, saved_name)
    file.save(file_path)

    logs = []

    def log(msg):
        logs.append(msg)
        current_app.logger.info(f'[代付] {msg}')

    try:
        rows = pay_service._load_rows(file_path)
        if not rows:
            return jsonify({'success': False, 'message': 'Excel 无数据行'}), 400
        log(f'读取 {len(rows)} 行数据，渠道={channel} 环境={environment} 接口={params["interface_type"]}')
        message, result_rows = pay_service.execute_pay(channel, cfg, rows, params, log)
        result_path = pay_service._write_result(file_path, rows, result_rows)
        result_name = os.path.basename(result_path)
        return jsonify({
            'success': True,
            'data': {
                'message': message,
                'logs': logs,
                'result_url': f'/api/pay/files/{result_name}',
                'total': len(rows),
            },
        })
    except Exception as e:
        current_app.logger.exception('代付执行失败')
        return jsonify({'success': False, 'message': f'执行失败: {e}', 'logs': logs}), 500


@pay_bp.route('/files/<path:filename>', methods=['GET'])
@login_required
@permission_required('pay_withdraw')
def download_file(filename):
    """下载结果 Excel"""
    from flask import send_from_directory
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'pay')
    return send_from_directory(upload_dir, filename, as_attachment=True)
