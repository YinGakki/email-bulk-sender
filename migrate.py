"""
数据库迁移脚本
用于从旧版本升级时，补齐新增的字段和表
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email_sender.db')


def get_db_path():
    """查找数据库文件"""
    if os.path.exists(DB_PATH):
        return DB_PATH
    # 尝试 instance 目录
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'email_sender.db')
    if os.path.exists(instance_path):
        return instance_path
    return DB_PATH


def column_exists(cursor, table, column):
    """检查字段是否存在"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def table_exists(cursor, table):
    """检查表是否存在"""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    return cursor.fetchone() is not None


def migrate():
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        print("首次运行将自动创建，无需迁移。")
        return True

    print(f"正在迁移数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    changes = []

    # 1. SendTask 表新增 send_separately 字段
    if table_exists(cursor, 'send_task'):
        if not column_exists(cursor, 'send_task', 'send_separately'):
            cursor.execute("ALTER TABLE send_task ADD COLUMN send_separately BOOLEAN DEFAULT 1")
            changes.append("send_task.send_separately")

    # 2. 创建 email_config 表（如果不存在）
    if not table_exists(cursor, 'email_config'):
        cursor.execute("""
            CREATE TABLE email_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                smtp_server VARCHAR(200) DEFAULT 'smtp.qq.com',
                smtp_port INTEGER DEFAULT 587,
                smtp_username VARCHAR(200) DEFAULT '',
                smtp_password VARCHAR(500) DEFAULT '',
                sender_name VARCHAR(200) DEFAULT '',
                batch_size INTEGER DEFAULT 10,
                send_interval INTEGER DEFAULT 5,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        changes.append("email_config 表")

        # 尝试从 .env 导入配置
        try:
            from config import Config
            from dotenv import load_dotenv
            load_dotenv()

            if Config.SMTP_USERNAME:
                cursor.execute("""
                    INSERT INTO email_config
                    (smtp_server, smtp_port, smtp_username, smtp_password, sender_name, batch_size, send_interval)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    Config.SMTP_SERVER,
                    Config.SMTP_PORT,
                    Config.SMTP_USERNAME,
                    Config.SMTP_PASSWORD,
                    Config.SENDER_NAME,
                    Config.BATCH_SIZE,
                    Config.SEND_INTERVAL
                ))
                changes.append("已从 .env 导入邮箱配置")
        except Exception as e:
            print(f"  警告: 从 .env 导入配置失败: {e}")

    # 3. 创建 attachment 表（如果不存在）
    if not table_exists(cursor, 'attachment'):
        cursor.execute("""
            CREATE TABLE attachment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                filename VARCHAR(500) NOT NULL,
                filepath VARCHAR(1000) NOT NULL,
                file_size INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES send_task (id)
            )
        """)
        changes.append("attachment 表")

    conn.commit()
    conn.close()

    if changes:
        print(f"迁移完成，共执行 {len(changes)} 项变更:")
        for c in changes:
            print(f"  - {c}")
    else:
        print("数据库已是最新，无需迁移。")

    return True


if __name__ == '__main__':
    try:
        migrate()
        print("\n迁移成功！可以启动服务了。")
    except Exception as e:
        print(f"\n迁移失败: {e}", file=sys.stderr)
        sys.exit(1)
