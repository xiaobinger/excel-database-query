"""工单模型

状态流转：
  submitted  已提交    提交人创建 / 申诉重启 / 核实不通过重新发起
  received   已接收    指派人接收
  processing 处理中    指派人开始处理
  rejected   拒绝      指派人拒绝（需原因），提交人可申诉重启
  processed  已处理    指派人完成处理，待提交人核实
  closed     结束      提交人核实通过 / 管理员关闭
"""
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
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='指派人ID')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='提交人ID')

    status = db.Column(db.String(20), default='submitted', nullable=False, comment='状态')
    reject_reason = db.Column(db.Text, comment='最新拒绝原因')
    appeal_reason = db.Column(db.Text, comment='最新申诉理由')

    submitted_at = db.Column(db.DateTime, comment='提交时间')
    received_at = db.Column(db.DateTime, comment='接收时间')
    processed_at = db.Column(db.DateTime, comment='处理完成时间')
    closed_at = db.Column(db.DateTime, comment='结束时间')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_tickets', lazy='joined')
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref='assigned_tickets', lazy='joined')
    business_system = db.relationship('BusinessSystem', foreign_keys=[business_system_id], lazy='joined')
    comments = db.relationship('TicketComment', backref='ticket', lazy='select', cascade='all, delete-orphan',
                               order_by='TicketComment.created_at.asc()')

    def to_dict(self, include_comments=False) -> dict:
        data = {
            'id': self.id,
            'ticket_no': self.ticket_no,
            'title': self.title,
            'content': self.content or '',
            'business_system_id': self.business_system_id,
            'business_system_name': self.business_system.name if self.business_system else None,
            'assignee_id': self.assignee_id,
            'assignee_name': self.assignee.display_name or self.assignee.username if self.assignee else None,
            'assignee_username': self.assignee.username if self.assignee else None,
            'created_by': self.created_by,
            'creator_name': self.creator.display_name or self.creator.username if self.creator else None,
            'creator_username': self.creator.username if self.creator else None,
            'status': self.status,
            'reject_reason': self.reject_reason,
            'appeal_reason': self.appeal_reason,
            'submitted_at': beijing_isoformat(self.submitted_at),
            'received_at': beijing_isoformat(self.received_at),
            'processed_at': beijing_isoformat(self.processed_at),
            'closed_at': beijing_isoformat(self.closed_at),
            'created_at': beijing_isoformat(self.created_at),
            'updated_at': beijing_isoformat(self.updated_at),
        }
        if include_comments:
            data['comments'] = [c.to_dict() for c in (self.comments or [])]
        return data

    def __repr__(self):
        return f'<Ticket {self.ticket_no}>'


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False, comment='工单ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='评论人ID')
    content = db.Column(db.Text, comment='评论内容(Markdown富文本)')
    action = db.Column(db.String(20), default='comment', comment='动作: comment/reject/appeal/status_change')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], lazy='joined')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'user_id': self.user_id,
            'user_name': self.user.display_name or self.user.username if self.user else None,
            'user_username': self.user.username if self.user else None,
            'content': self.content or '',
            'action': self.action,
            'created_at': beijing_isoformat(self.created_at),
        }

    def __repr__(self):
        return f'<TicketComment {self.id}>'
