from flask import Blueprint, request, jsonify
from app import db
from app.models.ai_strategy import AiStrategy
from app.models.ai_config import AiConfig
from app.utils.auth import permission_required

ai_strategy_bp = Blueprint('ai_strategy', __name__, url_prefix='/api/ai-strategy')


def _enrich_strategy(strategy):
    d = strategy.to_dict()
    model_ids = strategy.get_model_ids()
    models = []
    for mid in model_ids:
        cfg = AiConfig.query.get(mid)
        if cfg:
            models.append({'id': cfg.id, 'name': cfg.name, 'model_name': cfg.model_name, 'is_active': cfg.is_active})
    d['models'] = models
    return d


@ai_strategy_bp.route('/list', methods=['GET'])
@permission_required('system')
def list_strategies():
    strategies = AiStrategy.query.order_by(AiStrategy.sort_order.desc()).all()
    data = [_enrich_strategy(s) for s in strategies]
    return jsonify({'success': True, 'data': data})


@ai_strategy_bp.route('/<int:strategy_id>', methods=['GET'])
@permission_required('system')
def get_strategy(strategy_id):
    strategy = AiStrategy.query.get(strategy_id)
    if not strategy:
        return jsonify({'success': False, 'message': '策略不存在'}), 404
    return jsonify({'success': True, 'data': _enrich_strategy(strategy)})


@ai_strategy_bp.route('', methods=['POST'])
@permission_required('system')
def create_strategy():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    strategy = AiStrategy()
    db.session.add(strategy)
    _apply_fields(strategy, data)
    db.session.commit()
    return jsonify({'success': True, 'data': strategy.to_dict(), 'message': '策略已创建'})


@ai_strategy_bp.route('/<int:strategy_id>', methods=['PUT'])
@permission_required('system')
def update_strategy(strategy_id):
    strategy = AiStrategy.query.get(strategy_id)
    if not strategy:
        return jsonify({'success': False, 'message': '策略不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    _apply_fields(strategy, data)
    db.session.commit()
    return jsonify({'success': True, 'data': strategy.to_dict(), 'message': '策略已更新'})


@ai_strategy_bp.route('/<int:strategy_id>', methods=['DELETE'])
@permission_required('system')
def delete_strategy(strategy_id):
    strategy = AiStrategy.query.get(strategy_id)
    if not strategy:
        return jsonify({'success': False, 'message': '策略不存在'}), 404

    db.session.delete(strategy)
    db.session.commit()
    return jsonify({'success': True, 'message': '策略已删除'})


@ai_strategy_bp.route('/<int:strategy_id>/reset-tokens', methods=['POST'])
@permission_required('system')
def reset_token_usage(strategy_id):
    strategy = AiStrategy.query.get(strategy_id)
    if not strategy:
        return jsonify({'success': False, 'message': '策略不存在'}), 404

    strategy.token_usage = None
    strategy.round_robin_index = 0
    db.session.commit()
    return jsonify({'success': True, 'message': 'Token统计已重置'})


def _apply_fields(strategy, data):
    simple_fields = ['name', 'strategy_type', 'failover_enabled', 'failover_max_retries',
                     'failover_timeout', 'description', 'is_active', 'route_to_free_only', 'sort_order']
    for field in simple_fields:
        if field in data:
            setattr(strategy, field, data[field])

    if 'model_ids' in data:
        strategy.set_model_ids(data['model_ids'])
    if 'scope' in data:
        strategy.set_scope(data['scope'])

    if 'strategy_type' in data:
        strategy.round_robin_index = 0
    if 'model_ids' in data:
        strategy.token_usage = None
