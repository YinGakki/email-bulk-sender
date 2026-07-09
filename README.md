# 邮件批量发送工具

基于 Flask 的 Web 邮件批量发送工具，支持个性化变量、分批发送、进度追踪。

## 功能特性

- **联系人管理** - 手动添加、CSV/Excel 导入、搜索筛选、导入/导出
- **邮件模板** - 创建和管理邮件模板，快速复用
- **个性化变量** - 支持 `{{姓名}}`、`{{公司}}` 等变量自动替换
- **分批发送** - 可配置批次大小和间隔，避免被判定为垃圾邮件
- **进度追踪** - 实时查看发送进度和结果
- **发送日志** - 记录每封邮件的发送状态和错误信息
- **单独发送** - 每个收件人独立接收，互不可见

## 快速开始

### 方式一：本地运行

```bash
git clone https://github.com/你的用户名/email-bulk-sender.git
cd email-bulk-sender
./install.sh
./start.sh
```

访问 http://localhost:5000 即可使用。

### 方式二：Linux 服务器部署

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/email-bulk-sender.git /opt/email-sender
cd /opt/email-sender

# 2. 一键安装（自动配置）
./install.sh

# 3. 启动
./start.sh

# 或使用 systemd 服务（推荐）
sudo cp email-sender.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-sender
sudo systemctl start email-sender
```

### 方式三：手动部署

#### 1. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. 配置邮箱

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
vim .env
```

配置内容示例：

```
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_qq@qq.com
SMTP_PASSWORD=你的授权码
SENDER_NAME=你的名称
SECRET_KEY=随机密钥
ACCESS_PASSWORD=页面访问密码
```

**获取 QQ 邮箱授权码：**
1. 登录 QQ 邮箱网页版
2. 进入「设置」→「账户」
3. 找到「POP3/SMTP服务」，点击「开启」
4. 按提示发送短信验证
5. 获得授权码

#### 3. 启动服务

```bash
python app.py
```

## 使用流程

1. **导入联系人** - 在「联系人」页面导入 CSV/Excel 文件，或手动添加
2. **创建模板** - 在「模板」页面创建邮件模板（可选）
3. **撰写邮件** - 在「撰写」页面选择收件人、编辑内容
4. **发送邮件** - 点击发送，在「任务」页面查看实时进度

## CSV 文件格式

CSV 文件必须包含以下列：

| 列名 | 必填 | 说明 |
|------|------|------|
| 姓名 | ✓ | 联系人姓名 |
| 邮箱 | ✓ | 联系人邮箱 |
| 公司 | | 联系人公司 |
| 电话 | | 联系人电话 |
| 标签 | | 多个标签用逗号分隔 |
| 备注 | | 其他备注信息 |

示例：

```csv
姓名,邮箱,公司,电话,标签,备注
张三,zhangsan@example.com,ABC公司,13800138000,VIP,重要客户
李四,lisi@example.com,XYZ公司,13900139000,,普通客户
```

## 模板变量

在邮件主题和内容中使用以下变量，系统会自动替换：

- `{{姓名}}` 或 `{{name}}` - 联系人姓名
- `{{公司}}` 或 `{{company}}` - 联系人公司
- `{{邮箱}}` 或 `{{email}}` - 联系人邮箱
- `{{电话}}` 或 `{{phone}}` - 联系人电话
- `{{备注}}` 或 `{{notes}}` - 联系人备注

示例邮件内容：

```html
<p>尊敬的{{姓名}}：</p>
<p>您好！感谢您选择{{公司}}。</p>
<p>我们将为您提供最优质的服务。</p>
<p>如有任何问题，请联系：{{电话}}</p>
```

## 发送配置

在 `.env` 文件中可调整发送参数：

```
BATCH_SIZE=10      # 每批发送数量
SEND_INTERVAL=5    # 批次间隔秒数
```

## 项目结构

```
email-bulk-sender/
├── app.py                  # Flask 主应用
├── config.py               # 配置文件
├── models.py               # 数据模型
├── email_sender.py         # 邮件发送核心逻辑
├── requirements.txt        # 依赖列表
├── start.sh                # 启动脚本
├── install.sh              # 一键安装脚本
├── email-sender.service    # systemd 服务配置
├── .env.example            # 配置示例
├── .gitignore
├── README.md
└── templates/              # Web 界面模板
    ├── base.html
    ├── index.html
    ├── contacts.html
    ├── templates.html
    ├── compose.html
    └── tasks.html
```

## 密码保护

在 `.env` 中设置 `ACCESS_PASSWORD` 即可启用页面密码保护：

```
ACCESS_PASSWORD=your-password
```

- 设置后所有页面和 API 都需要先输入密码才能访问
- 留空则不启用密码保护
- `./install.sh` 安装时会交互式提示设置

## 注意事项

1. **发送间隔** - 为避免被判定为垃圾邮件，每封邮件间隔 1.5 秒，每批次间隔 5 秒
2. **邮箱限制** - QQ 邮箱每日发送量有上限（约 500 封），请勿过度使用
3. **数据安全** - 所有数据存储在本地 SQLite 数据库，不会上传到服务器
4. **授权码** - SMTP 密码使用的是授权码，不是 QQ 密码
5. **防火墙** - 部署到服务器后，请确保防火墙开放 5000 端口（或配置 Nginx 反向代理）

## 技术栈

- **后端**: Python 3 + Flask + SQLAlchemy
- **前端**: 原生 HTML/CSS/JavaScript
- **数据库**: SQLite（本地存储，无需额外配置）