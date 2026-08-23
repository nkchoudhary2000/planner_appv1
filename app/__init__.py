from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flasgger import Swagger
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

@login_manager.request_loader
def load_user_from_request(request):
    """Securely authenticates incoming HTTP requests via API Token.
    Supports Authorization Bearer/Token header, X-API-Token header, or api_token query param.
    """
    token = None

    # 1. Check Authorization Header (Bearer <token> or Token <token>)
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() in ('bearer', 'token'):
            token = parts[1]
        elif len(parts) == 1 and not parts[0].lower().startswith('basic'):
            token = parts[0]

    # 2. Check X-API-Token header
    if not token:
        token = request.headers.get('X-API-Token')

    # 3. Check Query parameter or Form data
    if not token:
        token = request.args.get('api_token') or request.args.get('token')

    if token:
        from app.models import User
        user = User.query.filter_by(api_token=token).first()
        if user:
            return user

    return None

from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        finally:
            cursor.close()

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Chronos Planner REST API",
        "description": "Comprehensive REST API documentation for Chronos Planner. Authenticate using Bearer Token (Authorization: Bearer <token>) or X-API-Token header.",
        "version": "1.0.0",
        "contact": {
            "name": "Chronos API Team"
        }
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter API token in the format: Bearer <token>"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "X-API-Token",
            "in": "header",
            "description": "Enter API token in X-API-Token header"
        }
    },
    "security": [
        {"Bearer": []},
        {"ApiKeyAuth": []}
    ]
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/"
}

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Enable CORS for all endpoints & allow Authorization / X-API-Token headers
    CORS(app, resources={r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Token", "Accept"]
    }})

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

    from app.services.google_service import init_google_oauth
    init_google_oauth(app)

    from app.auth.routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from app.planner_ui import planner_ui as planner_ui_blueprint
    app.register_blueprint(planner_ui_blueprint)

    from app.planner_api import planner_api as planner_api_blueprint
    app.register_blueprint(planner_api_blueprint)

    from app.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    with app.app_context():
        db.create_all()
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'user' in tables:
                columns = [c['name'] for c in inspector.get_columns('user')]
                if 'custom_tags' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN custom_tags JSON DEFAULT \'[]\''))
                if 'display_name' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN display_name VARCHAR(128) NULL'))
                if 'api_token' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN api_token VARCHAR(128) NULL'))
                if 'api_token_created_at' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text('ALTER TABLE "user" ADD COLUMN api_token_created_at TIMESTAMP NULL'))

            if 'daily_plan' in tables:
                columns = [c['name'] for c in inspector.get_columns('daily_plan')]
                if 'memory_logs' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text("ALTER TABLE daily_plan ADD COLUMN memory_logs JSON DEFAULT '[]'"))
                if 'sleep_log' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text("ALTER TABLE daily_plan ADD COLUMN sleep_log JSON DEFAULT '{}'"))

            if 'yearly_plan' in tables:
                columns = [c['name'] for c in inspector.get_columns('yearly_plan')]
                if 'events' not in columns:
                    with db.engine.begin() as conn:
                        conn.execute(text("ALTER TABLE yearly_plan ADD COLUMN events JSON DEFAULT '[]'"))

            if 'planning_event' not in tables:
                db.create_all()
        except Exception as e:
            app.logger.error(f"Auto-migration check notice: {e}")

    return app


