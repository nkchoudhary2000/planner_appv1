from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
from app import db
from app.auth import auth
from app.models import User

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('planner.dashboard'))

    if request.method == 'POST':
        login_input = request.form.get('login_input', '').strip()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False

        if not login_input or not password:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter(
            (func.lower(User.email) == login_input.lower()) | 
            (func.lower(User.username) == login_input.lower())
        ).first()

        if not user:
            flash('Invalid email/username or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        # Check if user registered via Google Sign-In only and hasn't set a local password yet
        if not user.password_hash:
            flash('This account was created using Google Sign-In and does not have a local password set yet. Please log in with Google, or register with this email to set up a local password.', 'warning')
            return redirect(url_for('auth.login'))

        if not user.check_password(password):
            flash('Invalid email/username or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        from app.services.google_service import check_and_trigger_daily_drive_sync
        sync_res = check_and_trigger_daily_drive_sync(user)
        if sync_res and isinstance(sync_res, dict) and sync_res.get('success'):
            flash('Daily automatic Google Drive backup completed!', 'success')

        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('planner.dashboard')
        flash(f'Welcome back, {user.username}!', 'success')
        return redirect(next_page)

    return render_template('auth/login.html')



@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('planner.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not username or not email or not password or not confirm_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return redirect(url_for('auth.register'))

        # Check if user exists by email or username
        existing_email_user = User.query.filter(func.lower(User.email) == email.lower()).first()
        existing_username_user = User.query.filter(func.lower(User.username) == username.lower()).first()

        if existing_email_user:
            # Case 1: User signed up with Google previously and hasn't set a local password yet
            if not existing_email_user.password_hash:
                # Check username collision with another user
                if existing_username_user and existing_username_user.id != existing_email_user.id:
                    flash('Username is already taken by another account. Please choose a different username.', 'warning')
                    return redirect(url_for('auth.register'))
                
                # Merge local password & username into existing Google account
                existing_email_user.username = username
                existing_email_user.set_password(password)
                db.session.commit()

                login_user(existing_email_user)
                flash('Your account (previously created with Google Sign-In) has been merged with your local login password! You can now log in using either Google or your password.', 'success')
                return redirect(url_for('planner.dashboard'))
            else:
                # Case 2: Account exists and already has a password set
                flash('An account with this email already exists. You can log in using your password or Google.', 'warning')
                return redirect(url_for('auth.login'))

        if existing_username_user:
            flash('Username is already taken. Please choose another username.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash('Registration successful! Your account has been created.', 'success')
        return redirect(url_for('planner.dashboard'))

    return render_template('auth/register.html')


@auth.route('/set-password', methods=['POST'])
@login_required
def set_password():
    """Allows logged in user (e.g. Google user) to set or update their local password directly from profile."""
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not new_password or not confirm_password:
        flash('Password fields cannot be empty.', 'danger')
        return redirect(request.referrer or url_for('planner.dashboard'))

    if new_password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return redirect(request.referrer or url_for('planner.dashboard'))

    if len(new_password) < 6:
        flash('Password must be at least 6 characters long.', 'danger')
        return redirect(request.referrer or url_for('planner.dashboard'))

    current_user.set_password(new_password)
    db.session.commit()

    flash('Local login password saved successfully! You can now log in with either Google or local password.', 'success')
    return redirect(request.referrer or url_for('planner.dashboard'))


@auth.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    """Allows logged-in users to update display_name, username, email, and password."""
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
    data = request.get_json() if request.is_json else request.form

    display_name = (data.get('display_name') or '').strip()
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    new_password = (data.get('new_password') or '').strip()
    confirm_password = (data.get('confirm_password') or '').strip()

    errors = []

    if username and username.lower() != current_user.username.lower():
        if len(username) < 3:
            errors.append('Username must be at least 3 characters long.')
        else:
            existing = User.query.filter(func.lower(User.username) == username.lower(), User.id != current_user.id).first()
            if existing:
                errors.append('Username is already taken by another user.')
            else:
                current_user.username = username

    if email and email.lower() != current_user.email.lower():
        existing = User.query.filter(func.lower(User.email) == email.lower(), User.id != current_user.id).first()
        if existing:
            errors.append('Email address is already registered to another account.')
        else:
            current_user.email = email

    current_user.display_name = display_name if display_name else None

    if new_password:
        if new_password != confirm_password:
            errors.append('Passwords do not match.')
        elif len(new_password) < 6:
            errors.append('Password must be at least 6 characters long.')
        else:
            current_user.set_password(new_password)

    if errors:
        msg = ' '.join(errors)
        if is_ajax:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('planner.dashboard'))

    db.session.commit()

    if is_ajax:
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully!',
            'user': {
                'username': current_user.username,
                'email': current_user.email,
                'display_name': current_user.display_name or '',
                'name': current_user.name
            }
        })

    flash('Profile updated successfully!', 'success')
    return redirect(request.referrer or url_for('planner.dashboard'))


@auth.route('/google/login')
def google_login():
    from app.services.google_service import oauth
    from flask import current_app
    
    # Check if Google OAuth Client ID is configured
    client_id = current_app.config.get('GOOGLE_CLIENT_ID')
    if not client_id or client_id == 'MOCK_GOOGLE_CLIENT_ID':
        # Friendly Development/Demo Google Login mode
        mock_email = "user.google@gmail.com"
        mock_username = "GoogleUser"
        
        user = User.query.filter(
            (func.lower(User.email) == mock_email.lower()) | 
            (func.lower(User.username) == mock_username.lower())
        ).first()
        
        if not user:
            user = User(username=mock_username, email=mock_email, google_id="mock_google_id_12345")
            db.session.add(user)
        else:
            if not user.google_id:
                user.google_id = "mock_google_id_12345"

        user.google_token = {"access_token": "mock_token", "token_type": "Bearer"}
        db.session.commit()
        login_user(user)
        flash('Logged in via Google Account! Google Drive sync is enabled.', 'success')
        return redirect(url_for('planner.dashboard'))

    scheme = 'https' if request.headers.get('X-Forwarded-Proto') == 'https' or not (request.host.startswith('127.0.0.1') or request.host.startswith('localhost')) else 'http'
    redirect_uri = url_for('auth.google_callback', _external=True, _scheme=scheme)
    return oauth.google.authorize_redirect(redirect_uri, access_type='offline', prompt='select_account')


@auth.route('/google/callback')
def google_callback():
    from app.services.google_service import oauth
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or oauth.google.userinfo()
        google_id = user_info['sub']
        email = user_info['email'].lower()
        username = user_info.get('name') or email.split('@')[0]

        user = User.query.filter((User.google_id == google_id) | (func.lower(User.email) == email.lower())).first()
        if not user:
            existing_user_by_name = User.query.filter(func.lower(User.username) == username.lower()).first()
            if existing_user_by_name:
                username = f"{username}_{google_id[:5]}"
            user = User(username=username, email=email, google_id=google_id)
            db.session.add(user)
        else:
            if not user.google_id:
                user.google_id = google_id

        user.google_token = token
        db.session.commit()

        login_user(user)
        flash('Successfully authenticated with Google Account! Your accounts are merged.', 'success')
        return redirect(url_for('planner.dashboard'))

    except Exception as e:
        db.session.rollback()
        flash(f'Google authentication failed: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))


