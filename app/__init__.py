from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

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

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.services.google_service import init_google_oauth
    init_google_oauth(app)

    from app.auth.routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from app.planner.routes import planner as planner_blueprint
    app.register_blueprint(planner_blueprint)

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
        except Exception as e:
            app.logger.error(f"Auto-migration check notice: {e}")

    return app


