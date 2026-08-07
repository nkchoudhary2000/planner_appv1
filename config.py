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

    # Google OAuth2 Credentials
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'MOCK_GOOGLE_CLIENT_ID'
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'MOCK_GOOGLE_CLIENT_SECRET'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
