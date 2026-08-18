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

class APITokenTestCase(unittest.TestCase):
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

    def register_and_login(self, username="tokenuser", email="token@example.com", password="password123"):
        self.client.post('/auth/register', data={
            'username': username,
            'email': email,
            'password': password,
            'confirm_password': password
        }, follow_redirects=True)

        return self.client.post('/auth/login', data={
            'login_input': username,
            'password': password
        }, follow_redirects=True)

    def test_generate_and_revoke_api_token(self):
        """Test API endpoints for generating, inspecting, and revoking API tokens."""
        self.register_and_login()

        # 1. Initially no token
        info_res = self.client.get('/auth/api-token-info')
        self.assertEqual(info_res.status_code, 200)
        data = info_res.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['has_token'])

        # 2. Generate token
        gen_res = self.client.post('/auth/generate-api-token')
        self.assertEqual(gen_res.status_code, 200)
        gen_data = gen_res.get_json()
        self.assertTrue(gen_data['success'])
        self.assertTrue(gen_data['api_token'].startswith('cp_'))
        self.assertIsNotNone(gen_data['masked_token'])

        # Check DB
        user = User.query.filter_by(username='tokenuser').first()
        self.assertEqual(user.api_token, gen_data['api_token'])

        # 3. Inspect token info
        info_res2 = self.client.get('/auth/api-token-info')
        self.assertEqual(info_res2.status_code, 200)
        data2 = info_res2.get_json()
        self.assertTrue(data2['has_token'])
        self.assertEqual(data2['masked_token'], user.get_masked_api_token())

        # 4. Revoke token
        rev_res = self.client.post('/auth/revoke-api-token')
        self.assertEqual(rev_res.status_code, 200)
        rev_data = rev_res.get_json()
        self.assertTrue(rev_data['success'])

        user_after = User.query.filter_by(username='tokenuser').first()
        self.assertIsNone(user_after.api_token)

    def test_api_authentication_via_bearer_header(self):
        """Test accessing protected endpoints using Authorization: Bearer <token>."""
        # Create user and generate token
        self.register_and_login()
        gen_res = self.client.post('/auth/generate-api-token')
        raw_token = gen_res.get_json()['api_token']

        # Use fresh unauthenticated client to simulate external REST API client request
        api_client = self.app.test_client()
        with api_client.session_transaction() as sess:
            sess.clear()

        # Access protected endpoint with Bearer header
        headers = {'Authorization': f'Bearer {raw_token}'}
        res = api_client.get('/auth/api-token-info', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['has_token'])

    def test_api_authentication_via_x_api_token_header(self):
        """Test accessing protected endpoints using X-API-Token: <token>."""
        self.register_and_login()
        gen_res = self.client.post('/auth/generate-api-token')
        raw_token = gen_res.get_json()['api_token']

        # Use fresh unauthenticated client
        api_client = self.app.test_client()
        with api_client.session_transaction() as sess:
            sess.clear()

        # Access protected endpoint with X-API-Token header
        headers = {'X-API-Token': raw_token}
        res = api_client.get('/auth/api-token-info', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_api_authentication_via_query_parameter(self):
        """Test accessing protected endpoints using ?api_token=<token>."""
        self.register_and_login()
        gen_res = self.client.post('/auth/generate-api-token')
        raw_token = gen_res.get_json()['api_token']

        # Use fresh unauthenticated client
        api_client = self.app.test_client()
        with api_client.session_transaction() as sess:
            sess.clear()

        # Access protected endpoint with query parameter
        res = api_client.get(f'/auth/api-token-info?api_token={raw_token}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

    def test_revoked_token_denies_access(self):
        """Test that a revoked token fails to authenticate requests."""
        self.register_and_login()
        gen_res = self.client.post('/auth/generate-api-token')
        raw_token = gen_res.get_json()['api_token']

        # Revoke token and logout session completely
        self.client.post('/auth/revoke-api-token')
        self.client.get('/auth/logout')
        with self.client.session_transaction() as sess:
            sess.clear()

        # Use fresh unauthenticated client
        api_client = self.app.test_client()
        with api_client.session_transaction() as sess:
            sess.clear()

        # Attempt access with revoked token
        headers = {'Authorization': f'Bearer {raw_token}'}
        res = api_client.get('/auth/api-token-info', headers=headers)
        # Should redirect to login page (302) because unauthenticated
        self.assertEqual(res.status_code, 302)

    def test_daily_today_tasks_json_api(self):
        """Test retrieving today's planned tasks as JSON using API token authentication."""
        self.register_and_login(username="dailyuser", email="daily@example.com")
        gen_res = self.client.post('/auth/generate-api-token')
        raw_token = gen_res.get_json()['api_token']

        # Add a task first
        self.client.post('/daily', data={
            'action': 'add_task',
            'task_text': 'Build API Endpoint',
            'priority': 'High'
        })

        api_client = self.app.test_client()
        with api_client.session_transaction() as sess:
            sess.clear()

        headers = {'Authorization': f'Bearer {raw_token}'}

        # 1. Test dedicated /api/daily/today endpoint
        res = api_client.get('/api/daily/today', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('tasks', data)
        self.assertEqual(len(data['tasks']), 1)
        self.assertEqual(data['tasks'][0]['text'], 'Build API Endpoint')

        # 2. Test /daily?format=json endpoint
        res2 = api_client.get('/daily?format=json', headers=headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertTrue(data2['success'])
        self.assertEqual(len(data2['tasks']), 1)

if __name__ == '__main__':
    unittest.main()
