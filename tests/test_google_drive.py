import unittest
from datetime import date
from app import create_app, db
from app.models import User, DailyPlan, MonthlyPlan, YearlyPlan
from app.services.google_service import export_user_data_payload, import_user_data_payload
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False

class GoogleDriveTestCase(unittest.TestCase):
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

    def register_and_login(self, username="driveuser", email="drive@example.com"):
        self.client.post('/auth/register', data={
            'username': username,
            'email': email,
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        return self.client.post('/auth/login', data={
            'login_input': username,
            'password': 'password123'
        }, follow_redirects=True)

    def test_json_export_payload_structure(self):
        self.register_and_login()
        user = User.query.filter_by(username='driveuser').first()

        # Add Daily Task
        today_str = date.today().strftime('%Y-%m-%d')
        self.client.post(f'/daily?date={today_str}', data={
            'action': 'add_task',
            'task_text': 'Backup data to Google Drive',
            'priority': 'High'
        }, follow_redirects=True)

        payload = export_user_data_payload(user)
        self.assertEqual(payload['app'], 'Chronos Planner')
        self.assertEqual(payload['user']['username'], 'driveuser')
        self.assertEqual(len(payload['daily_plans']), 1)
        self.assertEqual(payload['daily_plans'][0]['tasks'][0]['text'], 'Backup data to Google Drive')

    def test_json_import_restore(self):
        self.register_and_login()
        user = User.query.filter_by(username='driveuser').first()

        mock_payload = {
            "app": "Chronos Planner",
            "user": {"username": "driveuser", "email": "drive@example.com"},
            "daily_plans": [
                {
                    "date": "2026-08-10",
                    "schedule": {"09:00": "Strategy Sync"},
                    "tasks": [{"id": "1", "text": "Restored Task", "completed": True, "priority": "High"}],
                    "notes": "Restored notes"
                }
            ],
            "monthly_plans": [
                {
                    "year": 2026,
                    "month": 8,
                    "goals": [{"id": "g1", "title": "Run 100km", "category": "Health", "status": "Completed"}],
                    "habits": [{"id": "h1", "name": "Morning Walk", "completed_days": [1, 2, 3]}],
                    "milestones": []
                }
            ],
            "yearly_plans": [
                {
                    "year": 2026,
                    "resolutions": [{"id": "r1", "text": "Master Python", "category": "Career", "completed": True}],
                    "objectives": []
                }
            ]
        }

        success = import_user_data_payload(user, mock_payload)
        self.assertTrue(success)

        # Verify DB records
        dp = DailyPlan.query.filter_by(user_id=user.id, date=date(2026, 8, 10)).first()
        self.assertIsNotNone(dp)
        self.assertEqual(dp.tasks[0]['text'], 'Restored Task')
        self.assertEqual(dp.schedule['09:00'], 'Strategy Sync')

        mp = MonthlyPlan.query.filter_by(user_id=user.id, year=2026, month=8).first()
        self.assertIsNotNone(mp)
        self.assertEqual(mp.habits[0]['name'], 'Morning Walk')
        self.assertEqual(mp.habits[0]['completed_days'], [1, 2, 3])

    def test_drive_sync_api_endpoints(self):
        self.register_and_login()
        user = User.query.filter_by(username='driveuser').first()
        user.google_token = {'access_token': 'mock_token'}
        db.session.commit()

        sync_res = self.client.post('/api/google/drive/sync')
        self.assertEqual(sync_res.status_code, 200)
        sync_data = sync_res.get_json()
        self.assertTrue(sync_data['success'])

        restore_res = self.client.post('/api/google/drive/restore')
        self.assertEqual(restore_res.status_code, 200)
        restore_data = restore_res.get_json()
        self.assertTrue(restore_data['success'])

    def test_daily_auto_drive_sync_on_login(self):
        # 1. Register user without Google token
        self.client.post('/auth/register', data={
            'username': 'autosyncuser',
            'email': 'autosync@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        user = User.query.filter_by(username='autosyncuser').first()
        self.assertIsNone(user.last_drive_sync)

        # Login without Google token -> should NOT trigger auto drive sync
        self.client.post('/auth/login', data={
            'login_input': 'autosyncuser',
            'password': 'password123'
        }, follow_redirects=True)

        db.session.expire_all()
        user_no_token = User.query.filter_by(username='autosyncuser').first()
        self.assertIsNone(user_no_token.last_drive_sync)

        # 2. Attach Google token to user (simulate connected Google Account)
        user_no_token.google_token = {'access_token': 'mock_access_token'}
        db.session.commit()

        # Login with connected Google token -> should trigger daily auto drive sync
        login_res = self.client.post('/auth/login', data={
            'login_input': 'autosyncuser',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # Verify last_drive_sync was updated automatically
        db.session.expire_all()
        user_after = User.query.filter_by(username='autosyncuser').first()
        self.assertIsNotNone(user_after.last_drive_sync)

    def test_json_import_full_db_payload(self):
        self.register_and_login(username="fulluser", email="full@example.com")
        user = User.query.filter_by(username='fulluser').first()

        full_db_payload = {
            "app": "Chronos Planner",
            "backup_type": "full_database",
            "total_users": 1,
            "users": [
                {
                    "username": "fulluser",
                    "email": "full@example.com",
                    "custom_tags": [{"id": "t1", "name": "Projects", "color": "#00ff00"}],
                    "daily_plans": [
                        {
                            "date": "2026-08-15",
                            "schedule": {"10:00": "Code Review"},
                            "tasks": [{"id": "t_1", "text": "Full DB Daily Task", "completed": False}]
                        }
                    ],
                    "yearly_plans": [
                        {
                            "year": 2026,
                            "resolutions": [],
                            "events": [{"id": "e1", "title": "Birthday Celebration", "event_type": "birthday", "date": "2026-08-15"}]
                        }
                    ],
                    "planning_tasks": [
                        {
                            "id": 100,
                            "text": "Refactor Backup Module",
                            "priority": "High",
                            "completed": False
                        }
                    ]
                }
            ]
        }

        stats = import_user_data_payload(user, full_db_payload)
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats['daily'], 1)
        self.assertEqual(stats['yearly'], 1)
        self.assertEqual(stats['tasks'], 1)

        # Verify DB items were created
        dp = DailyPlan.query.filter_by(user_id=user.id, date=date(2026, 8, 15)).first()
        self.assertIsNotNone(dp)
        self.assertEqual(dp.tasks[0]['text'], 'Full DB Daily Task')

        yp = YearlyPlan.query.filter_by(user_id=user.id, year=2026).first()
        self.assertIsNotNone(yp)
        self.assertEqual(yp.events[0]['title'], 'Birthday Celebration')

        from app.models import PlanningTask
        pt = PlanningTask.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(pt)
        self.assertEqual(pt.text, 'Refactor Backup Module')

if __name__ == '__main__':
    unittest.main()
