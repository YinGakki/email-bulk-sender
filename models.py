from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Contact(db.Model):
    """联系人模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    company = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    tags = db.Column(db.String(500))  # 逗号分隔的标签
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'company': self.company or '',
            'phone': self.phone or '',
            'tags': self.tags or '',
            'notes': self.notes or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else ''
        }


class EmailTemplate(db.Model):
    """邮件模板模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else ''
        }


class SendTask(db.Model):
    """发送任务模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    subject = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, sending, completed, cancelled
    total_count = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    fail_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'content': self.content,
            'status': self.status,
            'total_count': self.total_count,
            'sent_count': self.sent_count,
            'success_count': self.success_count,
            'fail_count': self.fail_count,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M:%S') if self.started_at else '',
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else ''
        }


class SendLog(db.Model):
    """发送日志模型"""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('send_task.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    email = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    error_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)

    task = db.relationship('SendTask', backref=db.backref('logs', lazy=True))
    contact = db.relationship('Contact', backref=db.backref('logs', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'contact_id': self.contact_id,
            'email': self.email,
            'name': self.name,
            'status': self.status,
            'error_message': self.error_message or '',
            'sent_at': self.sent_at.strftime('%Y-%m-%d %H:%M:%S') if self.sent_at else ''
        }