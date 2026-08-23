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
        self.assertIn('09:00 - 10:00 AM', daily_plan.schedule)
        self.assertEqual(daily_plan.schedule['09:00 - 10:00 AM']['activity'], 'Deep Work & Strategy Sync')
        self.assertEqual(daily_plan.schedule['09:00 - 10:00 AM']['mood'], '😄')
        self.assertEqual(daily_plan.schedule['02:00 - 03:00 PM']['activity'], 'Team Retrospective')
        self.assertEqual(daily_plan.schedule['02:00 - 03:00 PM']['mood'], '😊')

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

    def test_today_current_defaults_for_all_planners(self):
        self.register_and_login()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        iso_year, iso_week, _ = today.isocalendar()

        # Daily Planner defaults to Today
        res_daily = self.client.get('/daily')
        self.assertEqual(res_daily.status_code, 200)
        self.assertIn(today.strftime('%A, %B %d, %Y').encode(), res_daily.data)

        # Weekly Planner defaults to Current Week
        res_weekly = self.client.get('/weekly')
        self.assertEqual(res_weekly.status_code, 200)
        self.assertIn(f'Week {iso_week}, {iso_year}'.encode(), res_weekly.data)

        # Monthly Planner defaults to Current Month and Year
        res_monthly = self.client.get('/monthly')
        self.assertEqual(res_monthly.status_code, 200)
        self.assertIn(today.strftime('%B %Y').encode(), res_monthly.data)

        # Yearly Planner defaults to Current Year
        res_yearly = self.client.get('/yearly')
        self.assertEqual(res_yearly.status_code, 200)
        self.assertIn(f'Year {today.year}'.encode(), res_yearly.data)

    def test_full_database_local_backup_export_and_restore(self):
        self.register_and_login()
        user = User.query.filter_by(username='testuser').first()
        today = date.today()

        # 1. Create records in DailyPlan
        dp = DailyPlan(
            user_id=user.id,
            date=today,
            schedule={"09:00 - 10:00 AM": {"activity": "Focus Work", "mood": "😄"}},
            tasks=[{"id": "t1", "text": "Finish Feature", "completed": True, "priority": "High"}],
            notes="Daily Note Test",
            depression_episodes=[{"id": "e1", "start_time": "10:00 AM", "duration": "30m", "intensity": 4, "coping_mechanism": "Walk"}]
        )
        db.session.add(dp)

        # 2. Create records in WeeklyPlan
        iso_year, iso_week, _ = today.isocalendar()
        wp = WeeklyPlan(
            user_id=user.id,
            year=iso_year,
            week_number=iso_week,
            start_date=today,
            goals=[{"id": "wg1", "title": "Ship MVP", "completed": True}],
            daily_todos={"Mon": [{"id": "wt1", "text": "Plan Sprint", "completed": True}]},
            shopping_list=[{"id": "ws1", "item": "Coffee", "category": "Groceries", "bought": True}],
            meals_menu={"Mon": {"breakfast": "Oatmeal", "lunch": "Salad", "dinner": "Soup"}},
            notes="Weekly Note Test"
        )
        db.session.add(wp)

        # 3. Create records in MonthlyPlan
        mp = MonthlyPlan(
            user_id=user.id,
            year=today.year,
            month=today.month,
            goals=[{"id": "mg1", "title": "Run 20km", "category": "Fitness"}],
            habits=[{"id": "mh1", "name": "Meditation", "completed_days": [1, 2, 5]}],
            milestones=[{"id": "mm1", "title": "Launch Alpha", "date": "15", "completed": True}],
            calendar_days={"15": {"items": [{"id": "c1", "text": "Key Demo", "type": "target"}], "sticker": "🚀"}},
            notes="Monthly Note Test"
        )
        db.session.add(mp)

        # 4. Create records in YearlyPlan
        yp = YearlyPlan(
            user_id=user.id,
            year=today.year,
            resolutions=[{"id": "yr1", "text": "Read 12 books", "completed": False}],
            objectives=[{"id": "yo1", "title": "Learn Flask", "status": "Done"}],
            reflections="Yearly Reflection Test"
        )
        db.session.add(yp)
        db.session.commit()

        # 5. Export JSON backup via API
        export_res = self.client.get('/api/backup/export_json')
        self.assertEqual(export_res.status_code, 200)
        import json
        payload = json.loads(export_res.data.decode('utf-8'))

        # Verify exported payload contains all 4 tables & nested fields
        self.assertEqual(len(payload['daily_plans']), 1)
        self.assertEqual(len(payload['weekly_plans']), 1)
        self.assertEqual(len(payload['monthly_plans']), 1)
        self.assertEqual(len(payload['yearly_plans']), 1)
        self.assertEqual(payload['daily_plans'][0]['depression_episodes'][0]['coping_mechanism'], "Walk")
        self.assertEqual(payload['weekly_plans'][0]['shopping_list'][0]['item'], "Coffee")
        self.assertEqual(payload['monthly_plans'][0]['calendar_days']['15']['sticker'], "🚀")

        # 6. Clear database records
        DailyPlan.query.filter_by(user_id=user.id).delete()
        WeeklyPlan.query.filter_by(user_id=user.id).delete()
        MonthlyPlan.query.filter_by(user_id=user.id).delete()
        YearlyPlan.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        self.assertEqual(DailyPlan.query.filter_by(user_id=user.id).count(), 0)
        self.assertEqual(WeeklyPlan.query.filter_by(user_id=user.id).count(), 0)

        # 7. Restore via JSON API
        restore_res = self.client.post('/api/backup/restore_json', json=payload)
        self.assertEqual(restore_res.status_code, 200)
        res_data = restore_res.get_json()
        self.assertTrue(res_data['success'])

        # 8. Query database afresh and assert all 4 tables are restored cleanly
        db.session.expire_all()
        restored_dp = DailyPlan.query.filter_by(user_id=user.id, date=today).first()
        self.assertIsNotNone(restored_dp)
        self.assertEqual(restored_dp.tasks[0]['text'], "Finish Feature")
        self.assertEqual(restored_dp.depression_episodes[0]['coping_mechanism'], "Walk")

        restored_wp = WeeklyPlan.query.filter_by(user_id=user.id, year=iso_year, week_number=iso_week).first()
        self.assertIsNotNone(restored_wp)
        self.assertEqual(restored_wp.shopping_list[0]['item'], "Coffee")

        restored_mp = MonthlyPlan.query.filter_by(user_id=user.id, year=today.year, month=today.month).first()
        self.assertIsNotNone(restored_mp)
        self.assertEqual(restored_mp.calendar_days['15']['sticker'], "🚀")

    def test_api_add_and_delete_task(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Add task via AJAX endpoint
        res = self.client.post('/api/daily/task/add', json={
            'date': today_str,
            'text': 'Fast AJAX Task',
            'priority': 'High',
            'is_default': True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        task_id = data['task']['id']
        self.assertEqual(data['task']['text'], 'Fast AJAX Task')

        # Verify DB
        user = User.query.filter_by(username='testuser').first()
        plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.tasks), 1)

        # Delete task via AJAX endpoint
        del_res = self.client.post('/api/daily/task/delete', json={
            'date': today_str,
            'task_id': task_id
        })
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.get_json()
        self.assertTrue(del_data['success'])

        # Verify DB after deletion
        db.session.expire_all()
        plan_after = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertEqual(len(plan_after.tasks), 0)

    def test_api_update_schedule_and_notes(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Update schedule slot via AJAX endpoint
        sched_res = self.client.post('/api/daily/schedule/update', json={
            'date': today_str,
            'slot': '09:00 - 10:00 AM',
            'activity': 'Focused Deep Work',
            'mood': '🤩',
            'is_default': True
        })
        self.assertEqual(sched_res.status_code, 200)
        self.assertTrue(sched_res.get_json()['success'])

        # Update reflection notes via AJAX endpoint
        notes_res = self.client.post('/api/daily/notes/update', json={
            'date': today_str,
            'notes': 'Had a productive coding session.'
        })
        self.assertEqual(notes_res.status_code, 200)
        self.assertTrue(notes_res.get_json()['success'])

        # Verify DB persistence
        user = User.query.filter_by(username='testuser').first()
        plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(plan)
        self.assertEqual(plan.schedule['09:00 - 10:00 AM']['activity'], 'Focused Deep Work')
        self.assertEqual(plan.schedule['09:00 - 10:00 AM']['mood'], '🤩')
        self.assertEqual(plan.notes, 'Had a productive coding session.')

    def test_daily_plan_memory_log(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Log memory slip
        res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'add_memory_log',
            'time': '10:30 AM',
            'item': 'Forgot where car keys were placed',
            'category': 'Item / Belonging',
            'context': 'Overwhelmed / Exhausted',
            'impact': 'Moderate',
            'recovery': 'Remembered later',
            'notes': 'Keep keys in bowl by front door'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check DB
        user = User.query.filter_by(username='testuser').first()
        plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.memory_logs), 1)
        log = plan.memory_logs[0]
        self.assertEqual(log['item'], 'Forgot where car keys were placed')
        self.assertEqual(log['category'], 'Item / Belonging')
        self.assertEqual(log['impact'], 'Moderate')

        # Delete memory log
        log_id = log['id']
        del_res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'delete_memory_log',
            'log_id': log_id
        }, follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)

        db.session.expire_all()
        plan_after = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertEqual(len(plan_after.memory_logs), 0)

    def test_daily_plan_sleep_log(self):
        self.register_and_login()
        today_str = date.today().strftime('%Y-%m-%d')

        # Save sleep log
        res = self.client.post(f'/daily?date={today_str}', data={
            'action': 'save_sleep_log',
            'sleep_hours': '8.0',
            'bedtime': '10:30 PM',
            'wake_time': '06:30 AM',
            'sleep_quality': '9',
            'disruptions': 'Woke up once at 3 AM',
            'notes': 'Read a book before sleep'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check DB
        user = User.query.filter_by(username='testuser').first()
        plan = DailyPlan.query.filter_by(user_id=user.id, date=date.today()).first()
        self.assertIsNotNone(plan)
        self.assertIsNotNone(plan.sleep_log)
        self.assertEqual(plan.sleep_log.get('hours'), 8.0)
        self.assertEqual(plan.sleep_log.get('bedtime'), '10:30 PM')
        self.assertIn(plan.sleep_log.get('wake_time'), ('6:30 AM', '06:30 AM'))
        self.assertEqual(plan.sleep_log.get('quality'), 9)
        self.assertEqual(plan.sleep_log.get('disruptions'), 'Woke up once at 3 AM')

    def test_monthly_remind_me_dashboard_integration(self):
        self.register_and_login()
        today = date.today()

        # Add a monthly plan item for today's day with remind_me=true
        res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'add_calendar_item',
            'day': str(today.day),
            'item_text': 'Project Presentation Review',
            'item_type': 'plan',
            'sticker': '🚀',
            'remind_me': 'true'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check DB persistence
        user = User.query.filter_by(username='testuser').first()
        m_plan = MonthlyPlan.query.filter_by(user_id=user.id, year=today.year, month=today.month).first()
        self.assertIsNotNone(m_plan)
        day_items = m_plan.calendar_days.get(str(today.day), {}).get('items', [])
        self.assertTrue(len(day_items) > 0)
        self.assertTrue(day_items[0].get('remind_me'))

        # Check Monthly view includes the reminder item
        monthly_res = self.client.get(f'/monthly?year={today.year}&month={today.month}')
        self.assertEqual(monthly_res.status_code, 200)
        self.assertIn('Project Presentation Review', monthly_res.get_data(as_text=True))

    def test_yearly_annual_event_dashboard_reminder(self):
        self.register_and_login()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')

        # Add a yearly event scheduled for today
        res = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'add_yearly_event',
            'event_title': 'Annual Company Summit',
            'event_type': 'conference',
            'event_date': today_str,
            'notes': 'Keynote presentation'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check Yearly view shows the event
        yearly_res = self.client.get(f'/yearly?year={today.year}')
        self.assertEqual(yearly_res.status_code, 200)
        self.assertIn('Annual Company Summit', yearly_res.get_data(as_text=True))

    def test_weekly_goals_and_shopping_ajax(self):
        self.register_and_login()
        today = date.today()
        current_year, current_week, _ = today.isocalendar()

        # 1. Add Weekly Goal via AJAX
        res = self.client.post(f'/weekly?year={current_year}&week={current_week}', data={
            'action': 'add_weekly_goal',
            'goal_title': 'Master Flask AJAX',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'add_weekly_goal')
        self.assertIn('goal', data)
        self.assertEqual(data['goal']['title'], 'Master Flask AJAX')
        goal_id = data['goal']['id']

        # 2. Toggle Weekly Goal via AJAX
        t_res = self.client.post(f'/weekly?year={current_year}&week={current_week}', data={
            'action': 'toggle_weekly_goal',
            'goal_id': goal_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(t_res.status_code, 200)
        t_data = t_res.get_json()
        self.assertTrue(t_data['success'])
        self.assertTrue(t_data['completed'])

        # 3. Add Shopping Item via AJAX
        s_res = self.client.post(f'/weekly?year={current_year}&week={current_week}', data={
            'action': 'add_shopping_item',
            'item_name': 'Organic Apples',
            'category': 'Groceries',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(s_res.status_code, 200)
        s_data = s_res.get_json()
        self.assertTrue(s_data['success'])
        self.assertEqual(s_data['item']['item'], 'Organic Apples')
        item_id = s_data['item']['id']

        # 4. Toggle Shopping Item via AJAX
        st_res = self.client.post(f'/weekly?year={current_year}&week={current_week}', data={
            'action': 'toggle_shopping_item',
            'item_id': item_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(st_res.status_code, 200)
        st_data = st_res.get_json()
        self.assertTrue(st_data['success'])
        self.assertTrue(st_data['bought'])

        # 5. Delete Weekly Goal and Shopping Item via AJAX
        d1 = self.client.post(f'/weekly?year={current_year}&week={current_week}', data={
            'action': 'delete_weekly_goal',
            'goal_id': goal_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d1.get_json()['success'])

        d2 = self.client.post(f'/weekly?year={current_year}&week={current_week}', data={
            'action': 'delete_shopping_item',
            'item_id': item_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d2.get_json()['success'])

    def test_monthly_goals_milestones_and_calendar_ajax(self):
        """Test adding, toggling, and deleting monthly goals, milestones, and calendar plans via AJAX."""
        self.register_and_login()
        today = date.today()

        # 1. Add Monthly Goal via AJAX
        res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'add_goal',
            'goal_title': 'Launch Product V2',
            'category': 'Career',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['goal']['title'], 'Launch Product V2')
        goal_id = data['goal']['id']

        # 2. Toggle Monthly Goal via AJAX
        t_res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'toggle_goal_status',
            'goal_id': goal_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(t_res.status_code, 200)
        t_data = t_res.get_json()
        self.assertTrue(t_data['success'])
        self.assertEqual(t_data['status'], 'Completed')

        # 3. Add Milestone via AJAX
        m_res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'add_milestone',
            'milestone_title': 'Code Review Passed',
            'target_day': '15',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(m_res.status_code, 200)
        m_data = m_res.get_json()
        self.assertTrue(m_data['success'])
        self.assertEqual(m_data['milestone']['title'], 'Code Review Passed')
        ms_id = m_data['milestone']['id']

        # 4. Add Calendar Item via AJAX
        c_res = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'add_calendar_item',
            'day': '15',
            'item_text': 'Release Build 1.0',
            'item_type': 'deadline',
            'sticker': '🚀',
            'remind_me': 'true',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(c_res.status_code, 200)
        c_data = c_res.get_json()
        self.assertTrue(c_data['success'])

        # 5. Delete Goal & Milestone via AJAX
        d1 = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'delete_goal',
            'goal_id': goal_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d1.get_json()['success'])

        d2 = self.client.post(f'/monthly?year={today.year}&month={today.month}', data={
            'action': 'delete_milestone',
            'milestone_id': ms_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d2.get_json()['success'])

    def test_yearly_events_resolutions_and_objectives_ajax(self):
        """Test adding, toggling, updating, and deleting yearly events, resolutions, and objectives via AJAX."""
        self.register_and_login()
        today = date.today()

        # 1. Add Yearly Event via AJAX
        res = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'add_yearly_event',
            'event_title': 'Annual Gala 2026',
            'event_type': 'event',
            'event_date': f'{today.year}-12-25',
            'notes': 'Dress code black tie',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['event']['title'], 'Annual Gala 2026')
        ev_id = data['event']['id']

        # 2. Toggle Yearly Event via AJAX
        t_res = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'toggle_yearly_event',
            'event_id': ev_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(t_res.status_code, 200)
        self.assertTrue(t_res.get_json()['success'])

        # 3. Add Resolution via AJAX
        r_res = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'add_resolution',
            'resolution_text': 'Run Half Marathon',
            'category': 'Health',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(r_res.status_code, 200)
        r_data = r_res.get_json()
        self.assertTrue(r_data['success'])
        res_id = r_data['resolution']['id']

        # 4. Add Objective via AJAX
        o_res = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'add_objective',
            'objective_title': 'Expand Market to EU',
            'quarter': 'Q2',
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(o_res.status_code, 200)
        o_data = o_res.get_json()
        self.assertTrue(o_data['success'])
        obj_id = o_data['objective']['id']

        # 5. Delete Event, Resolution, and Objective via AJAX
        d1 = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'delete_yearly_event',
            'event_id': ev_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d1.get_json()['success'])

        d2 = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'delete_resolution',
            'resolution_id': res_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d2.get_json()['success'])

        d3 = self.client.post(f'/yearly?year={today.year}', data={
            'action': 'delete_objective',
            'objective_id': obj_id,
            'is_ajax': 'true'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertTrue(d3.get_json()['success'])

if __name__ == '__main__':
    unittest.main()
