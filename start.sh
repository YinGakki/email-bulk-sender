#!/bin/bash

# 邮件批量发送工具 - 启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 .env 文件是否存在
if [ ! -f .env ]; then
    echo "错误：.env 文件不存在"
    echo "请先复制 .env.example 为 .env 并填写配置"
    echo "  cp .env.example .env"
    echo "  vim .env"
    exit 1
fi

# 检查 Python3 是否存在
if ! command -v python3 &> /dev/null; then
    echo "错误：未找到 Python3，请先安装"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "正在创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "检查依赖..."
pip install -q -r requirements.txt

# 启动服务
echo ""
echo "====================================="
echo "邮件批量发送工具已启动"
echo "访问地址：http://0.0.0.0:5000"
echo "====================================="
echo ""

python app.py