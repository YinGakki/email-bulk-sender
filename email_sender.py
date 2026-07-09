import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import threading
import time
from datetime import datetime
import re

from config import Config


class EmailSender:
    """邮件发送器"""

    def __init__(self):
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT
        self.smtp_username = Config.SMTP_USERNAME
        self.smtp_password = Config.SMTP_PASSWORD
        self.sender_name = Config.SENDER_NAME
        self.batch_size = Config.BATCH_SIZE
        self.send_interval = Config.SEND_INTERVAL

    def replace_variables(self, template, contact_info):
        """替换模板变量"""
        content = template
        # 支持 {{姓名}}、{{name}} 等格式
        for key, value in contact_info.items():
            # 支持 {{key}} 和 {{中文key}}
            pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            content = re.sub(pattern, str(value) if value else '', content)
        return content

    def send_single_email(self, to_email, to_name, subject, content):
        """发送单封邮件"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((self.sender_name, self.smtp_username))
            msg['To'] = formataddr((to_name, to_email))

            # 添加HTML内容
            html_part = MIMEText(content, 'html', 'utf-8')
            msg.attach(html_part)

            # 连接SMTP服务器并发送
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.smtp_username, [to_email], msg.as_string())

            return True, None
        except Exception as e:
            return False, str(e)

    def send_batch_emails(self, contacts, subject, content_template, 
                          progress_callback=None, cancel_event=None):
        """
        批量发送邮件
        :param contacts: 联系人列表 [{'id': 1, 'name': '张三', 'email': 'xxx@xx.com', 'company': '公司', ...}, ...]
        :param subject: 邮件主题
        :param content_template: 邮件内容模板
        :param progress_callback: 进度回调函数 callback(contact_id, email, status, error_msg)
        :param cancel_event: 取消事件 threading.Event
        :return: (成功数, 失败数)
        """
        success_count = 0
        fail_count = 0
        total = len(contacts)

        for i, contact in enumerate(contacts):
            # 检查是否取消
            if cancel_event and cancel_event.is_set():
                break

            # 替换变量
            contact_info = {
                '姓名': contact.get('name', ''),
                'name': contact.get('name', ''),
                '邮箱': contact.get('email', ''),
                'email': contact.get('email', ''),
                '公司': contact.get('company', ''),
                'company': contact.get('company', ''),
                '电话': contact.get('phone', ''),
                'phone': contact.get('phone', ''),
                '备注': contact.get('notes', ''),
                'notes': contact.get('notes', '')
            }

            personalized_subject = self.replace_variables(subject, contact_info)
            personalized_content = self.replace_variables(content_template, contact_info)

            # 发送邮件
            success, error = self.send_single_email(
                contact['email'],
                contact.get('name', ''),
                personalized_subject,
                personalized_content
            )

            if success:
                success_count += 1
                if progress_callback:
                    progress_callback(contact['id'], contact['email'], 'success', None)
            else:
                fail_count += 1
                if progress_callback:
                    progress_callback(contact['id'], contact['email'], 'failed', error)

            # 批次间隔
            if (i + 1) % self.batch_size == 0 and i + 1 < total:
                if cancel_event and cancel_event.is_set():
                    break
                time.sleep(self.send_interval)
            else:
                # 每封邮件间隔1-2秒，避免被判定为垃圾邮件
                time.sleep(1.5)

        return success_count, fail_count


class EmailSenderThread(threading.Thread):
    """邮件发送线程"""

    def __init__(self, sender, contacts, subject, content, task_id, app, cancel_event):
        super().__init__()
        self.sender = sender
        self.contacts = contacts
        self.subject = subject
        self.content = content
        self.task_id = task_id
        self.app = app
        self.cancel_event = cancel_event

    def run(self):
        from models import db, SendTask, SendLog

        with self.app.app_context():
            task = SendTask.query.get(self.task_id)
            if not task:
                return

            task.status = 'sending'
            task.started_at = datetime.utcnow()
            task.total_count = len(self.contacts)
            db.session.commit()

            def progress_callback(contact_id, email, status, error_msg):
                log = SendLog(
                    task_id=self.task_id,
                    contact_id=contact_id,
                    email=email,
                    name=next((c['name'] for c in self.contacts if c['id'] == contact_id), ''),
                    status=status,
                    error_message=error_msg,
                    sent_at=datetime.utcnow()
                )
                db.session.add(log)
                
                task.sent_count += 1
                if status == 'success':
                    task.success_count += 1
                else:
                    task.fail_count += 1
                db.session.commit()

            success, fail = self.sender.send_batch_emails(
                self.contacts,
                self.subject,
                self.content,
                progress_callback,
                self.cancel_event
            )

            # 更新任务状态
            task.status = 'cancelled' if self.cancel_event.is_set() else 'completed'
            task.completed_at = datetime.utcnow()
            db.session.commit()


# 全局发送任务管理
send_tasks = {}  # {task_id: {'thread': Thread, 'cancel_event': Event}}


def start_send_task(task_id, contacts, subject, content, app):
    """启动发送任务"""
    cancel_event = threading.Event()
    sender = EmailSender()
    thread = EmailSenderThread(sender, contacts, subject, content, task_id, app, cancel_event)
    
    send_tasks[task_id] = {
        'thread': thread,
        'cancel_event': cancel_event
    }
    thread.start()


def cancel_send_task(task_id):
    """取消发送任务"""
    if task_id in send_tasks:
        send_tasks[task_id]['cancel_event'].set()
        return True
    return False