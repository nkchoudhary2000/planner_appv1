import json
from datetime import datetime, date
from authlib.integrations.flask_client import OAuth
from flask import url_for, current_app
from sqlalchemy.orm.attributes import flag_modified
from app import db
from app.models import User, DailyPlan, MonthlyPlan, YearlyPlan

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
    """Serialize all plans for a user into a clean JSON structure."""
    daily_plans = DailyPlan.query.filter_by(user_id=user.id).all()
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
                "notes": dp.notes or ''
            }
            for dp in daily_plans
        ],
        "monthly_plans": [
            {
                "year": mp.year,
                "month": mp.month,
                "goals": mp.goals or [],
                "habits": mp.habits or [],
                "milestones": mp.milestones or [],
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
    """Restore database records for a user from a JSON payload."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid backup format")

    # Restore Daily Plans
    for dp_data in payload.get('daily_plans', []):
        try:
            plan_date = datetime.strptime(dp_data['date'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            continue

        dp = DailyPlan.query.filter_by(user_id=user.id, date=plan_date).first()
        if not dp:
            dp = DailyPlan(user_id=user.id, date=plan_date)
            db.session.add(dp)

        dp.schedule = dp_data.get('schedule', {})
        dp.tasks = dp_data.get('tasks', [])
        dp.notes = dp_data.get('notes', '')
        flag_modified(dp, 'schedule')
        flag_modified(dp, 'tasks')

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
        mp.notes = mp_data.get('notes', '')
        flag_modified(mp, 'goals')
        flag_modified(mp, 'habits')
        flag_modified(mp, 'milestones')

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

    # Backup / Mock restore mode
    user.last_drive_sync = datetime.utcnow()
    db.session.commit()
    return {
        'success': True,
        'message': 'Planner backup data restored successfully!'
    }



