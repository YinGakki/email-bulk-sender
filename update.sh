#!/bin/bash
# 邮件批量发送工具 - 服务器一键更新脚本
# 使用方法：在服务器上执行 bash update.sh

set -e

PROJECT_DIR="/opt/email-sender"
SERVICE_NAME="email-sender"

echo "=========================================="
echo "邮件批量发送工具 - 更新脚本"
echo "=========================================="
echo ""

# 自动查找项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo "默认路径 $PROJECT_DIR 不存在，正在查找..."
    FOUND=$(find / -name "app.py" -path "*email*" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        PROJECT_DIR=$(dirname "$FOUND")
        echo "找到项目目录: $PROJECT_DIR"
    else
        echo "未找到已安装的项目，执行全新安装..."
        PROJECT_DIR="/opt/email-sender"
        git clone https://github.com/YinGakki/email-bulk-sender.git "$PROJECT_DIR"
        cd "$PROJECT_DIR"
        chmod +x install.sh start.sh
        ./install.sh
        exit 0
    fi
fi

cd "$PROJECT_DIR"
echo "项目目录: $PROJECT_DIR"
echo ""

# 1. 停止服务
echo "[1/5] 停止服务..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
pkill -f "python.*app.py" 2>/dev/null || true
echo "完成"
echo ""

# 2. 备份数据库
echo "[2/5] 备份数据库..."
if [ -f "email_sender.db" ]; then
    cp email_sender.db "email_sender.db.bak.$(date +%Y%m%d%H%M%S)"
    echo "数据库已备份"
else
    echo "无数据库文件，跳过"
fi
echo ""

# 3. 拉取最新代码
echo "[3/5] 拉取最新代码..."
git fetch origin
git reset --hard origin/main
echo "完成"
echo ""

# 4. 安装依赖和迁移
echo "[4/5] 安装依赖和执行迁移..."
if [ -d "venv" ]; then
    source venv/bin/activate
else
    python3 -m venv venv
    source venv/bin/activate
fi
pip install -r requirements.txt -q
python migrate.py
echo "完成"
echo ""

# 5. 启动服务
echo "[5/5] 启动服务..."
chmod +x start.sh

if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    systemctl daemon-reload
    systemctl start "$SERVICE_NAME"
    sleep 2
    systemctl status "$SERVICE_NAME" --no-pager || true
    echo ""
    echo "服务已通过 systemd 启动"
else
    nohup ./start.sh > /tmp/email-sender.log 2>&1 &
    sleep 2
    echo "服务已后台启动（日志: /tmp/email-sender.log）"
fi

echo ""
echo "=========================================="
echo "更新完成！"
echo "=========================================="
echo ""
echo "验证服务状态："
echo "  curl -I http://127.0.0.1:5000"
echo ""
echo "查看日志："
echo "  journalctl -u $SERVICE_NAME -n 50 -f"
echo ""
echo "访问地址："
echo "  https://hermes-txyun.ying.host"
echo ""
