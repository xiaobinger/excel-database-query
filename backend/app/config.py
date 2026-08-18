import os
import secrets
from datetime import timedelta
import yaml


def _load_yaml_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yaml')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml_config = _load_yaml_config()

_db_conf = _yaml_config.get('database', {})
_security_conf = _yaml_config.get('security', {})
_storage_conf = _yaml_config.get('storage', {})
_logging_conf = _yaml_config.get('logging', {})

_db_host = os.environ.get('DB_HOST', _db_conf.get('host', 'localhost'))
_db_port = os.environ.get('DB_PORT', _db_conf.get('port', 3306))
_db_name = os.environ.get('DB_NAME', _db_conf.get('name', 'excel_query_db'))
_db_user = os.environ.get('DB_USER', _db_conf.get('username', 'root'))
_db_pass = os.environ.get('DB_PASSWORD', _db_conf.get('password', ''))
_db_charset = _db_conf.get('charset', 'utf8mb4')

DATABASE_URL = f'mysql+pymysql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}?charset={_db_charset}'


class Config:
    # 密钥：优先级 环境变量 > config.yaml > 随机生成（生产环境启动时警告）
    SECRET_KEY = os.environ.get('SECRET_KEY') or _security_conf.get('secret_key') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', DATABASE_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': _db_conf.get('pool_size', 5),
        'max_overflow': _db_conf.get('max_overflow', 10),
        'pool_pre_ping': True,
        'pool_recycle': _db_conf.get('pool_recycle', 3600),
    }
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or _security_conf.get('jwt_secret_key') or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(base_dir, _storage_conf.get('upload_folder', 'uploads').lstrip('./')))
    OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', os.path.join(base_dir, _storage_conf.get('output_folder', 'outputs').lstrip('./')))
    LOG_FOLDER = os.environ.get('LOG_FOLDER', os.path.join(base_dir, _storage_conf.get('log_folder', 'logs').lstrip('./')))
    MAX_CONTENT_LENGTH = _storage_conf.get('max_content_length_mb', 50) * 1024 * 1024
    FILE_RETENTION_HOURS = _storage_conf.get('file_retention_hours', 24)
    ALLOWED_UPLOAD_EXTENSIONS = set(_storage_conf.get('allowed_upload_extensions', ['xlsx', 'xls', 'csv']))
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY') or _security_conf.get('encryption_key') or secrets.token_hex(16)
    LOG_LEVEL = _logging_conf.get('level', 'INFO')
    LOGIN_LOCKOUT_SECONDS = _security_conf.get('login_lockout_minutes', 5) * 60


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig,  # 默认使用生产配置
}
