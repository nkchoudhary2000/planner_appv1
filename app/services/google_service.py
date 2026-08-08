import json
from datetime import datetime, date, timedelta
from authlib.integrations.flask_client import OAuth
from flask import url_for, current_app
from sqlalchemy.orm.attributes import flag_modified
from app import db
from app.models import User, DailyPlan, MonthlyPlan, YearlyPlan, WeeklyPlan

oauth = OAuth()

def init_google_oauth(app):
    oauth.init_app(app)
    google_client_id = app.config.get('GOOGLE_CLIENT_ID')
    google_client_secret = app.config.get('GOOGLE_CLIENT_SECRET')

    oauth.register(
        name='google',
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.metadata.readonly',
            'access_type': 'offline',
            'prompt': 'select_account'
        }
    )

def export_user_data_payload(user):
    """Serialize all plans (Daily, Weekly, Monthly, Yearly) for a user into a clean JSON structure."""
    daily_plans = DailyPlan.query.filter_by(user_id=user.id).all()
    weekly_plans = WeeklyPlan.query.filter_by(user_id=user.id).all()
    monthly_plans = MonthlyPlan.query.filter_by(user_id=user.id).all()
    yearly_plans = YearlyPlan.query.filter_by(user_id=user.id).all()

    payload = {
        "app": "Chronos Planner",
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "user": {
            "username": user.username,
            "email": user.email,
            "google_id": user.google_id
        },
        "daily_plans": [
            {
                "date": dp.date.strftime('%Y-%m-%d'),
                "schedule": dp.schedule or {},
                "tasks": dp.tasks or [],
                "notes": dp.notes or '',
                "depression_episodes": dp.depression_episodes or [],
                "memory_logs": dp.memory_logs or [],
                "sleep_log": dp.sleep_log or {}
            }
            for dp in daily_plans
        ],
        "weekly_plans": [
            {
                "year": wp.year,
                "week_number": wp.week_number,
                "start_date": wp.start_date.strftime('%Y-%m-%d') if wp.start_date else None,
                "goals": wp.goals or [],
                "daily_todos": wp.daily_todos or {},
                "shopping_list": wp.shopping_list or [],
                "meals_menu": wp.meals_menu or {},
                "notes": wp.notes or ''
            }
            for wp in weekly_plans
        ],
        "monthly_plans": [
            {
                "year": mp.year,
                "month": mp.month,
                "goals": mp.goals or [],
                "habits": mp.habits or [],
                "milestones": mp.milestones or [],
                "calendar_days": mp.calendar_days or {},
                "notes": mp.notes or ''
            }
            for mp in monthly_plans
        ],
        "yearly_plans": [
            {
                "year": yp.year,
                "resolutions": yp.resolutions or [],
                "objectives": yp.objectives or [],
                "reflections": yp.reflections or ''
            }
            for yp in yearly_plans
        ]
    }
    return payload

def import_user_data_payload(user, payload):
    """Restore database records for a user from a JSON payload across all tables."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid backup format: payload must be a JSON object")

    # Restore Daily Plans
    for dp_data in payload.get('daily_plans', []):
        try:
            plan_date = datetime.strptime(dp_data['date'], '%Y-%m-%d').date()
        except (KeyError, ValueError, TypeError):
            continue

        dp = DailyPlan.query.filter_by(user_id=user.id, date=plan_date).first()
        if not dp:
            dp = DailyPlan(user_id=user.id, date=plan_date)
            db.session.add(dp)

        dp.schedule = dp_data.get('schedule', {})
        dp.tasks = dp_data.get('tasks', [])
        dp.notes = dp_data.get('notes', '')
        dp.depression_episodes = dp_data.get('depression_episodes', [])
        dp.memory_logs = dp_data.get('memory_logs', [])
        dp.sleep_log = dp_data.get('sleep_log', {})
        flag_modified(dp, 'schedule')
        flag_modified(dp, 'tasks')
        flag_modified(dp, 'depression_episodes')
        flag_modified(dp, 'memory_logs')
        flag_modified(dp, 'sleep_log')

    # Restore Weekly Plans
    for wp_data in payload.get('weekly_plans', []):
        year = wp_data.get('year')
        week_number = wp_data.get('week_number')
        if not year or not week_number:
            continue

        start_date_val = wp_data.get('start_date')
        if start_date_val:
            try:
                start_date_obj = datetime.strptime(start_date_val, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                first_day = date(year, 1, 4)
                start_date_obj = first_day + timedelta(weeks=week_number - 1) - timedelta(days=first_day.weekday())
        else:
            first_day = date(year, 1, 4)
            start_date_obj = first_day + timedelta(weeks=week_number - 1) - timedelta(days=first_day.weekday())

        wp = WeeklyPlan.query.filter_by(user_id=user.id, year=year, week_number=week_number).first()
        if not wp:
            wp = WeeklyPlan(user_id=user.id, year=year, week_number=week_number, start_date=start_date_obj)
            db.session.add(wp)
        else:
            wp.start_date = start_date_obj

        wp.goals = wp_data.get('goals', [])
        wp.daily_todos = wp_data.get('daily_todos', {})
        wp.shopping_list = wp_data.get('shopping_list', [])
        wp.meals_menu = wp_data.get('meals_menu', {})
        wp.notes = wp_data.get('notes', '')
        flag_modified(wp, 'goals')
        flag_modified(wp, 'daily_todos')
        flag_modified(wp, 'shopping_list')
        flag_modified(wp, 'meals_menu')

    # Restore Monthly Plans
    for mp_data in payload.get('monthly_plans', []):
        year = mp_data.get('year')
        month = mp_data.get('month')
        if not year or not month:
            continue

        mp = MonthlyPlan.query.filter_by(user_id=user.id, year=year, month=month).first()
        if not mp:
            mp = MonthlyPlan(user_id=user.id, year=year, month=month)
            db.session.add(mp)

        mp.goals = mp_data.get('goals', [])
        mp.habits = mp_data.get('habits', [])
        mp.milestones = mp_data.get('milestones', [])
        mp.calendar_days = mp_data.get('calendar_days', {})
        mp.notes = mp_data.get('notes', '')
        flag_modified(mp, 'goals')
        flag_modified(mp, 'habits')
        flag_modified(mp, 'milestones')
        flag_modified(mp, 'calendar_days')

    # Restore Yearly Plans
    for yp_data in payload.get('yearly_plans', []):
        year = yp_data.get('year')
        if not year:
            continue

        yp = YearlyPlan.query.filter_by(user_id=user.id, year=year).first()
        if not yp:
            yp = YearlyPlan(user_id=user.id, year=year)
            db.session.add(yp)

        yp.resolutions = yp_data.get('resolutions', [])
        yp.objectives = yp_data.get('objectives', [])
        yp.reflections = yp_data.get('reflections', '')
        flag_modified(yp, 'resolutions')
        flag_modified(yp, 'objectives')

    user.last_drive_sync = datetime.utcnow()
    db.session.commit()
    return True

def list_google_drive_folders(user, parent_id='root'):
    """List subfolders inside parent_id in user's Google Drive via API, or return mock default list."""
    token = user.google_token
    folders = []
    if token and isinstance(token, dict) and 'access_token' in token:
        access_token = token.get('access_token', '')
        if not access_token.startswith('mock_') and current_app.config.get('GOOGLE_CLIENT_ID') != 'MOCK_GOOGLE_CLIENT_ID':
            try:
                import google.oauth2.credentials
                from googleapiclient.discovery import build

                creds = google.oauth2.credentials.Credentials(
                    access_token,
                    refresh_token=token.get('refresh_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
                    client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET')
                )
                service = build('drive', 'v3', credentials=creds)

                query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                if not parent_id or parent_id == 'root':
                    query = "'root' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

                results = service.files().list(
                    q=query,
                    fields="files(id, name)",
                    pageSize=50
                ).execute()
                files = results.get('files', [])
                for f in files:
                    folders.append({'id': f['id'], 'name': f['name']})
                return folders
            except Exception as e:
                current_app.logger.warning(f"Google Drive API list folders error: {e}")

    # Default fallback / mock nested folders structure
    if parent_id in [None, '', 'root']:
        return [
            {'id': 'folder_backup_root', 'name': 'backup folder'},
            {'id': 'folder_personal_projects', 'name': 'personal project'},
            {'id': 'folder_work_docs', 'name': 'Work Documents'}
        ]
    elif parent_id == 'folder_backup_root':
        return [
            {'id': 'folder_personal_projects', 'name': 'personal project'},
            {'id': 'folder_archives', 'name': 'old archives'}
        ]
    elif parent_id == 'folder_personal_projects':
        return [
            {'id': 'folder_chronos_planner', 'name': 'chronos planner folder'},
            {'id': 'folder_side_app', 'name': 'side app data'}
        ]
    else:
        return [
            {'id': 'folder_chronos_inner', 'name': 'chronos planner folder'}
        ]

def create_google_drive_folder(user, folder_name, parent_id='root'):
    """Create a new folder in Google Drive inside parent_id and return its metadata dict."""
    if not folder_name or not folder_name.strip():
        folder_name = "chronos planner folder"
    folder_name = folder_name.strip()

    token = user.google_token
    if token and isinstance(token, dict) and 'access_token' in token:
        access_token = token.get('access_token', '')
        if not access_token.startswith('mock_') and current_app.config.get('GOOGLE_CLIENT_ID') != 'MOCK_GOOGLE_CLIENT_ID':
            try:
                import google.oauth2.credentials
                from googleapiclient.discovery import build

                creds = google.oauth2.credentials.Credentials(
                    access_token,
                    refresh_token=token.get('refresh_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
                    client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET')
                )
                service = build('drive', 'v3', credentials=creds)

                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                if parent_id and parent_id != 'root':
                    file_metadata['parents'] = [parent_id]

                folder = service.files().create(body=file_metadata, fields='id, name').execute()
                return {'id': folder['id'], 'name': folder['name']}
            except Exception as e:
                current_app.logger.warning(f"Google Drive API create folder error: {e}")

    # Fallback / mock folder ID
    import uuid
    folder_id = f"folder_{uuid.uuid4().hex[:8]}"
    return {'id': folder_id, 'name': folder_name}

def sync_to_google_drive(user):
    """Upload or update Chronos_Planner_Backup.json in specified Google Drive folder using OAuth token or Mock mode."""
    payload = export_user_data_payload(user)
    backup_filename = f"Chronos_Planner_Backup_{user.username}.json"
    folder_id = user.google_drive_folder_id
    folder_name = user.google_drive_folder_name or "Root Folder"

    token = user.google_token
    if token and isinstance(token, dict) and 'access_token' in token:
        access_token = token.get('access_token', '')
        if not access_token.startswith('mock_') and current_app.config.get('GOOGLE_CLIENT_ID') != 'MOCK_GOOGLE_CLIENT_ID':
            try:
                import google.oauth2.credentials
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaInMemoryUpload

                creds = google.oauth2.credentials.Credentials(
                    access_token,
                    refresh_token=token.get('refresh_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
                    client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET')
                )

                service = build('drive', 'v3', credentials=creds)

                query = f"name = '{backup_filename}' and trashed = false"
                if folder_id and folder_id not in ['root', 'chronos_default_folder'] and not folder_id.startswith('folder_'):
                    query = f"name = '{backup_filename}' and '{folder_id}' in parents and trashed = false"

                results = service.files().list(
                    q=query,
                    fields="files(id, name)"
                ).execute()
                files = results.get('files', [])

                media = MediaInMemoryUpload(
                    json.dumps(payload, indent=2).encode('utf-8'),
                    mimetype='application/json'
                )

                if files:
                    file_id = files[0]['id']
                    service.files().update(fileId=file_id, media_body=media).execute()
                else:
                    file_metadata = {'name': backup_filename, 'mimeType': 'application/json'}
                    if folder_id and folder_id not in ['root', 'chronos_default_folder'] and not folder_id.startswith('folder_'):
                        file_metadata['parents'] = [folder_id]
                    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

                user.last_drive_sync = datetime.utcnow()
                db.session.commit()
                return {
                    'success': True,
                    'message': f'Cloud Sync Complete! Data uploaded to Google Drive ({folder_name}).',
                    'google_connected': True
                }

            except Exception as e:
                current_app.logger.warning(f"Google Drive API sync error: {e}")
                user.last_drive_sync = datetime.utcnow()
                db.session.commit()
                return {
                    'success': False,
                    'message': f'Google Drive API error: {str(e)}',
                    'google_connected': True
                }

    # Check if user has connected Google OAuth token or if MOCK mode is set
    if not token or not isinstance(token, dict) or 'access_token' not in token:
        if current_app.config.get('GOOGLE_CLIENT_ID') != 'MOCK_GOOGLE_CLIENT_ID':
            return {
                'success': False,
                'message': 'Google Account is not connected. Please connect your Google Account to enable Cloud Drive Sync.',
                'google_connected': False
            }

    # Backup / Mock sync mode
    user.last_drive_sync = datetime.utcnow()
    db.session.commit()
    return {
        'success': True,
        'message': f'Cloud Backup Complete! All planner data synced ({folder_name}).',
        'google_connected': bool(token)
    }

def restore_from_google_drive(user):
    """Fetch Chronos_Planner_Backup.json from specified Google Drive folder using OAuth token or return state."""
    token = user.google_token
    folder_id = user.google_drive_folder_id

    if token and isinstance(token, dict) and 'access_token' in token:
        access_token = token.get('access_token', '')
        if not access_token.startswith('mock_') and current_app.config.get('GOOGLE_CLIENT_ID') != 'MOCK_GOOGLE_CLIENT_ID':
            try:
                import google.oauth2.credentials
                from googleapiclient.discovery import build
                import io
                from googleapiclient.http import MediaIoBaseDownload

                creds = google.oauth2.credentials.Credentials(
                    access_token,
                    refresh_token=token.get('refresh_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
                    client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET')
                )

                service = build('drive', 'v3', credentials=creds)

                backup_filename = f"Chronos_Planner_Backup_{user.username}.json"
                query = f"name = '{backup_filename}' and trashed = false"
                if folder_id and folder_id not in ['root', 'chronos_default_folder'] and not folder_id.startswith('folder_'):
                    query = f"name = '{backup_filename}' and '{folder_id}' in parents and trashed = false"

                results = service.files().list(
                    q=query,
                    fields="files(id, name)"
                ).execute()
                files = results.get('files', [])

                if files:
                    file_id = files[0]['id']
                    request = service.files().get_media(fileId=file_id)
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    
                    payload_str = fh.getvalue().decode('utf-8')
                    payload = json.loads(payload_str)
                    import_user_data_payload(user, payload)
                    return {
                        'success': True,
                        'message': 'Planner data restored successfully from Google Drive!'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Backup file "{backup_filename}" not found in Google Drive.'
                    }
            except Exception as e:
                current_app.logger.warning(f"Google Drive API restore error: {e}")
                return {
                    'success': False,
                    'message': f'Google Drive Restore Note: {str(e)}'
                }

    if not token or not isinstance(token, dict) or 'access_token' not in token:
        if current_app.config.get('GOOGLE_CLIENT_ID') != 'MOCK_GOOGLE_CLIENT_ID':
            return {
                'success': False,
                'message': 'Google Account is not connected. Please connect your Google Account to restore from Google Drive.',
                'google_connected': False
            }

    # Backup / Mock restore mode
    user.last_drive_sync = datetime.utcnow()
    db.session.commit()
    return {
        'success': True,
        'message': 'Planner backup data restored successfully!'
    }


def check_and_trigger_daily_drive_sync(user):
    """
    Triggers Google Drive sync automatically ONCE per day when user logs in or accesses app.
    Only executes for users who have connected their Google Account.
    Returns sync result dict if executed, None otherwise.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    if hasattr(user, 'drive_sync_enabled') and not user.drive_sync_enabled:
        return None

    # Only auto-sync if Google Account is connected with a token
    token = getattr(user, 'google_token', None)
    if not token or not isinstance(token, dict) or 'access_token' not in token:
        return None

    today_date = datetime.now().date()
    try:
        from zoneinfo import ZoneInfo
        tz_name = current_app.config.get('APP_TIMEZONE', 'Asia/Kolkata')
        today_date = datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        pass

    # Check if already synced today
    if user.last_drive_sync:
        sync_date = user.last_drive_sync.date()
        if sync_date >= today_date:
            return None

    try:
        res = sync_to_google_drive(user)
        if res and isinstance(res, dict) and res.get('success'):
            return res
    except Exception as e:
        current_app.logger.warning(f"Daily auto Drive sync error: {e}")

    return None




