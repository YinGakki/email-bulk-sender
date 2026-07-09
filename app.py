from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import functools
import pandas as pd
import io
import os
from datetime import datetime

from config import Config
from models import db, Contact, EmailTemplate, SendTask, SendLog
from email_sender import start_send_task, cancel_send_task

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

# 创建数据库表
with app.app_context():
    db.create_all()


# ========== 登录认证 ==========

def require_login(func):
    """登录认证装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 未设置密码则跳过认证
        if not Config.ACCESS_PASSWORD:
            return func(*args, **kwargs)
        # 已登录则放行
        if session.get('logged_in'):
            return func(*args, **kwargs)
        # 未登录跳转到登录页
        return redirect(url_for('login_page'))
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """登录页面"""
    # 未设置密码则直接放行
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


# ========== API 认证（统一处理） ==========

@app.before_request
def check_api_auth():
    """API 请求认证检查"""
    # 跳过不需要认证的路径
    exempt_paths = ['/login', '/logout']
    if request.path in exempt_paths:
        return None
    # 只检查 API 路由
    if request.path.startswith('/api/'):
        if not Config.ACCESS_PASSWORD:
            return None
        if not session.get('logged_in'):
            return jsonify({'success': False, 'error': '未登录'}), 401
    return None


# ========== 联系人 API ==========

@app.route('/api/contacts', methods=['GET'])
@require_login
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
        # 读取CSV或Excel
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(file.stream.read().decode('utf-8')))
        elif file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
            df = pd.read_excel(file.stream)
        else:
            return jsonify({'success': False, 'error': '只支持CSV和Excel文件'}), 400
        
        # 标准化列名
        column_mapping = {
            '姓名': 'name', 'name': 'name', 'Name': 'name',
            '邮箱': 'email', 'email': 'email', 'Email': 'email',
            '公司': 'company', 'company': 'company', 'Company': 'company',
            '电话': 'phone', 'phone': 'phone', 'Phone': 'phone',
            '标签': 'tags', 'tags': 'tags', 'Tags': 'tags',
            '备注': 'notes', 'notes': 'notes', 'Notes': 'notes'
        }
        
        df.columns = [column_mapping.get(col.lower(), col.lower()) for col in df.columns]
        
        # 检查必需列
        if 'name' not in df.columns or 'email' not in df.columns:
            return jsonify({'success': False, 'error': '文件必须包含"姓名"和"邮箱"列'}), 400
        
        # 导入数据
        imported = 0
        skipped = 0
        for _, row in df.iterrows():
            email = str(row['email']).strip()
            name = str(row['name']).strip()
            
            if not email or not name:
                skipped += 1
                continue
            
            # 检查是否已存在
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
    return jsonify({
        'task': task.to_dict(),
        'logs': [l.to_dict() for l in logs]
    })


@app.route('/api/tasks', methods=['POST'])
def create_task():
    """创建发送任务"""
    data = request.get_json()
    
    # 获取选中的联系人
    contact_ids = data.get('contact_ids', [])
    if not contact_ids:
        return jsonify({'success': False, 'error': '请选择收件人'}), 400
    
    contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
    if not contacts:
        return jsonify({'success': False, 'error': '联系人不存在'}), 400
    
    contacts_data = [c.to_dict() for c in contacts]
    
    # 创建任务
    task = SendTask(
        name=data.get('name', f'发送任务-{datetime.now().strftime("%Y%m%d%H%M%S")}'),
        subject=data.get('subject'),
        content=data.get('content'),
        status='pending',
        total_count=len(contacts)
    )
    db.session.add(task)
    db.session.commit()
    
    # 启动发送
    start_send_task(task.id, contacts_data, task.subject, task.content, app)
    
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


# ========== 配置 API ==========

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前SMTP配置"""
    return jsonify({
        'smtp_server': Config.SMTP_SERVER,
        'smtp_port': Config.SMTP_PORT,
        'smtp_username': Config.SMTP_USERNAME,
        'sender_name': Config.SENDER_NAME,
        'batch_size': Config.BATCH_SIZE,
        'send_interval': Config.SEND_INTERVAL,
        'configured': bool(Config.SMTP_USERNAME and Config.SMTP_PASSWORD)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)