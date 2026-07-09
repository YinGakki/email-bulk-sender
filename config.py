import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///email_sender.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SMTP配置
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.qq.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SENDER_NAME = os.environ.get('SENDER_NAME', '')

    # 发送配置
    BATCH_SIZE = int(os.environ.get('BATCH_SIZE', 10))  # 每批发送数量
    SEND_INTERVAL = int(os.environ.get('SEND_INTERVAL', 5))  # 批次间隔秒数

    # 访问密码（为空则不启用密码保护）
    ACCESS_PASSWORD = os.environ.get('ACCESS_PASSWORD', '')