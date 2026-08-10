import unittest
from datetime import date
from app import create_app, db
from app.models import User, DailyPlan, MonthlyPlan, YearlyPlan, WeeklyPlan
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False

class NewFeaturesTestCase(unittest.TestCase):
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

    def register_and_login(self, username="testuser", email="test@example.com", password="password123"):
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

    def test_yearly_planner_entries(self):
        """Feature 1: Test creating, toggling, and deleting yearly entries (goals, birthdays, anniversaries, date events)."""
        self.register_and_login()

        # Add a Birthday event
        res = self.client.post('/yearly?year=2026', data={
            'action': 'add_yearly_event',
            'event_title': "Alice's Birthday",
            'event_type': 'birthday',
            'event_date': '2026-08-15',
            'notes': 'Buy cake'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify event in DB
        user = User.query.filter_by(username='testuser').first()
        yearly_plan = YearlyPlan.query.filter_by(user_id=user.id, year=2026).first()
        self.assertIsNotNone(yearly_plan)
        self.assertEqual(len(yearly_plan.events), 1)
        event = yearly_plan.events[0]
        self.assertEqual(event['title'], "Alice's Birthday")
        self.assertEqual(event['event_type'], 'birthday')
        self.assertEqual(event['date'], '2026-08-15')
        self.assertFalse(event['completed'])

        # Toggle event completion
        event_id = event['id']
        toggle_res = self.client.post('/yearly?year=2026', data={
            'action': 'toggle_yearly_event',
            'event_id': event_id
        }, follow_redirects=True)
        self.assertEqual(toggle_res.status_code, 200)

        db.session.expire_all()
        updated_plan = YearlyPlan.query.filter_by(user_id=user.id, year=2026).first()
        self.assertTrue(updated_plan.events[0]['completed'])

        # Delete event
        del_res = self.client.post('/yearly?year=2026', data={
            'action': 'delete_yearly_event',
            'event_id': event_id
        }, follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

        db.session.expire_all()
        final_plan = YearlyPlan.query.filter_by(user_id=user.id, year=2026).first()
        self.assertEqual(len(final_plan.events), 0)

    def test_cascading_task_visibility(self):
        """Feature 2: Test top-down hierarchical data visibility across Yearly -> Monthly -> Weekly -> Daily."""
        self.register_and_login()
        user = User.query.filter_by(username='testuser').first()

        # 1. Create Yearly Event for 2026-08-15
        self.client.post('/yearly?year=2026', data={
            'action': 'add_yearly_event',
            'event_title': "Annual Leadership Summit",
            'event_type': 'goal',
            'event_date': '2026-08-15',
            'notes': 'Keynote presentation'
        })

        # 2. Check Monthly view for August 2026
        monthly_res = self.client.get('/monthly?year=2026&month=8')
        self.assertEqual(monthly_res.status_code, 200)
        self.assertIn(b'Annual Leadership Summit', monthly_res.data)

        # 3. Check Daily view for 2026-08-15
        daily_res = self.client.get('/daily?date=2026-08-15')
        self.assertEqual(daily_res.status_code, 200)
        self.assertIn(b'Annual Leadership Summit', daily_res.data)

    def test_dynamic_color_coded_tags(self):
        """Feature 3: Test user dynamic tags CRUD and assigning tags to daily tasks."""
        self.register_and_login()

        # 1. Create a custom tag via API
        tag_res = self.client.post('/api/tags', json={
            'action': 'add',
            'name': 'Client Project',
            'color': '#8b5cf6'
        })
        self.assertEqual(tag_res.status_code, 200)
        tag_data = tag_res.get_json()
        self.assertTrue(tag_data['success'])
        created_tag_id = tag_data['tag']['id']

        # 2. Create task with custom tag
        today_str = date.today().strftime('%Y-%m-%d')
        task_res = self.client.post('/api/daily/task/add', json={
            'date': today_str,
            'text': 'Deliver Client Mockups',
            'priority': 'High',
            'tags': [created_tag_id]
        })
        self.assertEqual(task_res.status_code, 200)
        t_data = task_res.get_json()
        self.assertTrue(t_data['success'])
        self.assertIn(created_tag_id, t_data['task']['tags'])

    def test_auto_dating_weekly_shopping_list(self):
        """Feature 4: Test automatic timestamping (added_date) for weekly shopping items."""
        self.register_and_login()
        today = date.today()
        year, week, _ = today.isocalendar()

        # Add shopping item
        res = self.client.post(f'/weekly?year={year}&week={week}', data={
            'action': 'add_shopping_item',
            'item_name': 'Organic Almond Milk',
            'category': 'Groceries'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify added_date in DB
        user = User.query.filter_by(username='testuser').first()
        weekly_plan = WeeklyPlan.query.filter_by(user_id=user.id, year=year, week_number=week).first()
        self.assertIsNotNone(weekly_plan)
        self.assertEqual(len(weekly_plan.shopping_list), 1)
        item = weekly_plan.shopping_list[0]
        self.assertEqual(item['item'], 'Organic Almond Milk')
        self.assertEqual(item['added_date'], today.strftime('%Y-%m-%d'))

    def test_dashboard_reminder_marquee_alerts(self):
        """Feature 5: Test dashboard reminder panel marquee alert generation."""
        self.register_and_login()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')

        # 1. Add unchecked shopping item
        year, week, _ = today.isocalendar()
        self.client.post(f'/weekly?year={year}&week={week}', data={
            'action': 'add_shopping_item',
            'item_name': 'Fresh Coffee Beans',
            'category': 'Groceries'
        })

        # 2. Add high priority task for today
        self.client.post('/api/daily/task/add', json={
            'date': today_str,
            'text': 'Critical Client Meeting',
            'priority': 'High'
        })

        # 3. Fetch Dashboard and verify active alerts in response HTML
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Active Reminders', dash_res.data)
        self.assertIn(b'Fresh Coffee Beans', dash_res.data)
        self.assertIn(b'Critical Client Meeting', dash_res.data)

    def test_weekly_unbought_shopping_list_move_to_next_week(self):
        """Feature 6: Test that unbought weekly shopping list items are moved to next week and removed from prior week."""
        self.register_and_login()
        user = User.query.filter_by(username='testuser').first()

        # Add 2 shopping items to Week 30: one bought, one unbought
        self.client.post('/weekly?year=2026&week=30', data={
            'action': 'add_shopping_item',
            'item_name': 'Oat Milk (Bought)',
            'category': 'Groceries'
        }, follow_redirects=True)

        self.client.post('/weekly?year=2026&week=30', data={
            'action': 'add_shopping_item',
            'item_name': 'Almond Milk (Unbought)',
            'category': 'Groceries'
        }, follow_redirects=True)

        # Mark Oat Milk as bought
        wp30 = WeeklyPlan.query.filter_by(user_id=user.id, year=2026, week_number=30).first()
        oat_item = next(s for s in wp30.shopping_list if s['item'] == 'Oat Milk (Bought)')
        self.client.post('/weekly?year=2026&week=30', data={
            'action': 'toggle_shopping_item',
            'item_id': oat_item['id']
        })

        # Load Week 31
        res31 = self.client.get('/weekly?year=2026&week=31')
        self.assertEqual(res31.status_code, 200)

        # Verify Week 30 has ONLY Oat Milk (Bought) left
        wp30_updated = WeeklyPlan.query.filter_by(user_id=user.id, year=2026, week_number=30).first()
        self.assertEqual(len(wp30_updated.shopping_list), 1)
        self.assertEqual(wp30_updated.shopping_list[0]['item'], 'Oat Milk (Bought)')

        # Verify Week 31 has Almond Milk (Unbought) moved into it
        wp31 = WeeklyPlan.query.filter_by(user_id=user.id, year=2026, week_number=31).first()
        self.assertIsNotNone(wp31)
        self.assertEqual(len(wp31.shopping_list), 1)
        self.assertEqual(wp31.shopping_list[0]['item'], 'Almond Milk (Unbought)')

    def test_user_profile_update(self):
        """Feature 7: Test updating user display name, username, email, and password."""
        self.register_and_login()
        user = User.query.filter_by(username='testuser').first()

        # Update profile via AJAX
        res = self.client.post('/auth/update-profile', json={
            'display_name': 'Niraj Choudhary',
            'username': 'niraj_updated',
            'email': 'niraj_new@example.com',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['display_name'], 'Niraj Choudhary')
        self.assertEqual(data['user']['name'], 'Niraj Choudhary')
        self.assertEqual(data['user']['username'], 'niraj_updated')
        self.assertEqual(data['user']['email'], 'niraj_new@example.com')

        # Verify DB updates
        updated_user = User.query.filter_by(id=user.id).first()
        self.assertEqual(updated_user.display_name, 'Niraj Choudhary')
        self.assertEqual(updated_user.name, 'Niraj Choudhary')
        self.assertEqual(updated_user.username, 'niraj_updated')
        self.assertEqual(updated_user.email, 'niraj_new@example.com')
        self.assertTrue(updated_user.check_password('newpassword123'))

        # Verify Dashboard reflects display_name
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Niraj Choudhary', dash_res.data)

if __name__ == '__main__':
    unittest.main()
