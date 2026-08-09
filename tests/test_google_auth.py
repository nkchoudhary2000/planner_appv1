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

    def test_merge_google_account_with_local_registration(self):
        # 1. Create a Google user without local password
        google_user = User(username="GoogleUser", email="user.google@gmail.com", google_id="google_sub_1001")
        db.session.add(google_user)
        db.session.commit()

        # 2. User registers with the exact same email to set a local password
        res = self.client.post('/auth/register', data={
            'username': 'GoogleUserMerged',
            'email': 'user.google@gmail.com',
            'password': 'secretpassword123',
            'confirm_password': 'secretpassword123'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)

        # 3. Verify user in DB is merged (same ID, updated password, google_id intact)
        user = User.query.filter_by(email="user.google@gmail.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.id, google_user.id)
        self.assertEqual(user.username, "GoogleUserMerged")
        self.assertEqual(user.google_id, "google_sub_1001")
        self.assertTrue(user.check_password("secretpassword123"))

        # 4. Logout and verify logging in via local password works!
        self.client.get('/auth/logout')
        login_res = self.client.post('/auth/login', data={
            'login_input': 'user.google@gmail.com',
            'password': 'secretpassword123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b'Welcome back', login_res.data)

    def test_google_login_merges_into_existing_local_user(self):
        # 1. Create a local account first
        local_user = User(username="LocalUser", email="user.google@gmail.com")
        local_user.set_password("localpass123")
        db.session.add(local_user)
        db.session.commit()

        # 2. User logs in via Google
        res = self.client.get('/auth/google/login', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 3. Verify user has both password and google_id linked
        user = User.query.filter_by(email="user.google@gmail.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.id, local_user.id)
        self.assertEqual(user.google_id, "mock_google_id_12345")
        self.assertTrue(user.check_password("localpass123"))

if __name__ == '__main__':
    unittest.main()
