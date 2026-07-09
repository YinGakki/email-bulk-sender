from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import functools
import pandas as pd
import io
import os
import uuid
from datetime import datetime

from config import Config
from models import db, Contact, EmailTemplate, SendTask, SendLog, EmailConfig, Attachment
from email_sender import start_send_task, cancel_send_task

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

# 创建上传目录
os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'attachments'), exist_ok=True)


# ========== 数据库初始化（从 .env 导入默认配置）==========

def init_email_config():
    """首次运行时从 .env 导入默认邮箱配置"""
    with app.app_context():
        db.create_all()
        config = EmailConfig.query.first()
        if not config:
            config = EmailConfig(
                smtp_server=Config.SMTP_SERVER,
                smtp_port=Config.SMTP_PORT,
                smtp_username=Config.SMTP_USERNAME,
                smtp_password=Config.SMTP_PASSWORD,
                sender_name=Config.SENDER_NAME,
                batch_size=Config.BATCH_SIZE,
                send_interval=Config.SEND_INTERVAL
            )
            db.session.add(config)
            db.session.commit()


init_email_config()


# ========== 登录认证 ==========

def require_login(func):
    """登录认证装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not Config.ACCESS_PASSWORD:
            return func(*args, **kwargs)
        if session.get('logged_in'):
            return func(*args, **kwargs)
        return redirect(url_for('login_page'))
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """登录页面"""
    if not Config.ACCESS_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('index'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == Config.ACCESS_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='密码错误')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """退出登录"""
    session.pop('logged_in', None)
    return redirect(url_for('login_page'))


# ========== 页面路由 ==========

@app.route('/')
@require_login
def index():
    """首页"""
    return render_template('index.html')


@app.route('/contacts')
@require_login
def contacts_page():
    """联系人管理页面"""
    return render_template('contacts.html')


@app.route('/templates')
@require_login
def templates_page():
    """邮件模板页面"""
    return render_template('templates.html')


@app.route('/tasks')
@require_login
def tasks_page():
    """发送任务页面"""
    return render_template('tasks.html')


@app.route('/compose')
@require_login
def compose_page():
    """撰写邮件页面"""
    return render_template('compose.html')


@app.route('/settings')
@require_login
def settings_page():
    """邮箱设置页面"""
    return render_template('settings.html')


# ========== API 认证 ==========

@app.before_request
def check_api_auth():
    """API 请求认证检查"""
    exempt_paths = ['/login', '/logout']
    if request.path in exempt_paths:
        return None
    if request.path.startswith('/api/'):
        if not Config.ACCESS_PASSWORD:
            return None
        if not session.get('logged_in'):
            return jsonify({'success': False, 'error': '未登录'}), 401
    return None


# ========== 联系人 API ==========

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    """获取联系人列表"""
    contacts = Contact.query.order_by(Contact.created_at.desc()).all()
    return jsonify([c.to_dict() for c in contacts])


@app.route('/api/contacts', methods=['POST'])
def add_contact():
    """添加联系人"""
    data = request.get_json()
    contact = Contact(
        name=data.get('name'),
        email=data.get('email'),
        company=data.get('company'),
        phone=data.get('phone'),
        tags=data.get('tags'),
        notes=data.get('notes')
    )
    try:
        db.session.add(contact)
        db.session.commit()
        return jsonify({'success': True, 'contact': contact.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/contacts/<int:id>', methods=['PUT'])
def update_contact(id):
    """更新联系人"""
    contact = Contact.query.get(id)
    if not contact:
        return jsonify({'success': False, 'error': '联系人不存在'}), 404

    data = request.get_json()
    contact.name = data.get('name', contact.name)
    contact.email = data.get('email', contact.email)
    contact.company = data.get('company', contact.company)
    contact.phone = data.get('phone', contact.phone)
    contact.tags = data.get('tags', contact.tags)
    contact.notes = data.get('notes', contact.notes)

    try:
        db.session.commit()
        return jsonify({'success': True, 'contact': contact.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/contacts/<int:id>', methods=['DELETE'])
def delete_contact(id):
    """删除联系人"""
    contact = Contact.query.get(id)
    if not contact:
        return jsonify({'success': False, 'error': '联系人不存在'}), 404

    try:
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/contacts/import', methods=['POST'])
def import_contacts():
    """从CSV导入联系人"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '请上传文件'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': '文件名无效'}), 400

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(file.stream.read().decode('utf-8')))
        elif file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
            df = pd.read_excel(file.stream)
        else:
            return jsonify({'success': False, 'error': '只支持CSV和Excel文件'}), 400

        column_mapping = {
            '姓名': 'name', 'name': 'name', 'Name': 'name',
            '邮箱': 'email', 'email': 'email', 'Email': 'email',
            '公司': 'company', 'company': 'company', 'Company': 'company',
            '电话': 'phone', 'phone': 'phone', 'Phone': 'phone',
            '标签': 'tags', 'tags': 'tags', 'Tags': 'tags',
            '备注': 'notes', 'notes': 'notes', 'Notes': 'notes'
        }

        df.columns = [column_mapping.get(col.lower(), col.lower()) for col in df.columns]

        if 'name' not in df.columns or 'email' not in df.columns:
            return jsonify({'success': False, 'error': '文件必须包含"姓名"和"邮箱"列'}), 400

        imported = 0
        skipped = 0
        for _, row in df.iterrows():
            email = str(row['email']).strip()
            name = str(row['name']).strip()

            if not email or not name:
                skipped += 1
                continue

            existing = Contact.query.filter_by(email=email).first()
            if existing:
                skipped += 1
                continue

            contact = Contact(
                name=name,
                email=email,
                company=str(row.get('company', '')).strip() if 'company' in row else '',
                phone=str(row.get('phone', '')).strip() if 'phone' in row else '',
                tags=str(row.get('tags', '')).strip() if 'tags' in row else '',
                notes=str(row.get('notes', '')).strip() if 'notes' in row else ''
            )
            db.session.add(contact)
            imported += 1

        db.session.commit()
        return jsonify({'success': True, 'imported': imported, 'skipped': skipped})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/contacts/export', methods=['GET'])
def export_contacts():
    """导出联系人为CSV"""
    contacts = Contact.query.order_by(Contact.created_at.desc()).all()

    data = [{
        '姓名': c.name,
        '邮箱': c.email,
        '公司': c.company,
        '电话': c.phone,
        '标签': c.tags,
        '备注': c.notes
    } for c in contacts]

    df = pd.DataFrame(data)
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')

    return output.getvalue(), 200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename=contacts.csv'
    }


# ========== 模板 API ==========

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """获取模板列表"""
    templates = EmailTemplate.query.order_by(EmailTemplate.created_at.desc()).all()
    return jsonify([t.to_dict() for t in templates])


@app.route('/api/templates', methods=['POST'])
def add_template():
    """添加模板"""
    data = request.get_json()
    template = EmailTemplate(
        name=data.get('name'),
        subject=data.get('subject'),
        content=data.get('content')
    )
    try:
        db.session.add(template)
        db.session.commit()
        return jsonify({'success': True, 'template': template.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/templates/<int:id>', methods=['PUT'])
def update_template(id):
    """更新模板"""
    template = EmailTemplate.query.get(id)
    if not template:
        return jsonify({'success': False, 'error': '模板不存在'}), 404

    data = request.get_json()
    template.name = data.get('name', template.name)
    template.subject = data.get('subject', template.subject)
    template.content = data.get('content', template.content)

    try:
        db.session.commit()
        return jsonify({'success': True, 'template': template.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/templates/<int:id>', methods=['DELETE'])
def delete_template(id):
    """删除模板"""
    template = EmailTemplate.query.get(id)
    if not template:
        return jsonify({'success': False, 'error': '模板不存在'}), 404

    try:
        db.session.delete(template)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


# ========== 发送任务 API ==========

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    tasks = SendTask.query.order_by(SendTask.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks])


@app.route('/api/tasks/<int:id>', methods=['GET'])
def get_task(id):
    """获取任务详情"""
    task = SendTask.query.get(id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'}), 404

    logs = SendLog.query.filter_by(task_id=id).order_by(SendLog.sent_at.desc()).all()
    attachments = Attachment.query.filter_by(task_id=id).all()
    return jsonify({
        'task': task.to_dict(),
        'logs': [l.to_dict() for l in logs],
        'attachments': [a.to_dict() for a in attachments]
    })


@app.route('/api/tasks', methods=['POST'])
def create_task():
    """创建发送任务（支持附件上传）"""
    # 解析表单数据
    contact_ids_str = request.form.get('contact_ids', '')
    subject = request.form.get('subject', '')
    content = request.form.get('content', '')
    send_separately = request.form.get('send_separately', 'true').lower() == 'true'

    if not contact_ids_str:
        return jsonify({'success': False, 'error': '请选择收件人'}), 400

    try:
        contact_ids = [int(x.strip()) for x in contact_ids_str.split(',') if x.strip()]
    except ValueError:
        return jsonify({'success': False, 'error': '收件人ID格式错误'}), 400

    contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
    if not contacts:
        return jsonify({'success': False, 'error': '联系人不存在'}), 400

    contacts_data = [c.to_dict() for c in contacts]

    # 创建任务
    task = SendTask(
        name=request.form.get('name', f'发送任务-{datetime.now().strftime("%Y%m%d%H%M%S")}'),
        subject=subject,
        content=content,
        status='pending',
        total_count=len(contacts),
        send_separately=send_separately
    )
    db.session.add(task)
    db.session.commit()

    # 处理附件上传
    attachments = []
    uploaded_files = request.files.getlist('attachments')
    for file in uploaded_files:
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(Config.UPLOAD_FOLDER, 'attachments', unique_name)
            file.save(filepath)

            att = Attachment(
                task_id=task.id,
                filename=file.filename,
                filepath=filepath,
                file_size=os.path.getsize(filepath)
            )
            db.session.add(att)
            attachments.append({'filepath': filepath, 'filename': file.filename})

    db.session.commit()

    # 启动发送
    start_send_task(task.id, contacts_data, task.subject, task.content, app,
                    send_separately=send_separately, attachments=attachments)

    return jsonify({'success': True, 'task_id': task.id})


@app.route('/api/tasks/<int:id>/cancel', methods=['POST'])
def cancel_task(id):
    """取消任务"""
    task = SendTask.query.get(id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'}), 404

    if task.status != 'sending':
        return jsonify({'success': False, 'error': '任务不在发送状态'}), 400

    cancel_send_task(id)
    return jsonify({'success': True})


# ========== 邮箱配置 API ==========

@app.route('/api/email-config', methods=['GET'])
def get_email_config():
    """获取邮箱配置"""
    config = EmailConfig.get_config()
    return jsonify(config.to_dict(hide_password=True))


@app.route('/api/email-config', methods=['POST'])
def update_email_config():
    """更新邮箱配置"""
    data = request.get_json()
    config = EmailConfig.get_config()

    config.smtp_server = data.get('smtp_server', config.smtp_server)
    config.smtp_port = int(data.get('smtp_port', config.smtp_port))
    config.smtp_username = data.get('smtp_username', config.smtp_username)
    if data.get('smtp_password'):
        config.smtp_password = data.get('smtp_password')
    config.sender_name = data.get('sender_name', config.sender_name)
    config.batch_size = int(data.get('batch_size', config.batch_size))
    config.send_interval = int(data.get('send_interval', config.send_interval))

    try:
        db.session.commit()
        return jsonify({'success': True, 'config': config.to_dict(hide_password=True)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/email-config/test', methods=['POST'])
def test_email_config():
    """测试邮箱配置"""
    import smtplib
    config = EmailConfig.get_config()

    if not config.smtp_username or not config.smtp_password:
        return jsonify({'success': False, 'error': '邮箱账号或密码未配置'}), 400

    try:
        with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_username, config.smtp_password)
        return jsonify({'success': True, 'message': '连接成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


# ========== 配置 API（兼容旧版）==========

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前SMTP配置"""
    config = EmailConfig.get_config()
    return jsonify({
        'smtp_server': config.smtp_server,
        'smtp_port': config.smtp_port,
        'smtp_username': config.smtp_username,
        'sender_name': config.sender_name,
        'batch_size': config.batch_size,
        'send_interval': config.send_interval,
        'configured': bool(config.smtp_username and config.smtp_password)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
