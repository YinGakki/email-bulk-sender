import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
import threading
import time
from datetime import datetime
import re
import os


class EmailSender:
    """邮件发送器"""

    def __init__(self, config):
        """
        :param config: EmailConfig 模型实例
        """
        self.smtp_server = config.smtp_server
        self.smtp_port = config.smtp_port
        self.smtp_username = config.smtp_username
        self.smtp_password = config.smtp_password
        self.sender_name = config.sender_name
        self.batch_size = config.batch_size
        self.send_interval = config.send_interval

    def replace_variables(self, template, contact_info):
        """替换模板变量"""
        content = template
        for key, value in contact_info.items():
            pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            content = re.sub(pattern, str(value) if value else '', content)
        return content

    def _build_msg(self, subject, content, attachments=None):
        """构建邮件消息体"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = formataddr((self.sender_name, self.smtp_username))

        # HTML内容
        html_part = MIMEText(content, 'html', 'utf-8')
        msg.attach(html_part)

        # 附件
        if attachments:
            for att in attachments:
                filepath = att.get('filepath')
                filename = att.get('filename')
                if filepath and os.path.exists(filepath):
                    with open(filepath, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filename}"'
                    )
                    msg.attach(part)

        return msg

    def send_single_email(self, to_email, to_name, subject, content, attachments=None):
        """发送单封邮件（分别发送模式）"""
        try:
            msg = self._build_msg(subject, content, attachments)
            msg['To'] = formataddr((to_name, to_email))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.smtp_username, [to_email], msg.as_string())

            return True, None
        except Exception as e:
            return False, str(e)

    def send_group_email(self, contacts, subject, content, attachments=None):
        """发送群发邮件（一封邮件发给所有人）"""
        try:
            msg = self._build_msg(subject, content, attachments)
            to_addrs = []
            to_header = []
            for c in contacts:
                to_addrs.append(c['email'])
                to_header.append(formataddr((c.get('name', ''), c['email'])))
            msg['To'] = ', '.join(to_header)
            # 添加 Bcc 确保每个收件人只看到发件人和自己
            msg['Bcc'] = ', '.join(to_addrs)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.smtp_username, to_addrs, msg.as_string())

            return True, None
        except Exception as e:
            return False, str(e)

    def send_batch_emails(self, contacts, subject, content_template,
                          send_separately=True, attachments=None,
                          progress_callback=None, cancel_event=None):
        """
        批量发送邮件
        :param contacts: 联系人列表
        :param subject: 邮件主题
        :param content_template: 邮件内容模板
        :param send_separately: True=分别发送，False=群发
        :param attachments: 附件列表 [{'filepath': '...', 'filename': '...'}, ...]
        :param progress_callback: 进度回调函数
        :param cancel_event: 取消事件
        :return: (成功数, 失败数)
        """
        success_count = 0
        fail_count = 0
        total = len(contacts)

        # 群发模式：一封邮件发给所有人
        if not send_separately:
            if cancel_event and cancel_event.is_set():
                return 0, total

            success, error = self.send_group_email(contacts, subject, content_template, attachments)
            if success:
                success_count = total
                for c in contacts:
                    if progress_callback:
                        progress_callback(c['id'], c['email'], 'success', None)
            else:
                fail_count = total
                for c in contacts:
                    if progress_callback:
                        progress_callback(c['id'], c['email'], 'failed', error)
            return success_count, fail_count

        # 分别发送模式
        for i, contact in enumerate(contacts):
            if cancel_event and cancel_event.is_set():
                break

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

            success, error = self.send_single_email(
                contact['email'],
                contact.get('name', ''),
                personalized_subject,
                personalized_content,
                attachments
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
                time.sleep(1.5)

        return success_count, fail_count


class EmailSenderThread(threading.Thread):
    """邮件发送线程"""

    def __init__(self, sender, contacts, subject, content, task_id, app,
                 send_separately=True, attachments=None, cancel_event=None):
        super().__init__()
        self.sender = sender
        self.contacts = contacts
        self.subject = subject
        self.content = content
        self.task_id = task_id
        self.app = app
        self.send_separately = send_separately
        self.attachments = attachments
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
                send_separately=self.send_separately,
                attachments=self.attachments,
                progress_callback=progress_callback,
                cancel_event=self.cancel_event
            )

            task.status = 'cancelled' if self.cancel_event.is_set() else 'completed'
            task.completed_at = datetime.utcnow()
            db.session.commit()


# 全局发送任务管理
send_tasks = {}


def start_send_task(task_id, contacts, subject, content, app,
                    send_separately=True, attachments=None):
    """启动发送任务"""
    from models import EmailConfig
    with app.app_context():
        config = EmailConfig.get_config()

    cancel_event = threading.Event()
    sender = EmailSender(config)
    thread = EmailSenderThread(
        sender, contacts, subject, content, task_id, app,
        send_separately=send_separately, attachments=attachments,
        cancel_event=cancel_event
    )

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
