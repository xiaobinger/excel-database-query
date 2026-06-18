import logging
from flask import Blueprint, request, jsonify
from app import db
from app.models.ai_agent import AiAgent
from app.models.agent_memory import AgentMemory
from app.utils.auth import login_required, admin_required, get_current_user, permission_required

logger = logging.getLogger(__name__)
agent_bp = Blueprint('agent', __name__, url_prefix='/api/agents')


@agent_bp.route('', methods=['GET'])
@login_required
def get_agents():
    """获取Agent列表：管理员可查看所有，普通用户只能查看被授权的，并返回切换权限"""
    current_user = get_current_user()
    can_switch = current_user.can_switch_agent()

    if current_user.is_admin():
        agents = AiAgent.query.filter_by(is_active=True).order_by(AiAgent.is_default.desc(), AiAgent.name).all()
    else:
        agents = current_user.get_allowed_agents()

    return jsonify({
        'success': True,
        'data': [a.to_dict() for a in agents],
        'can_switch_agent': can_switch,
    })


@agent_bp.route('/all', methods=['GET'])
@admin_required
def get_all_agents():
    """管理员获取所有Agent（包括禁用的）"""
    agents = AiAgent.query.order_by(AiAgent.is_default.desc(), AiAgent.name).all()
    return jsonify({'success': True, 'data': [a.to_dict() for a in agents]})


@agent_bp.route('/default', methods=['GET'])
@login_required
def get_default_agent():
    """获取默认Agent"""
    agent = AiAgent.query.filter_by(is_default=True, is_active=True).first()
    if not agent:
        # 如果没有默认Agent，返回第一个可用的
        current_user = get_current_user()
        if current_user.is_admin():
            agent = AiAgent.query.filter_by(is_active=True).first()
        else:
            agent_ids = current_user.get_agent_ids()
            if agent_ids is None:
                agent = AiAgent.query.filter_by(is_active=True).first()
            elif agent_ids:
                agent = AiAgent.query.filter(AiAgent.id.in_(agent_ids), AiAgent.is_active == True).first()
    
    if agent:
        return jsonify({'success': True, 'data': agent.to_dict()})
    return jsonify({'success': False, 'message': '没有可用的Agent'}), 404


@agent_bp.route('', methods=['POST'])
@permission_required('system')
def create_agent():
    """创建Agent"""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('system_prompt'):
        return jsonify({'success': False, 'message': '请填写Agent名称和系统提示词'}), 400
    
    current_user = get_current_user()
    
    try:
        agent = AiAgent(
            name=data['name'],
            description=data.get('description', ''),
            system_prompt=data['system_prompt'],
            is_default=data.get('is_default', False),
            is_active=data.get('is_active', True),
            created_by=current_user.id,
        )
        # 设置启用的工具列表
        if 'enabled_tools' in data:
            agent.set_enabled_tools(data['enabled_tools'])
        
        if agent.is_default:
            # 取消其他Agent的默认状态
            AiAgent.query.filter_by(is_default=True).update({'is_default': False})
        
        db.session.add(agent)
        db.session.commit()
        return jsonify({'success': True, 'data': agent.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'创建Agent失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@agent_bp.route('/<int:agent_id>', methods=['PUT'])
@permission_required('system')
def update_agent(agent_id):
    """更新Agent"""
    agent = AiAgent.query.get(agent_id)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent不存在'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400
    
    try:
        if 'name' in data:
            agent.name = data['name']
        if 'description' in data:
            agent.description = data['description']
        if 'system_prompt' in data:
            agent.system_prompt = data['system_prompt']
        if 'is_active' in data:
            agent.is_active = data['is_active']
        if 'enabled_tools' in data:
            agent.set_enabled_tools(data['enabled_tools'])
        
        if data.get('is_default'):
            # 取消其他Agent的默认状态
            AiAgent.query.filter(AiAgent.id != agent_id, AiAgent.is_default == True).update({'is_default': False})
            agent.is_default = True
        
        db.session.commit()
        return jsonify({'success': True, 'data': agent.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f'更新Agent失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@agent_bp.route('/<int:agent_id>', methods=['DELETE'])
@permission_required('system')
def delete_agent(agent_id):
    """删除Agent"""
    agent = AiAgent.query.get(agent_id)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent不存在'}), 404
    
    if agent.is_default:
        return jsonify({'success': False, 'message': '不能删除默认Agent'}), 400
    
    db.session.delete(agent)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@agent_bp.route('/batch-delete', methods=['POST'])
@permission_required('system')
def batch_delete_agents():
    """批量删除Agent"""
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'message': '请提供要删除的ID列表'}), 400
    
    ids = data.get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'success': False, 'message': 'ids必须是非空列表'}), 400
    
    deleted_count = 0
    for agent_id in ids:
        agent = AiAgent.query.get(agent_id)
        if agent and not agent.is_default:
            db.session.delete(agent)
            deleted_count += 1
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个Agent', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@agent_bp.route('/all', methods=['DELETE'])
@permission_required('system')
def delete_all_agents():
    """删除所有非默认Agent"""
    try:
        deleted_count = AiAgent.query.filter_by(is_default=False).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': f'成功删除{deleted_count}个Agent', 'deleted_count': deleted_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@agent_bp.route('/<int:agent_id>/set-default', methods=['POST'])
@permission_required('system')
def set_default_agent(agent_id):
    """设置默认Agent"""
    agent = AiAgent.query.get(agent_id)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent不存在'}), 404
    
    if not agent.is_active:
        return jsonify({'success': False, 'message': '不能将禁用的Agent设为默认'}), 400
    
    try:
        # 取消其他Agent的默认状态
        AiAgent.query.filter(AiAgent.id != agent_id, AiAgent.is_default == True).update({'is_default': False})
        agent.is_default = True
        db.session.commit()
        return jsonify({'success': True, 'data': agent.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


# ============ Agent 记忆管理 ============

@agent_bp.route('/<int:agent_id>/memories', methods=['GET'])
@login_required
def get_agent_memories(agent_id):
    """获取指定Agent的记忆列表（当前用户的）"""
    current_user = get_current_user()
    agent = AiAgent.query.get(agent_id)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent不存在'}), 404

    # 普通用户只能查看自己被授权的Agent的记忆
    if not current_user.is_admin() and not current_user.can_use_agent(agent_id):
        return jsonify({'success': False, 'message': '无权访问该Agent'}), 403

    memory_type = request.args.get('type', '')
    query = AgentMemory.query.filter_by(user_id=current_user.id, agent_id=agent_id, is_active=True)
    if memory_type:
        query = query.filter_by(memory_type=memory_type)
    memories = query.order_by(AgentMemory.created_at.desc()).all()

    return jsonify({'success': True, 'data': [m.to_dict() for m in memories]})


@agent_bp.route('/<int:agent_id>/memories', methods=['POST'])
@login_required
def add_agent_memory(agent_id):
    """手动添加Agent记忆"""
    current_user = get_current_user()
    agent = AiAgent.query.get(agent_id)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent不存在'}), 404

    if not current_user.is_admin() and not current_user.can_use_agent(agent_id):
        return jsonify({'success': False, 'message': '无权操作该Agent'}), 403

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'success': False, 'message': '记忆内容不能为空'}), 400

    try:
        memory = AgentMemory(
            user_id=current_user.id,
            agent_id=agent_id,
            memory_type=data.get('memory_type', 'rule'),
            content=data['content'].strip(),
            source='manual',
        )
        db.session.add(memory)
        db.session.commit()
        return jsonify({'success': True, 'data': memory.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'添加Agent记忆失败: {e}')
        return jsonify({'success': False, 'message': str(e)}), 400


@agent_bp.route('/<int:agent_id>/memories/<int:memory_id>', methods=['PUT'])
@login_required
def update_agent_memory(agent_id, memory_id):
    """更新Agent记忆"""
    current_user = get_current_user()
    memory = AgentMemory.query.filter_by(id=memory_id, user_id=current_user.id, agent_id=agent_id).first()
    if not memory:
        return jsonify({'success': False, 'message': '记忆不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求数据为空'}), 400

    try:
        if 'content' in data:
            memory.content = data['content'].strip()
        if 'memory_type' in data:
            memory.memory_type = data['memory_type']
        if 'is_active' in data:
            memory.is_active = data['is_active']
        db.session.commit()
        return jsonify({'success': True, 'data': memory.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@agent_bp.route('/<int:agent_id>/memories/<int:memory_id>', methods=['DELETE'])
@login_required
def delete_agent_memory(agent_id, memory_id):
    """删除Agent记忆"""
    current_user = get_current_user()
    memory = AgentMemory.query.filter_by(id=memory_id, user_id=current_user.id, agent_id=agent_id).first()
    if not memory:
        return jsonify({'success': False, 'message': '记忆不存在'}), 404

    db.session.delete(memory)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})