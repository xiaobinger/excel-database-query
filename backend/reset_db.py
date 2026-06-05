import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db


def reset_database():
    app = create_app()

    with app.app_context():
        print("正在清理旧表...")

        old_tables = ['db_connections', 'sql_scripts', 'execution_logs', 'users']
        for table in old_tables:
            try:
                db.session.execute(db.text(f'DROP TABLE IF EXISTS `{table}`'))
                print(f"  [DROP] {table}")
            except Exception as e:
                print(f"  [SKIP] {table}: {e}")

        db.session.commit()

        print("\n正在清理模型表...")
        from app.models.ssh_config import SshConfig
        from app.models.database import DatabaseConnection
        from app.models.script import Script
        from app.models.query_task import QueryTask

        model_tables = ['query_tasks', 'scripts', 'database_connections', 'ssh_configs']
        for table in model_tables:
            try:
                db.session.execute(db.text(f'DROP TABLE IF EXISTS `{table}`'))
                print(f"  [DROP] {table}")
            except Exception as e:
                print(f"  [SKIP] {table}: {e}")

        db.session.commit()

        print("\n正在重新创建表...")
        db.create_all()
        print("  [OK] 表创建完成")

        result = db.session.execute(db.text('SHOW TABLES'))
        print("\n当前表:")
        for row in result:
            print(f"  {row[0]}")

        print("\n数据库重置完成! 请运行 seed_data.py 初始化数据")


if __name__ == '__main__':
    reset_database()
