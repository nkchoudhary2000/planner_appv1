import json
import unittest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, PlanningEvent
from app.services.google_service import export_user_data_payload, import_user_data_payload
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False


class PlanningEventsTestCase(unittest.TestCase):
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

    def register_and_login(self, username="eventuser", email="event@example.com", password="password123"):
        self.client.post('/auth/register', data={
            'username': username,
            'email': email,
            'password': password,
            'confirm_password': password
        }, follow_redirects=True)

        self.client.post('/auth/login', data={
            'login_input': username,
            'password': password
        }, follow_redirects=True)

        user = User.query.filter_by(username=username).first()
        return user

    def test_add_planning_events_future_and_past(self):
        user = self.register_and_login()

        # 1. Add Future Event (Countdown)
        future_dt = (datetime.utcnow() + timedelta(days=45, hours=3, minutes=15)).strftime('%Y-%m-%dT%H:%M:%S')
        res_future = self.client.post('/api/planning/event/add', json={
            'title': 'Product v2.0 Launch',
            'target_datetime': future_dt,
            'category': 'Milestone',
            'notes': 'Production release with countdown',
            'color': '#8b5cf6',
            'icon': 'fa-rocket'
        })
        self.assertEqual(res_future.status_code, 200)
        data_f = res_future.get_json()
        self.assertTrue(data_f['success'])
        self.assertEqual(data_f['event']['title'], 'Product v2.0 Launch')
        self.assertEqual(data_f['event']['category'], 'Milestone')
        self.assertEqual(data_f['event']['color'], '#8b5cf6')

        # 2. Add Past Event (Count-up)
        past_dt = (datetime.utcnow() - timedelta(days=120, hours=5)).strftime('%Y-%m-%dT%H:%M:%S')
        res_past = self.client.post('/api/planning/event/add', json={
            'title': 'Started New Job',
            'target_datetime': past_dt,
            'category': 'Work',
            'notes': 'Elapsed time since start date',
            'color': '#10b981',
            'icon': 'fa-briefcase'
        })
        self.assertEqual(res_past.status_code, 200)
        data_p = res_past.get_json()
        self.assertTrue(data_p['success'])
        self.assertEqual(data_p['event']['title'], 'Started New Job')

        # Verify in DB
        events = PlanningEvent.query.filter_by(user_id=user.id).all()
        self.assertEqual(len(events), 2)

    def test_get_planning_events(self):
        user = self.register_and_login()

        dt = (datetime.utcnow() + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M:%S')
        self.client.post('/api/planning/event/add', json={
            'title': 'Tokyo Vacation',
            'target_datetime': dt,
            'category': 'Personal'
        })

        res = self.client.get('/api/planning/events')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['events']), 1)
        self.assertEqual(data['events'][0]['title'], 'Tokyo Vacation')
        self.assertEqual(data['events'][0]['category'], 'Personal')

    def test_edit_planning_event(self):
        user = self.register_and_login()

        dt1 = (datetime.utcnow() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%S')
        res_add = self.client.post('/api/planning/event/add', json={
            'title': 'Original Title',
            'target_datetime': dt1,
            'category': 'General',
            'notes': 'Original notes'
        })
        event_id = res_add.get_json()['event']['id']

        # Edit event
        dt2 = (datetime.utcnow() + timedelta(days=12, hours=4)).strftime('%Y-%m-%dT%H:%M:%S')
        res_edit = self.client.post('/api/planning/event/edit', json={
            'event_id': event_id,
            'title': 'Updated Title',
            'target_datetime': dt2,
            'category': 'Deadline',
            'color': '#f43f5e',
            'icon': 'fa-triangle-exclamation',
            'notes': 'Updated critical notes'
        })
        self.assertEqual(res_edit.status_code, 200)
        data_edit = res_edit.get_json()
        self.assertTrue(data_edit['success'])
        self.assertEqual(data_edit['event']['title'], 'Updated Title')
        self.assertEqual(data_edit['event']['category'], 'Deadline')
        self.assertEqual(data_edit['event']['color'], '#f43f5e')
        self.assertEqual(data_edit['event']['notes'], 'Updated critical notes')

        # Verify in DB
        db_event = db.session.get(PlanningEvent, event_id)
        self.assertEqual(db_event.title, 'Updated Title')
        self.assertEqual(db_event.category, 'Deadline')

    def test_delete_planning_event(self):
        user = self.register_and_login()

        dt = (datetime.utcnow() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%S')
        res_add = self.client.post('/api/planning/event/add', json={
            'title': 'To be deleted',
            'target_datetime': dt
        })
        event_id = res_add.get_json()['event']['id']

        res_del = self.client.post('/api/planning/event/delete', json={'event_id': event_id})
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()['success'])

        db_event = db.session.get(PlanningEvent, event_id)
        self.assertIsNone(db_event)

    def test_reorder_planning_events(self):
        user = self.register_and_login()

        res1 = self.client.post('/api/planning/event/add', json={'title': 'Event 1', 'target_datetime': '2026-10-01T10:00:00'})
        res2 = self.client.post('/api/planning/event/add', json={'title': 'Event 2', 'target_datetime': '2026-11-01T10:00:00'})
        id1 = res1.get_json()['event']['id']
        id2 = res2.get_json()['event']['id']

        # Reorder [id2, id1]
        res_reorder = self.client.post('/api/planning/event/reorder', json={'event_ids': [id2, id1]})
        self.assertEqual(res_reorder.status_code, 200)
        self.assertTrue(res_reorder.get_json()['success'])

        e1 = db.session.get(PlanningEvent, id1)
        e2 = db.session.get(PlanningEvent, id2)
        self.assertEqual(e2.sort_order, 0)
        self.assertEqual(e1.sort_order, 1)

    def test_validation_errors(self):
        user = self.register_and_login()

        # Missing title
        res = self.client.post('/api/planning/event/add', json={'title': '', 'target_datetime': '2026-12-31T20:00:00'})
        self.assertEqual(res.status_code, 400)

        # Invalid target datetime
        res = self.client.post('/api/planning/event/add', json={'title': 'Valid Title', 'target_datetime': 'invalid-date'})
        self.assertEqual(res.status_code, 400)

        # Edit missing event_id
        res = self.client.post('/api/planning/event/edit', json={'title': 'New Title'})
        self.assertEqual(res.status_code, 400)

        # Delete missing event_id
        res = self.client.post('/api/planning/event/delete', json={})
        self.assertEqual(res.status_code, 400)

        # Non-existent event
        res = self.client.post('/api/planning/event/edit', json={'event_id': 99999, 'title': 'Test'})
        self.assertEqual(res.status_code, 404)

    def test_user_data_isolation(self):
        # User 1 creates an event
        user1 = self.register_and_login(username="user1", email="user1@example.com")
        res1 = self.client.post('/api/planning/event/add', json={
            'title': 'User 1 Secret Milestone',
            'target_datetime': '2026-12-31T23:59:59'
        })
        event_id = res1.get_json()['event']['id']

        # Logout User 1
        self.client.get('/auth/logout', follow_redirects=True)

        # User 2 logs in
        user2 = self.register_and_login(username="user2", email="user2@example.com")

        # User 2 should see 0 events
        res_get = self.client.get('/api/planning/events')
        self.assertEqual(len(res_get.get_json()['events']), 0)

        # User 2 cannot edit User 1's event
        res_edit = self.client.post('/api/planning/event/edit', json={
            'event_id': event_id,
            'title': 'Hacked Title'
        })
        self.assertEqual(res_edit.status_code, 404)

        # User 2 cannot delete User 1's event
        res_del = self.client.post('/api/planning/event/delete', json={'event_id': event_id})
        self.assertEqual(res_del.status_code, 404)

    def test_planning_ui_route_includes_events(self):
        user = self.register_and_login()
        self.client.post('/api/planning/event/add', json={
            'title': 'Trip to Paris',
            'target_datetime': '2026-09-15T14:30:00',
            'category': 'Personal'
        })

        res = self.client.get('/planning')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Dynamic Event Time-Tracker', html)
        self.assertIn('Trip to Paris', html)
        self.assertIn('planning-event-tracker-panel', html)
        self.assertIn('planning-event-modal', html)

    def test_backup_and_restore_planning_events(self):
        user = self.register_and_login()

        # Add event
        self.client.post('/api/planning/event/add', json={
            'title': 'Marathon Training Complete',
            'target_datetime': '2026-11-20T08:00:00',
            'category': 'Milestone',
            'color': '#f59e0b',
            'icon': 'fa-trophy',
            'notes': '42km sub-4hr target'
        })

        # Export payload
        payload = export_user_data_payload(user)
        self.assertIn('planning_events', payload)
        self.assertEqual(len(payload['planning_events']), 1)
        self.assertEqual(payload['planning_events'][0]['title'], 'Marathon Training Complete')

        # Wipe DB event
        PlanningEvent.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        self.assertEqual(PlanningEvent.query.filter_by(user_id=user.id).count(), 0)

        # Restore payload
        stats = import_user_data_payload(user, payload)
        self.assertEqual(stats.get('events'), 1)
        restored = PlanningEvent.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(restored)
        self.assertEqual(restored.title, 'Marathon Training Complete')
        self.assertEqual(restored.category, 'Milestone')
        self.assertEqual(restored.color, '#f59e0b')


    def test_auto_expire_countdown_mode(self):
        user = self.register_and_login()

        dt = (datetime.utcnow() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%S')
        res = self.client.post('/api/planning/event/add', json={
            'title': 'Flash Sale Deadline',
            'target_datetime': dt,
            'timer_type': 'auto_expire',
            'completion_message': 'Flash sale has concluded!',
            'category': 'Deadline'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['event']['timer_type'], 'auto_expire')
        self.assertEqual(data['event']['completion_message'], 'Flash sale has concluded!')
        self.assertFalse(data['event']['is_recurring'])

        # Edit completion message
        event_id = data['event']['id']
        res_edit = self.client.post('/api/planning/event/edit', json={
            'event_id': event_id,
            'completion_message': 'Offer expired! Check back next season.'
        })
        self.assertEqual(res_edit.status_code, 200)
        data_edit = res_edit.get_json()
        self.assertEqual(data_edit['event']['completion_message'], 'Offer expired! Check back next season.')

        # Verify in DB
        db_ev = db.session.get(PlanningEvent, event_id)
        self.assertEqual(db_ev.timer_type, 'auto_expire')
        self.assertEqual(db_ev.completion_message, 'Offer expired! Check back next season.')

    def test_recurring_mode_event(self):
        user = self.register_and_login()

        # Create daily recurring timer (10:00 to 19:00)
        res = self.client.post('/api/planning/event/add', json={
            'title': 'Daily Focus Block',
            'timer_type': 'recurring',
            'is_recurring': True,
            'recurrence_frequency': 'daily',
            'window_start_time': '10:00',
            'window_end_time': '19:00',
            'inactive_message': 'Focus hours ended for today! Resumes at 10:00 AM.',
            'category': 'Work'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['event']['timer_type'], 'recurring')
        self.assertTrue(data['event']['is_recurring'])
        self.assertEqual(data['event']['recurrence_frequency'], 'daily')
        self.assertEqual(data['event']['window_start_time'], '10:00')
        self.assertEqual(data['event']['window_end_time'], '19:00')
        self.assertEqual(data['event']['inactive_message'], 'Focus hours ended for today! Resumes at 10:00 AM.')

        # Edit to monthly recurring
        event_id = data['event']['id']
        res_edit = self.client.post('/api/planning/event/edit', json={
            'event_id': event_id,
            'recurrence_frequency': 'monthly',
            'window_start_time': '09:00',
            'window_end_time': '17:00',
            'inactive_message': 'Monthly review paused.'
        })
        self.assertEqual(res_edit.status_code, 200)
        data_edit = res_edit.get_json()
        self.assertEqual(data_edit['event']['recurrence_frequency'], 'monthly')
        self.assertEqual(data_edit['event']['window_start_time'], '09:00')
        self.assertEqual(data_edit['event']['window_end_time'], '17:00')
        self.assertEqual(data_edit['event']['inactive_message'], 'Monthly review paused.')

        # Verify DB
        db_ev = db.session.get(PlanningEvent, event_id)
        self.assertEqual(db_ev.recurrence_frequency, 'monthly')
        self.assertEqual(db_ev.window_start_time, '09:00')
        self.assertEqual(db_ev.window_end_time, '17:00')

    def test_recurring_validation_errors(self):
        user = self.register_and_login()

        # Recurring without window times
        res = self.client.post('/api/planning/event/add', json={
            'title': 'Missing Window Times',
            'timer_type': 'recurring',
            'is_recurring': True
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn('Window start and end times are required', res.get_json()['message'])

    def test_backup_and_restore_auto_expire_and_recurring(self):
        user = self.register_and_login()

        # 1. Auto-expire event
        self.client.post('/api/planning/event/add', json={
            'title': 'New Year 2027 Countdown',
            'target_datetime': '2027-01-01T00:00:00',
            'timer_type': 'auto_expire',
            'completion_message': 'Happy New Year 2027!',
            'category': 'Celebration',
            'color': '#8b5cf6'
        })

        # 2. Recurring event
        self.client.post('/api/planning/event/add', json={
            'title': 'Trading Session Window',
            'timer_type': 'recurring',
            'is_recurring': True,
            'recurrence_frequency': 'daily',
            'window_start_time': '09:15',
            'window_end_time': '15:30',
            'inactive_message': 'Market is closed.',
            'category': 'Work',
            'color': '#10b981'
        })

        payload = export_user_data_payload(user)
        self.assertIn('planning_events', payload)
        self.assertEqual(len(payload['planning_events']), 2)

        # Clear DB
        PlanningEvent.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        self.assertEqual(PlanningEvent.query.filter_by(user_id=user.id).count(), 0)

        # Restore
        stats = import_user_data_payload(user, payload)
        self.assertEqual(stats.get('events'), 2)

        ev_ae = PlanningEvent.query.filter_by(user_id=user.id, title='New Year 2027 Countdown').first()
        self.assertIsNotNone(ev_ae)
        self.assertEqual(ev_ae.timer_type, 'auto_expire')
        self.assertEqual(ev_ae.completion_message, 'Happy New Year 2027!')

        ev_rec = PlanningEvent.query.filter_by(user_id=user.id, title='Trading Session Window').first()
        self.assertIsNotNone(ev_rec)
        self.assertEqual(ev_rec.timer_type, 'recurring')
        self.assertTrue(ev_rec.is_recurring)
        self.assertEqual(ev_rec.window_start_time, '09:15')
        self.assertEqual(ev_rec.window_end_time, '15:30')
        self.assertEqual(ev_rec.inactive_message, 'Market is closed.')


if __name__ == '__main__':
    unittest.main()

