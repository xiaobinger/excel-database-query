from datetime import datetime
from app import db
import json
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.helpers import beijing_isoformat


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(100))
    gender = db.Column(db.String(10), default='male')
    phone = db.Column(db.String(20), comment='手机号')
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    script_ids = db.Column(db.Text, comment='available script id list (JSON)')
    auto_task_ids = db.Column(db.Text, comment='available auto export task id list (JSON)')
    system_task_ids = db.Column(db.Text, comment='available system task id list (JSON)')

    role = db.relationship('Role', backref='users', lazy='joined')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_script_ids(self):
        if self.script_ids:
            try:
                return json.loads(self.script_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_script_ids(self, ids):
        self.script_ids = json.dumps(ids) if ids else None

    def get_auto_task_ids(self):
        if self.auto_task_ids:
            try:
                return json.loads(self.auto_task_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_auto_task_ids(self, ids):
        self.auto_task_ids = json.dumps(ids) if ids else None

    def get_system_task_ids(self):
        if self.system_task_ids:
            try:
                return json.loads(self.system_task_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_system_task_ids(self, ids):
        self.system_task_ids = json.dumps(ids) if ids else None

    def is_admin(self):
        if self.role and self.role.is_admin:
            return True
        return False

    def get_agent_ids(self):
        """获取用户可用的AgentID列表。管理员返回None表示全部可用"""
        if self.is_admin():
            return None  # 管理员可访问所有Agent
        if self.role:
            agent_perms = self.role.get_agent_permissions()
            # 如果包含"all"，表示该角色可访问所有Agent
            if 'all' in agent_perms:
                return None
            return [int(a) for a in agent_perms if str(a).isdigit()]
        return []

    def can_use_agent(self, agent_id):
        """检查用户是否可以使用指定Agent。默认Agent天然对所有用户可用"""
        from app.models.ai_agent import AiAgent
        # 检查是否是默认Agent
        agent = AiAgent.query.filter_by(id=agent_id, is_active=True).first()
        if agent and agent.is_default:
            return True  # 默认Agent天然对所有用户可用
        # 检查角色权限
        agent_ids = self.get_agent_ids()
        if agent_ids is None:
            return True  # 管理员或all权限
        return agent_id in agent_ids

    def can_switch_agent(self):
        """检查用户是否有切换Agent的权限（管理员或有角色开关即可，不管Agent数量）"""
        if self.is_admin():
            return True
        if not self.role or not self.role.can_switch_agent:
            return False
        return True

    def can_switch_model(self):
        """检查用户是否有切换模型的权限（管理员或有角色开关即可，不管模型数量）"""
        if self.is_admin():
            return True
        if not self.role or not self.role.can_switch_model:
            return False
        return True

    def get_model_ids(self):
        """获取用户可用的AI配置ID列表。管理员返回None表示全部可用"""
        if self.is_admin():
            return None
        if self.role:
            model_perms = self.role.get_model_permissions()
            if 'all' in model_perms:
                return None
            return [int(m) for m in model_perms if str(m).isdigit()]
        return []

    def get_allowed_models(self):
        """获取用户可用的AI配置列表（含默认模型）"""
        from app.models.ai_config import AiConfig
        model_ids = self.get_model_ids()
        if model_ids is None:
            return AiConfig.query.filter_by(is_active=True).order_by(AiConfig.name).all()
        # 始终包含默认模型
        default_config = AiConfig.query.filter_by(is_default=True, is_active=True).first()
        configs = AiConfig.query.filter(AiConfig.id.in_(model_ids), AiConfig.is_active == True).all()
        if default_config and default_config not in configs:
            configs.append(default_config)
        return configs

    def get_allowed_agents(self):
        """获取用户可用的Agent列表（含默认Agent）"""
        from app.models.ai_agent import AiAgent
        agent_ids = self.get_agent_ids()
        if agent_ids is None:
            return AiAgent.query.filter_by(is_active=True).order_by(AiAgent.name).all()
        # 始终包含默认Agent
        default_agent = AiAgent.query.filter_by(is_default=True, is_active=True).first()
        agents = AiAgent.query.filter(AiAgent.id.in_(agent_ids), AiAgent.is_active == True).all()
        if default_agent and default_agent not in agents:
            agents.append(default_agent)
        return agents

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'gender': self.gender or 'male',
            'phone': self.phone or '',
            'role_id': self.role_id,
            'is_active': self.is_active,
            'script_ids': self.get_script_ids(),
            'auto_task_ids': self.get_auto_task_ids(),
            'system_task_ids': self.get_system_task_ids(),
            'created_at': beijing_isoformat(self.created_at),
        }

    def to_dict_with_role(self):
        data = self.to_dict()
        if self.role:
            data['role'] = self.role.to_dict()
        else:
            data['role'] = None
        return data

    def __repr__(self):
        return f'<User {self.username}>'
