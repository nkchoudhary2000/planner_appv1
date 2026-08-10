import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'planner-app-secret-key-super-secure-2026'
    
    # Handle database URL (Render provides 'postgres://', SQLAlchemy requires 'postgresql://')
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = db_url or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'planner.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configure connect_args based on DB driver (psycopg2 uses connect_timeout, sqlite uses timeout)
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "connect_args": {"timeout": 30}
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "connect_args": {"connect_timeout": 30}
        }


    # Google OAuth2 Credentials
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'MOCK_GOOGLE_CLIENT_ID'
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'MOCK_GOOGLE_CLIENT_SECRET'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Asia/Kolkata')
