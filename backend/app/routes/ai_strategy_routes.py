from flask import Blueprint, request, jsonify
from app import db
from app.models.ai_strategy import AiStrategy
from app.models.ai_config import AiConfig
from app.utils.auth import permission_required

ai_strategy_bp = Blueprint('ai_strategy', __name__, url_prefix='/api/ai-strategy')


@ai_strategy_bp.route('', methods=['GET'])
@permission_required('system')
def get_strategy():
    strategy = AiStrategy.query.filter_by(is_active=True).first()
    if not strategy:
        return jsonify({'success': True, 'data': None, 'message': '未配置策略'})
    # Enrich with model details
    d = strategy.to_dict()
    model_ids = strategy.get_model_ids()
    models = []
    for mid in model_ids:
        cfg = AiConfig.query.get(mid)
        if cfg:
            models.append({'id': cfg.id, 'name': cfg.name, 'model_name': cfg.model_name, 'is_active': cfg.is_active})
    d['models'] = models
    return jsonify({'success': True, 'data': d})


@ai_strategy_bp.route('', methods=['POST', 'PUT'])
@permission_required('system')
def save_strategy():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    strategy = AiStrategy.query.filter_by(is_active=True).first()
    is_new = not strategy

    if is_new:
        strategy = AiStrategy()
        db.session.add(strategy)

    strategy.name = data.get('name', '默认策略')
    strategy.strategy_type = data.get('strategy_type', 'priority')
    strategy.failover_enabled = data.get('failover_enabled', True)
    strategy.failover_max_retries = data.get('failover_max_retries', 3)
    strategy.failover_timeout = data.get('failover_timeout', 30)
    strategy.description = data.get('description', '')
    strategy.is_active = data.get('is_active', True)

    if 'model_ids' in data:
        strategy.set_model_ids(data['model_ids'])

    # Reset round_robin_index when strategy changes
    if 'strategy_type' in data:
        strategy.round_robin_index = 0
    if 'model_ids' in data:
        strategy.token_usage = None

    db.session.commit()
    return jsonify({'success': True, 'data': strategy.to_dict(), 'message': '策略已保存'})


@ai_strategy_bp.route('', methods=['DELETE'])
@permission_required('system')
def delete_strategy():
    strategy = AiStrategy.query.filter_by(is_active=True).first()
    if strategy:
        db.session.delete(strategy)
        db.session.commit()
    return jsonify({'success': True, 'message': '策略已删除'})


@ai_strategy_bp.route('/reset-tokens', methods=['POST'])
@permission_required('system')
def reset_token_usage():
    strategy = AiStrategy.query.filter_by(is_active=True).first()
    if not strategy:
        return jsonify({'success': False, 'message': '未配置策略'}), 404
    strategy.token_usage = None
    strategy.round_robin_index = 0
    db.session.commit()
    return jsonify({'success': True, 'message': 'Token统计已重置'})
