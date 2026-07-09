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
    send_separately = db.Column(db.Boolean, default=True)  # 分别发送
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
            'send_separately': self.send_separately,
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


class EmailConfig(db.Model):
    """邮箱配置模型（单条记录）"""
    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(200), default='smtp.qq.com')
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(200), default='')
    smtp_password = db.Column(db.String(500), default='')
    sender_name = db.Column(db.String(200), default='')
    batch_size = db.Column(db.Integer, default=10)
    send_interval = db.Column(db.Integer, default=5)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_config():
        """获取或创建默认配置"""
        config = EmailConfig.query.first()
        if not config:
            config = EmailConfig()
            db.session.add(config)
            db.session.commit()
        return config

    def to_dict(self, hide_password=True):
        result = {
            'id': self.id,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'smtp_username': self.smtp_username,
            'sender_name': self.sender_name,
            'batch_size': self.batch_size,
            'send_interval': self.send_interval,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else ''
        }
        if not hide_password:
            result['smtp_password'] = self.smtp_password
        return result


class Attachment(db.Model):
    """附件模型"""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('send_task.id'), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    filepath = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship('SendTask', backref=db.backref('attachments', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'filename': self.filename,
            'file_size': self.file_size,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else ''
        }