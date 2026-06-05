from app.routes.database_routes import database_bp
from app.routes.script_routes import script_bp
from app.routes.query_routes import query_bp
from app.routes.download_routes import download_bp
from app.routes.auth_routes import auth_bp
from app.routes.user_routes import user_bp
from app.routes.role_routes import role_bp
from app.routes.ai_routes import ai_bp

__all__ = ['database_bp', 'script_bp', 'query_bp', 'download_bp', 'auth_bp', 'user_bp', 'role_bp', 'ai_bp']
