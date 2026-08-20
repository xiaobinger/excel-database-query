"""工单模型

状态流转：
  submitted             已提交     提交人创建 / 申诉重启 / 核实不通过重新发起 / 重新指派
  received              已接收     指派人接收
  processing            处理中     指派人开始处理 / AI处理中
  rejected              拒绝       指派人拒绝（需原因），提交人可申诉重启
  processed             已处理     指派人完成处理 / AI处理成功，待提交人核实
  pending_assignment    待指派     AI处理失败，提醒提交人重新指派具体的人来人工介入
  pending_confirmation  待确认     AI需执行数据变更类任务(如SQL系统任务)，等待提交人确认后继续执行
  closed                结束       提交人核实通过 / 管理员关闭

指派类型：
  user  指派给具体用户（assignee_id 关联 users.id）
  ai    指派给AI助手（assignee_agent_id 关联 ai_agents.id，由AI自动处理）
"""
import json
from datetime import datetime
from app import db
from app.utils.helpers import beijing_isoformat


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_no = db.Column(db.String(32), nullable=False, unique=True, comment='工单编号')
    title = db.Column(db.String(200), nullable=False, comment='标题')
    content = db.Column(db.Text, comment='工单内容(Markdown富文本)')
    business_system_id = db.Column(db.Integer, db.ForeignKey('business_systems.id'), comment='涉及业务系统')

    # 指派人：user类型关联users.id，ai类型关联ai_agents.id
    assignee_type = db.Column(db.String(10), default='user', nullable=False, comment='指派类型: user/ai')
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='指派人ID(当assignee_type=user)')
    assignee_agent_id = db.Column(db.Integer, db.ForeignKey('ai_agents.id'), comment='指派AI Agent ID(当assignee_type=ai)')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='提交人ID')

    status = db.Column(db.String(20), default='submitted', nullable=False, comment='状态')
    reject_reason = db.Column(db.Text, comment='最新拒绝原因')
    appeal_reason = db.Column(db.Text, comment='最新申诉理由')
    ai_result = db.Column(db.Text, comment='AI处理结果')
    pending_action = db.Column(db.Text, comment='待确认执行的任务信息(JSON)，AI遇到数据变更类任务时存储')

    submitted_at = db.Column(db.DateTime, comment='提交时间')
    received_at = db.Column(db.DateTime, comment='接收时间')
    processed_at = db.Column(db.DateTime, comment='处理完成时间')
    closed_at = db.Column(db.DateTime, comment='结束时间')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_tickets', lazy='joined')
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref='assigned_tickets', lazy='joined')
    assignee_agent = db.relationship('AiAgent', foreign_keys=[assignee_agent_id], lazy='joined')
    business_system = db.relationship('BusinessSystem', foreign_keys=[business_system_id], lazy='joined')
    comments = db.relationship('TicketComment', backref='ticket', lazy='select', cascade='all, delete-orphan',
                               order_by='TicketComment.created_at.asc()')
    attachments = db.relationship('TicketAttachment', backref='ticket', lazy='select', cascade='all, delete-orphan',
                                  order_by='TicketAttachment.created_at.asc()')

    def get_pending_action(self) -> dict:
        """获取待确认执行的任务信息"""
        if self.pending_action:
            try:
                return json.loads(self.pending_action)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_pending_action(self, data: dict):
        """设置待确认执行的任务信息"""
        self.pending_action = json.dumps(data, ensure_ascii=False) if data else None

    def clear_pending_action(self):
        """清空待确认执行的任务信息"""
        self.pending_action = None

    def to_dict(self, include_comments=False) -> dict:
        # 指派人名称
        if self.assignee_type == 'ai':
            assignee_name = self.assignee_agent.name if self.assignee_agent else 'AI助手'
            assignee_username = None
        else:
            assignee_name = self.assignee.display_name or self.assignee.username if self.assignee else None
            assignee_username = self.assignee.username if self.assignee else None

        data = {
            'id': self.id,
            'ticket_no': self.ticket_no,
            'title': self.title,
            'content': self.content or '',
            'business_system_id': self.business_system_id,
            'business_system_name': self.business_system.name if self.business_system else None,
            'assignee_type': self.assignee_type or 'user',
            'assignee_id': self.assignee_id,
            'assignee_agent_id': self.assignee_agent_id,
            'assignee_name': assignee_name,
            'assignee_username': assignee_username,
            'created_by': self.created_by,
            'creator_name': self.creator.display_name or self.creator.username if self.creator else None,
            'creator_username': self.creator.username if self.creator else None,
            'status': self.status,
            'reject_reason': self.reject_reason,
            'appeal_reason': self.appeal_reason,
            'ai_result': self.ai_result,
            'pending_action': self.get_pending_action(),
            'submitted_at': beijing_isoformat(self.submitted_at),
            'received_at': beijing_isoformat(self.received_at),
            'processed_at': beijing_isoformat(self.processed_at),
            'closed_at': beijing_isoformat(self.closed_at),
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
        if include_comments:
            data['comments'] = [c.to_dict() for c in (self.comments or [])]
        data['attachments'] = [a.to_dict() for a in (self.attachments or [])]
        return data

    def __repr__(self):
        return f'<Ticket {self.ticket_no}>'


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, comment='工单ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='评论人ID')
    content = db.Column(db.Text, comment='评论内容(Markdown富文本)')
    action = db.Column(db.String(20), default='comment', comment='动作: comment/reject/appeal/status_change/ai_process')
    is_ai = db.Column(db.Boolean, default=False, comment='是否AI生成')
    attachment_path = db.Column(db.String(500), comment='附件文件路径')
    attachment_name = db.Column(db.String(200), comment='附件文件名')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], lazy='joined')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'user_id': self.user_id,
            'user_name': 'AI助手' if self.is_ai else (self.user.display_name or self.user.username if self.user else None),
            'user_username': self.user.username if self.user else None,
            'content': self.content or '',
            'action': self.action,
            'is_ai': self.is_ai,
            'attachment_path': self.attachment_path,
            'attachment_name': self.attachment_name,
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<TicketComment {self.id}>'


class TicketAttachment(db.Model):
    """工单附件（提交工单时上传的数据文件，如查询任务所需的Excel等）"""
    __tablename__ = 'ticket_attachments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), comment='工单ID(未关联时为NULL，暂存待提交)')
    file_path = db.Column(db.String(500), nullable=False, comment='文件存储路径')
    file_name = db.Column(db.String(200), nullable=False, comment='原始文件名')
    file_size = db.Column(db.Integer, default=0, comment='文件大小(字节)')
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='上传人ID')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy='joined')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'uploader_name': self.uploader.display_name or self.uploader.username if self.uploader else None,
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<TicketAttachment {self.id} {self.file_name}>'
