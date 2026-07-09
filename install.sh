#!/bin/bash

# 邮件批量发送工具 - 一键安装脚本

set -e

echo "=========================================="
echo "邮件批量发送工具 - 安装脚本"
echo "=========================================="
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "正在安装 Python3..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-venv
    else
        echo "错误：无法自动安装 Python3，请手动安装"
        exit 1
    fi
fi

echo "Python3 版本：$(python3 --version)"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo ""
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 安装依赖
echo ""
echo "安装依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    echo ""
    echo "=========================================="
    echo "请配置邮箱信息"
    echo "=========================================="
    echo ""
    cp .env.example .env
    
    read -p "请输入 QQ 邮箱地址：" email
    read -p "请输入 SMTP 授权码：" password
    read -p "请输入发件人显示名称：" sender_name
    
    sed -i "s|your_qq@qq.com|$email|" .env
    sed -i "s|your_authorization_code|$password|" .env
    sed -i "s|发件人名称|$sender_name|" .env
    
    # 生成随机密钥
    secret_key=$(python3 -c "import secrets; print(secrets.token_hex(24))")
    sed -i "s|your-secret-key-change-this|$secret_key|" .env
    
    echo ""
    echo "配置已保存到 .env 文件"
fi

# 设置启动脚本权限
chmod +x start.sh

echo ""
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "启动命令："
echo "  ./start.sh"
echo ""
echo "或使用 systemd 服务："
echo "  sudo cp email-sender.service /etc/systemd/system/"
echo "  sudo systemctl enable email-sender"
echo "  sudo systemctl start email-sender"
echo ""