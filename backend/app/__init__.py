import json
import logging
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()


def create_app(config_name='default'):
    from app.config import config_by_name

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    CORS(app)

    db.init_app(app)

    _setup_logging(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _ensure_directories(app)
    _start_file_cleanup(app)

    with app.app_context():
        from app.models.ssh_config import SshConfig
        from app.models.database import DatabaseConnection
        from app.models.script import Script
        from app.models.query_task import QueryTask
        from app.models.auto_export_task import AutoExportTask
        from app.models.system_config import SystemConfig
        from app.models.role import Role
        from app.models.user import User
        from app.models.ai_config import AiConfig
        from app.models.user_behavior import UserBehavior
        from app.models.ai_skill import AiSkill
        from app.models.ai_chat import AiChat, AiChatMessage
        from app.models.business_system import BusinessSystem
        from app.models.system_task import SystemTask, SystemTaskExecution
        from app.models.ai_strategy import AiStrategy
        from app.models.tool_memory import ToolMemory
        db.create_all()
        _auto_migrate(app)
        _init_default_admin(app)
        _init_connection_pool(app)

    _start_auto_export_scheduler(app)

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'ok', 'message': 'Excel Database Query API is running'})

    return app


def _setup_logging(app):
    from logging.handlers import TimedRotatingFileHandler

    log_dir = app.config.get('LOG_FOLDER', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_file = os.path.join(log_dir, 'app.log')

    # Windows-friendly timed rotating file handler
    class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # 确保converter属性存在（Python 3.13兼容）
            if not hasattr(self, 'converter'):
                import time as _time
                self.converter = _time.localtime

        def doRollover(self):
            """Override to handle Windows file locking during rotation."""
            if self.stream:
                self.stream.close()
                self.stream = None

            # Get the time for the new filename
            import time as _time
            currentTime = int(self.rolloverAt - self.interval)
            converter = getattr(self, 'converter', _time.localtime)
            fileTime = converter(currentTime)
            dfn = self.rotation_filename(self.baseFilename + "." +
                                         _time.strftime(self.suffix, fileTime))

            # 如果当前日志文件不存在，跳过轮转直接重新打开
            if not os.path.exists(self.baseFilename):
                if not self.delay:
                    self.stream = self._open()
                newRolloverAt = self.computeRollover(currentTime + self.interval)
                while newRolloverAt <= currentTime:
                    newRolloverAt = newRolloverAt + self.interval
                self.rolloverAt = newRolloverAt
                return

            # Retry rename with delay for Windows file locking
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    self.rotate(self.baseFilename, dfn)
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        _time.sleep(0.5)
                    else:
                        # Give up on rotation, reopen original file
                        pass

            # Clean up old log files
            if self.backupCount > 0:
                for s in self.getFilesToDelete(self.baseFilename):
                    try:
                        os.remove(s)
                    except (PermissionError, OSError):
                        pass

            # Reopen the log file
            if not self.delay:
                self.stream = self._open()

            # Update next rollover time
            newRolloverAt = self.computeRollover(currentTime + self.interval)
            while newRolloverAt <= currentTime:
                newRolloverAt = newRolloverAt + self.interval
            self.rolloverAt = newRolloverAt

    # 按天分割日志，保留30天
    file_handler = SafeTimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=30, encoding='utf-8'
    )
    file_handler.suffix = '%Y-%m-%d.log'
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('paramiko').setLevel(logging.ERROR)
    logging.getLogger('sshtunnel').setLevel(logging.ERROR)


def _register_blueprints(app):
    from app.routes.ssh_routes import ssh_bp
    from app.routes.database_routes import database_bp
    from app.routes.script_routes import script_bp
    from app.routes.query_routes import query_bp
    from app.routes.download_routes import download_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.user_routes import user_bp
    from app.routes.role_routes import role_bp
    from app.routes.export_routes import export_bp
    from app.routes.auto_export_routes import auto_export_bp
    from app.routes.system_routes import system_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.business_system_routes import business_bp
    from app.routes.system_task_routes import system_task_bp
    from app.routes.ai_strategy_routes import ai_strategy_bp
    from app.routes.lookup_routes import lookup_bp

    app.register_blueprint(ssh_bp)
    app.register_blueprint(database_bp)
    app.register_blueprint(script_bp)
    app.register_blueprint(query_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(auto_export_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(system_task_bp)
    app.register_blueprint(ai_strategy_bp)
    app.register_blueprint(lookup_bp)


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'message': '资源不存在'}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'success': False, 'message': '请求无效'}), 400

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({'success': False, 'message': '文件过大'}), 413


def _ensure_directories(app):
    for key in ['UPLOAD_FOLDER', 'OUTPUT_FOLDER', 'LOG_FOLDER']:
        folder = app.config.get(key)
        if folder:
            os.makedirs(folder, exist_ok=True)


def _start_file_cleanup(app):
    from app.utils.file_cleanup import start_cleanup_scheduler
    start_cleanup_scheduler(app)


def _start_auto_export_scheduler(app):
    from app.services.auto_export_scheduler import start_auto_export_scheduler
    start_auto_export_scheduler(app)


def _auto_migrate(app):
    with app.app_context():
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)

        type_map = {
            'Integer': 'INTEGER',
            'BigInteger': 'BIGINT',
            'SmallInteger': 'SMALLINT',
            'String': 'VARCHAR(255)',
            'Text': 'TEXT',
            'Unicode': 'VARCHAR(255)',
            'UnicodeText': 'TEXT',
            'Boolean': 'BOOLEAN',
            'Float': 'FLOAT',
            'Numeric': 'NUMERIC',
            'Date': 'DATE',
            'DateTime': 'DATETIME',
            'Time': 'TIME',
            'LargeBinary': 'BLOB',
            'JSON': 'TEXT',
        }

        for mapper in db.Model.registry.mappers:
            table = mapper.local_table
            if table is None:
                continue
            table_name = table.name
            if not inspector.has_table(table_name):
                continue
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}

            for column in table.columns:
                if column.name in existing_columns:
                    continue
                col_type = type_map.get(type(column.type).__name__, 'TEXT')
                if column.primary_key:
                    col_type = 'INTEGER PRIMARY KEY AUTOINCREMENT' if column.autoincrement else 'INTEGER PRIMARY KEY'
                else:
                    if column.foreign_keys:
                        fk = list(column.foreign_keys)[0]
                        ref_col = fk.column
                        col_type = f'INTEGER REFERENCES {ref_col.table.name}({ref_col.name})'
                    if not column.nullable and not column.primary_key:
                        col_type += ' NOT NULL'
                    if column.default is not None and hasattr(column.default, 'arg'):
                        default_val = column.default.arg
                        if not callable(default_val):
                            if isinstance(default_val, bool):
                                col_type += f' DEFAULT {1 if default_val else 0}'
                            elif isinstance(default_val, str):
                                col_type += f" DEFAULT '{default_val}'"
                            elif default_val is not None:
                                col_type += f' DEFAULT {default_val}'
                try:
                    db.session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}'))
                    db.session.commit()
                    app.logger.info(f'Migration: added column {table_name}.{column.name} ({col_type})')
                except Exception as e:
                    db.session.rollback()
                    app.logger.warning(f'Migration failed for {table_name}.{column.name}: {e}')


def _init_default_admin(app):
    from app.models.role import Role
    from app.models.user import User
    admin_role = Role.query.filter_by(is_admin=True).first()
    if not admin_role:
        admin_role = Role(
            name='超级管理员',
            description='系统超级管理员，拥有所有权限',
            is_admin=True,
            menu_permissions='["dashboard","databases","scripts","query","exports","export_exec","auto_export","history","users","roles","system","ai_chat","skills","business_systems","system_tasks"]',
            button_permissions='["all"]',
        )
        db.session.add(admin_role)
        db.session.commit()
    else:
        # 确保管理员角色包含新菜单权限
        try:
            menus = json.loads(admin_role.menu_permissions) if admin_role.menu_permissions else []
            new_menus = ['ai_chat', 'skills', 'business_systems', 'system_tasks']
            updated = False
            for m in new_menus:
                if m not in menus:
                    menus.append(m)
                    updated = True
            if updated:
                admin_role.menu_permissions = json.dumps(menus)
                db.session.commit()
        except Exception:
            pass
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            display_name='管理员',
            role_id=admin_role.id,
            is_active=True,
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()


def _init_connection_pool(app):
    """启动时预建立SSH隧道和数据库连接池"""
    try:
        from app.utils.connection_pool import ConnectionPoolManager
        pool = ConnectionPoolManager.get_instance()
        pool.initialize(app)
    except Exception as e:
        app.logger.warning(f'连接池初始化失败（将在首次请求时建立连接）: {e}')
