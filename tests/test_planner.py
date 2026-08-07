import unittest
from datetime import date
from app import create_app, db
from app.models import User, DailyPlan, MonthlyPlan, YearlyPlan, WeeklyPlan
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False

class PlannerTestCase(unittest.TestCase):
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

    def test_user_registration_and_login(self):
        res = self.register_and_login()
        self.assertEqual(res.status_code, 200)
        user = User.query.filter_by(username='testuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'test@example.com')

    def test_case_insensitive_login(self):
        self.client.post('/auth/register', data={
            'username': 'JohnDoe',
            'email': 'John@Example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)

        # Login with lowercase username
        res1 = self.client.post('/auth/login', data={'login_input': 'johndoe', 'password': 'password123'}, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        # Login with uppercase email
        res2 = self.client.post('/auth/login', data={'login_input': 'JOHN@EXAMPLE.COM', 'password': 'password123'}, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

    def test_daily_plan_creation_and_task_toggle(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')
        
        # Add task via form
        res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'add_task',
            'task_text': 'Write unit test suite',
            'priority': 'High'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify task in DB
        user = User.query.filter_by(username='testuser').first()
        plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.tasks), 1)
        task_id = plan.tasks[0]['id']
        self.assertFalse(plan.tasks[0]['completed'])

        # Toggle task via AJAX API endpoint
        toggle_res = self.client.post('/api/daily/task/toggle', json={
            'date': today_str,
            'task_id': task_id
        })
        self.assertEqual(toggle_res.status_code, 200)
        data = toggle_res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['completed'])

        # Query database afresh to ensure flag_modified saved JSON change
        db.session.expire_all()
        updated_plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertTrue(updated_plan.tasks[0]['completed'])

    def test_monthly_habit_matrix_toggle(self):
        self.register_and_login()
        today = date.today()
        
        # Add habit via form
        res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'add_habit',
            'habit_name': 'Read 20 mins'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        user = User.query.filter_by(username='testuser').first()
        monthly_plan = MonthlyPlan.query.filter_by(user_id=user.id, year=today.year, month=today.month).first()
        self.assertIsNotNone(monthly_plan)
        self.assertEqual(len(monthly_plan.habits), 1)
        habit_id = monthly_plan.habits[0]['id']

        # Toggle habit day via AJAX API endpoint
        toggle_res = self.client.post('/api/monthly/habit/toggle', json={
            'year': today.year,
            'month': today.month,
            'habit_id': habit_id,
            'day': 5
        })
        self.assertEqual(toggle_res.status_code, 200)
        data = toggle_res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['checked'])

        # Verify JSON persistence in DB
        db.session.expire_all()
        updated_monthly_plan = MonthlyPlan.query.filter_by(user_id=user.id, year=today.year, month=today.month).first()
        self.assertIn(5, updated_monthly_plan.habits[0]['completed_days'])

    def test_yearly_resolutions_and_objectives(self):
        self.register_and_login()
        today = date.today()

        # Add resolution
        self.client.post(f'/yearly?year={today.year}', data={
            'action': 'add_resolution',
            'resolution_text': 'Run marathon',
            'category': 'Health'
        }, follow_redirects=True)

        user = User.query.filter_by(username='testuser').first()
        yearly_plan = YearlyPlan.query.filter_by(user_id=user.id, year=today.year).first()
        self.assertIsNotNone(yearly_plan)
        self.assertEqual(len(yearly_plan.resolutions), 1)
        self.assertEqual(yearly_plan.resolutions[0]['text'], 'Run marathon')

    def test_monthly_calendar_item_and_sticker(self):
        self.register_and_login()
        today = date.today()

        # Add calendar item with sticker
        res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'add_calendar_item',
            'day': '15',
            'item_text': 'Submit Q3 Deliverables',
            'item_type': 'deadline',
            'sticker': '🚀'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        user = User.query.filter_by(username='testuser').first()
        monthly_plan = MonthlyPlan.query.filter_by(user_id=user.id, year=today.year, month=today.month).first()
        self.assertIsNotNone(monthly_plan)
        self.assertIn('15', monthly_plan.calendar_days)
        day_15 = monthly_plan.calendar_days['15']
        self.assertEqual(day_15['sticker'], '🚀')
        self.assertEqual(len(day_15['items']), 1)
        self.assertEqual(day_15['items'][0]['text'], 'Submit Q3 Deliverables')

    def test_daily_12h_schedule_and_mood_tracking(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Save 12h schedule with mood tracking
        res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'save_schedule',
            'slot_act_09_00_AM': 'Deep Work & Strategy Sync',
            'slot_mood_09_00_AM': '😄',
            'slot_act_02_00_PM': 'Team Retrospective',
            'slot_mood_02_00_PM': '😊'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        user = User.query.filter_by(username='testuser').first()
        daily_plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(daily_plan)
        self.assertIn('09:00 AM', daily_plan.schedule)
        self.assertEqual(daily_plan.schedule['09:00 AM']['activity'], 'Deep Work & Strategy Sync')
        self.assertEqual(daily_plan.schedule['09:00 AM']['mood'], '😄')
        self.assertEqual(daily_plan.schedule['02:00 PM']['activity'], 'Team Retrospective')
        self.assertEqual(daily_plan.schedule['02:00 PM']['mood'], '😊')

    def test_depression_episode_logging(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Log a depression episode
        res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'add_depression_episode',
            'start_time': '08:30 AM',
            'duration': '45 mins',
            'intensity': '6',
            'triggers': 'Work Overwhelm & Sleep Deprivation',
            'coping_mechanism': 'Box breathing & 15m outdoor walk',
            'coping_effectiveness': 'Very Helpful',
            'notes': 'Heavy feeling in morning, walked outside and felt better.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        user = User.query.filter_by(username='testuser').first()
        daily_plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(daily_plan)
        self.assertIsNotNone(daily_plan.depression_episodes)
        self.assertEqual(len(daily_plan.depression_episodes), 1)

        ep = daily_plan.depression_episodes[0]
        self.assertEqual(ep['start_time'], '08:30 AM')
        self.assertEqual(ep['duration'], '45 mins')
        self.assertEqual(ep['intensity'], 6)
        self.assertEqual(ep['coping_mechanism'], 'Box breathing & 15m outdoor walk')
        self.assertEqual(ep['coping_effectiveness'], 'Very Helpful')

        # Test episode deletion
        ep_id = ep['id']
        del_res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'delete_depression_episode',
            'episode_id': ep_id
        }, follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

        daily_plan_updated = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertEqual(len(daily_plan_updated.depression_episodes), 0)

    def test_weekly_plan_actions(self):
        self.register_and_login()
        
        # 1. Add Weekly Goal
        res = self.client.post('/weekly', data={
            'action': 'add_weekly_goal',
            'goal_title': 'Launch MVP feature set'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 2. Add Daily To-do
        res = self.client.post('/weekly', data={
            'action': 'add_daily_todo',
            'day_abbr': 'Mon',
            'todo_text': 'Morning Cardio Workout'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 3. Add Shopping Item
        res = self.client.post('/weekly', data={
            'action': 'add_shopping_item',
            'item_name': 'Almond Milk',
            'category': 'Groceries'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 4. Save Meals Menu
        res = self.client.post('/weekly', data={
            'action': 'save_meals_menu',
            'meal_bf_Mon': 'Oatmeal & Berries',
            'meal_lu_Mon': 'Chicken Salad',
            'meal_dn_Mon': 'Grilled Salmon'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB state
        user = User.query.filter_by(username='testuser').first()
        year, week_num, _ = date.today().isocalendar()
        weekly_plan = WeeklyPlan.query.filter_by(user_id=user.id, year=year, week_number=week_num).first()
        self.assertIsNotNone(weekly_plan)
        self.assertEqual(len(weekly_plan.goals), 1)
        self.assertEqual(weekly_plan.goals[0]['title'], 'Launch MVP feature set')
        self.assertEqual(len(weekly_plan.daily_todos['Mon']), 1)
        self.assertEqual(weekly_plan.daily_todos['Mon'][0]['text'], 'Morning Cardio Workout')
        self.assertEqual(len(weekly_plan.shopping_list), 1)
        self.assertEqual(weekly_plan.shopping_list[0]['item'], 'Almond Milk')
        self.assertEqual(weekly_plan.meals_menu['Mon']['breakfast'], 'Oatmeal & Berries')

    def test_dashboard_depression_summary(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Log episode
        self.client.post(f'/daily?date={today_str}', data={
            'action': 'add_depression_episode',
            'start_time': '09:00 AM',
            'duration': '30 mins',
            'intensity': '7',
            'triggers': 'Stress',
            'coping_mechanism': 'Deep Breathing',
            'coping_effectiveness': 'Very Helpful',
            'notes': 'Felt much calmer.'
        }, follow_redirects=True)

        # Load Dashboard
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Depression Tracker Summary', res.data)
        self.assertIn(b'Deep Breathing', res.data)

    def test_summary_cascade_daily_weekly_monthly_yearly(self):
        self.register_and_login()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        year = today.year
        month = today.month

        # 1. Add Daily Plan task
        self.client.post(f'/daily?date={today_str}', data={
            'action': 'add_task',
            'task_text': 'Daily Sprint Task',
            'priority': 'High'
        }, follow_redirects=True)

        # 2. Add Monthly Goal
        self.client.post(f'/monthly?year={year}&month={month}', data={
            'action': 'add_goal',
            'goal_title': 'Cascade Test Monthly Goal',
            'category': 'Career'
        }, follow_redirects=True)

        # Verify Weekly page contains Daily summary
        res_weekly = self.client.get('/weekly')
        self.assertEqual(res_weekly.status_code, 200)
        self.assertIn(b'Daily Plans Summary Cascade', res_weekly.data)

        # Verify Monthly page contains Weekly summary
        res_monthly = self.client.get(f'/monthly?year={year}&month={month}')
        self.assertEqual(res_monthly.status_code, 200)
        self.assertIn(b'Weekly Summaries Cascade', res_monthly.data)

        # Verify Yearly page contains 12-Month Achievement Grid
        res_yearly = self.client.get(f'/yearly?year={year}')
        self.assertEqual(res_yearly.status_code, 200)
        self.assertIn(b'12-Month Achievement Overview', res_yearly.data)
        self.assertIn(b'Cascade Test Monthly Goal', res_monthly.data)

    def test_excel_exports_all_planners(self):
        self.register_and_login()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        year, week_num, _ = today.isocalendar()

        # 1. Daily Excel Export
        res_daily = self.client.get(f'/daily/export_excel?date={today_str}')
        self.assertEqual(res_daily.status_code, 200)
        self.assertEqual(res_daily.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # 2. Weekly Excel Export
        res_weekly = self.client.get(f'/weekly/export_excel?year={year}&week={week_num}')
        self.assertEqual(res_weekly.status_code, 200)
        self.assertEqual(res_weekly.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # 3. Monthly Excel Export
        res_monthly = self.client.get(f'/monthly/export_excel?year={year}&month={today.month}')
        self.assertEqual(res_monthly.status_code, 200)
        self.assertEqual(res_monthly.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # 4. Yearly Excel Export
        res_yearly = self.client.get(f'/yearly/export_excel?year={year}')
        self.assertEqual(res_yearly.status_code, 200)
        self.assertEqual(res_yearly.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_google_drive_folder_selection_api(self):
        self.register_and_login()

        # 1. Fetch Drive folders list
        res = self.client.get('/api/google/drive/folders')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('folders', data)

        # 2. Select existing folder
        res_sel = self.client.post('/api/google/drive/folder_settings', json={
            'action': 'select',
            'folder_id': 'folder_123',
            'folder_name': 'My Backup Vault'
        })
        self.assertEqual(res_sel.status_code, 200)
        sel_data = res_sel.get_json()
        self.assertTrue(sel_data['success'])
        self.assertEqual(sel_data['folder_name'], 'My Backup Vault')

        # 3. Create new folder
        res_create = self.client.post('/api/google/drive/folder_settings', json={
            'action': 'create',
            'folder_name': 'Chronos Custom Folder'
        })
        self.assertEqual(res_create.status_code, 200)
        create_data = res_create.get_json()
        self.assertTrue(create_data['success'])
        self.assertEqual(create_data['folder_name'], 'Chronos Custom Folder')

if __name__ == '__main__':
    unittest.main()
