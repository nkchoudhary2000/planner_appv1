import unittest
import json
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models import User, MonthlyPlan
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'

class AdvancedHabitsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test user
        self.user = User(username='habituser', email='habituser@example.com')
        self.user.set_password('Secret123!')
        self.token = self.user.generate_api_token()
        db.session.add(self.user)
        db.session.commit()
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_standard_boolean_habit(self):
        """Test creating and toggling a standard checkbox habit."""
        # 1. Add habit
        res = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Morning Walk',
            'habit_type': 'boolean',
            'category': 'Fitness'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        habit_id = data['habit']['id']
        self.assertEqual(data['habit']['type'], 'boolean')

        # 2. Toggle Day 5 ON
        res_toggle = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 5
        })
        self.assertEqual(res_toggle.status_code, 200)
        toggle_data = res_toggle.get_json()
        self.assertTrue(toggle_data['success'])
        self.assertTrue(toggle_data['checked'])

        # Verify in DB
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        self.assertIn(5, plan.habits[0]['completed_days'])

        # 3. Toggle Day 5 OFF
        res_toggle2 = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 5
        })
        self.assertFalse(res_toggle2.get_json()['checked'])
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        self.assertNotIn(5, plan.habits[0]['completed_days'])

    def test_numeric_counter_habit(self):
        """Test creating and incrementing a numeric counter habit (e.g. coffee cups)."""
        # 1. Add Counter Habit: Drink Coffee, Target 2 cups
        res = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Drink Coffee',
            'habit_type': 'counter',
            'unit': 'cups',
            'target_count': 2,
            'category': 'Health'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        habit = data['habit']
        habit_id = habit['id']
        self.assertEqual(habit['type'], 'counter')
        self.assertEqual(habit['unit'], 'cups')
        self.assertEqual(habit['target_count'], 2)

        # 2. Increment Day 1 (+1 cup)
        res_inc = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 1,
            'delta': 1
        })
        d_inc = res_inc.get_json()
        self.assertTrue(d_inc['success'])
        self.assertEqual(d_inc['count'], 1)
        self.assertFalse(d_inc['checked']) # Target is 2, so 1 cup is not yet fully met

        # 3. Increment Day 1 again (+1 -> count is 2)
        res_inc2 = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 1,
            'delta': 1
        })
        d_inc2 = res_inc2.get_json()
        self.assertEqual(d_inc2['count'], 2)
        self.assertTrue(d_inc2['checked']) # Met target 2

        # 4. Explicitly set Day 2 to 4 cups
        res_set = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 2,
            'count': 4
        })
        d_set = res_set.get_json()
        self.assertEqual(d_set['count'], 4)
        self.assertTrue(d_set['checked'])

        # Verify DB structure
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        h_db = plan.habits[0]
        self.assertEqual(h_db['daily_counts']['1'], 2)
        self.assertEqual(h_db['daily_counts']['2'], 4)
        self.assertIn(1, h_db['completed_days'])
        self.assertIn(2, h_db['completed_days'])

    def test_sub_habits_group_habit(self):
        """Test creating and tracking sub-habit checklists (e.g. daily medicines)."""
        # 1. Add Sub-Habits Group: Take Medicine
        res = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Daily Medicine & Supplements',
            'habit_type': 'sub_habits',
            'sub_habits': 'Vitamin D, Omega 3, Iron'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        habit = data['habit']
        habit_id = habit['id']
        self.assertEqual(habit['type'], 'sub_habits')
        self.assertEqual(len(habit['sub_habits']), 3)
        sub1_id = habit['sub_habits'][0]['id']
        sub2_id = habit['sub_habits'][1]['id']
        sub3_id = habit['sub_habits'][2]['id']

        # 2. Toggle Sub-Habit 1 on Day 10
        res_sub1 = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 10,
            'sub_habit_id': sub1_id
        })
        d_sub1 = res_sub1.get_json()
        self.assertTrue(d_sub1['success'])
        self.assertTrue(d_sub1['sub_checked'])
        self.assertEqual(d_sub1['completed_sub_count'], 1)
        self.assertEqual(d_sub1['total_sub_count'], 3)
        self.assertFalse(d_sub1['all_done'])

        # 3. Toggle Sub-Habit 2 and 3 on Day 10
        self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 10,
            'sub_habit_id': sub2_id
        })
        res_sub3 = self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': habit_id,
            'day': 10,
            'sub_habit_id': sub3_id
        })
        d_sub3 = res_sub3.get_json()
        self.assertEqual(d_sub3['completed_sub_count'], 3)
        self.assertTrue(d_sub3['all_done'])
        self.assertTrue(d_sub3['checked'])

        # Verify in DB: Day 10 is in completed_days because all 3 medicines were taken
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        h_db = plan.habits[0]
        self.assertIn(10, h_db['completed_days'])
        self.assertEqual(len(h_db['daily_sub_completions']['10']), 3)

        # 4. Test Manage Sub-Habits (add a 4th medicine)
        res_manage = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'manage_sub_habits',
            'habit_id': habit_id,
            'sub_habits': ['Vitamin D', 'Omega 3', 'Iron', 'Blood Pressure pill']
        })
        self.assertTrue(res_manage.get_json()['success'])
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        self.assertEqual(len(plan.habits[0]['sub_habits']), 4)

    def test_yearly_momentum_data_with_new_habit_types(self):
        """Verify that /api/monthly/habit/momentum-yearly continues to work with all habit types."""
        # Add boolean habit with day 1 done
        self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Walk',
            'habit_type': 'boolean'
        })
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        walk_id = plan.habits[0]['id']
        self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={'year': 2026, 'month': 8, 'habit_id': walk_id, 'day': 1})

        # Add counter habit with day 2 done
        res = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Water',
            'habit_type': 'counter',
            'target_count': 8
        })
        water_id = res.get_json()['habit']['id']
        self.client.post('/api/monthly/habit/toggle', headers=self.headers, json={'year': 2026, 'month': 8, 'habit_id': water_id, 'day': 2, 'count': 8})

        # Query yearly momentum API
        res_momentum = self.client.get('/api/monthly/habit/momentum-yearly?year=2026', headers=self.headers)
        self.assertEqual(res_momentum.status_code, 200)
        data = res_momentum.get_json()
        self.assertTrue(data['success'])
        august_data = next((m for m in data['data'] if m['month'] == 8), None)
        self.assertIsNotNone(august_data)
        self.assertEqual(august_data['total_habits'], 2)
        self.assertEqual(august_data['completed_slots'], 2)

    def test_reorder_habits_move_up_down(self):
        """Test moving a habit up and down in the matrix."""
        # Create 3 habits
        r1 = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={'action': 'add_habit', 'habit_name': 'Habit A', 'habit_type': 'boolean'})
        r2 = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={'action': 'add_habit', 'habit_name': 'Habit B', 'habit_type': 'boolean'})
        r3 = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={'action': 'add_habit', 'habit_name': 'Habit C', 'habit_type': 'boolean'})

        h1_id = r1.get_json()['habit']['id']
        h2_id = r2.get_json()['habit']['id']
        h3_id = r3.get_json()['habit']['id']

        # Move Habit C up
        res_up = self.client.post('/api/monthly/habit/reorder', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': h3_id,
            'direction': 'up'
        })
        self.assertTrue(res_up.get_json()['success'])

        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        names = [h['name'] for h in plan.habits]
        self.assertEqual(names, ['Habit A', 'Habit C', 'Habit B'])

        # Move Habit A down
        res_down = self.client.post('/api/monthly/habit/reorder', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'habit_id': h1_id,
            'direction': 'down'
        })
        self.assertTrue(res_down.get_json()['success'])

        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        names = [h['name'] for h in plan.habits]
        self.assertEqual(names, ['Habit C', 'Habit A', 'Habit B'])

    def test_auto_arrange_habits_type_standard(self):
        """Test auto-arranging habits: Checklists (top) -> Sub-Habits (middle) -> Counters (bottom)."""
        # Create a counter habit first
        self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Coffee',
            'habit_type': 'counter',
            'target_count': 2
        })
        # Create a sub_habits habit second
        self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Medicines',
            'habit_type': 'sub_habits',
            'sub_habits': 'Vit D, Omega 3'
        })
        # Create a boolean habit third
        self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Morning Jog',
            'habit_type': 'boolean'
        })

        # Trigger auto-arrange type_standard
        res_arrange = self.client.post('/api/monthly/habit/reorder', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'arrange_by': 'type_standard'
        })
        self.assertTrue(res_arrange.get_json()['success'])

        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        types = [h.get('type', 'boolean') for h in plan.habits]
        names = [h['name'] for h in plan.habits]
        self.assertEqual(types, ['boolean', 'sub_habits', 'counter'])
        self.assertEqual(names, ['Morning Jog', 'Medicines', 'Coffee'])

    @patch('app.planner_api.fetch_monthly_github_commits')
    def test_sync_github_commits(self, mock_fetch):
        """Test syncing GitHub public commits into the Habit Tracker Matrix."""
        mock_fetch.return_value = {
            'success': True,
            'username': 'nkchoudhary2000',
            'year': 2026,
            'month': 8,
            'daily_counts': {'1': 3, '5': 1, '25': 4},
            'total_commits': 8,
            'active_days': [1, 5, 25],
            'message': 'Synced 8 commits across 3 active days in 8/2026.'
        }

        res = self.client.post('/api/monthly/habit/sync-github', headers=self.headers, json={
            'year': 2026,
            'month': 8,
            'username': 'nkchoudhary2000'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_commits'], 8)
        self.assertEqual(data['active_days'], [1, 5, 25])

        # Verify habit was created in database
        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        gh_habit = next((h for h in plan.habits if h.get('is_github') or h.get('name') == 'GitHub Commits'), None)
        self.assertIsNotNone(gh_habit)
        self.assertEqual(gh_habit['type'], 'counter')
        self.assertEqual(gh_habit['unit'], 'commits')
        self.assertEqual(gh_habit['daily_counts'], {'1': 3, '5': 1, '25': 4})
        self.assertEqual(gh_habit['completed_days'], [1, 5, 25])

        # Verify user model saved github_username
        user = User.query.get(self.user.id)
        self.assertEqual(user.github_username, 'nkchoudhary2000')

    @patch('urllib.request.urlopen')
    def test_fetch_monthly_github_commits_service(self, mock_urlopen):
        """Test the low-level GitHub service parsing of PushEvents."""
        from app.services.github_service import fetch_monthly_github_commits

        fake_events = [
            {
                'type': 'PushEvent',
                'created_at': '2026-08-25T10:00:00Z',
                'payload': {
                    'commits': [{'sha': '111'}, {'sha': '222'}]
                }
            },
            {
                'type': 'PushEvent',
                'created_at': '2026-08-25T14:30:00Z',
                'payload': {
                    'commits': [{'sha': '333'}]
                }
            },
            {
                'type': 'PushEvent',
                'created_at': '2026-08-01T09:15:00Z',
                'payload': {
                    'commits': [{'sha': '444'}, {'sha': '555'}]
                }
            },
            {
                'type': 'WatchEvent',
                'created_at': '2026-08-20T12:00:00Z'
            }
        ]

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(fake_events).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = fetch_monthly_github_commits('testuser', 2026, 8)
        self.assertTrue(result['success'])
        self.assertEqual(result['total_commits'], 5)
        self.assertEqual(result['daily_counts'], {'25': 3, '1': 2})
        self.assertEqual(result['active_days'], [1, 25])

    def test_edit_habit_name_and_category(self):
        """Test editing a habit name, category, and target counts."""
        # Add habit
        r = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'add_habit',
            'habit_name': 'Original Name',
            'habit_type': 'counter',
            'category': 'Health',
            'target_count': 1,
            'unit': 'times'
        })
        habit_id = r.get_json()['habit']['id']

        # Edit habit
        res_edit = self.client.post('/monthly?year=2026&month=8', headers=self.headers, json={
            'action': 'update_habit',
            'habit_id': habit_id,
            'habit_name': 'Updated Habit Name',
            'category': 'Productivity',
            'target_count': 3,
            'unit': 'glasses'
        })
        self.assertEqual(res_edit.status_code, 200)
        self.assertTrue(res_edit.get_json()['success'])

        plan = MonthlyPlan.query.filter_by(user_id=self.user.id, year=2026, month=8).first()
        updated_h = next((h for h in plan.habits if h['id'] == habit_id), None)
        self.assertIsNotNone(updated_h)
        self.assertEqual(updated_h['name'], 'Updated Habit Name')
        self.assertEqual(updated_h['category'], 'Productivity')
        self.assertEqual(updated_h['target_count'], 3)
        self.assertEqual(updated_h['unit'], 'glasses')

if __name__ == '__main__':
    unittest.main()


