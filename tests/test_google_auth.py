import unittest
from app import create_app, db
from app.models import User
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    GOOGLE_CLIENT_ID = 'MOCK_GOOGLE_CLIENT_ID'
    GOOGLE_CLIENT_SECRET = 'MOCK_GOOGLE_CLIENT_SECRET'

class GoogleAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_mock_google_login_creates_user_without_password_hash(self):
        # Trigger Google OAuth Mock Login route
        response = self.client.get('/auth/google/login', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Verify Google user was created without password_hash and logged in successfully
        user = User.query.filter_by(email="user.google@gmail.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "GoogleUser")
        self.assertIsNone(user.password_hash)
        self.assertIsNotNone(user.google_token)

    def test_user_creation_with_null_password_hash(self):
        user = User(username="OAuthUser", email="oauth@example.com", google_id="google_123456789")
        db.session.add(user)
        db.session.commit()

        queried_user = User.query.filter_by(google_id="google_123456789").first()
        self.assertIsNotNone(queried_user)
        self.assertIsNone(queried_user.password_hash)
        self.assertFalse(queried_user.check_password("any_password"))

if __name__ == '__main__':
    unittest.main()
