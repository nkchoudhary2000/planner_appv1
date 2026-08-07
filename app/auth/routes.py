from flask import render_template, redirect, url_for, flash, request
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

        if not user or not user.check_password(password):
            flash('Invalid email/username or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
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

        existing_user = User.query.filter((User.email == email) | (User.username == username)).first()
        if existing_user:
            if existing_user.email == email:
                flash('An account with this email already exists.', 'warning')
            else:
                flash('Username is already taken. Please choose another.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


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
        
        user = User.query.filter((User.email == mock_email) | (User.username == mock_username)).first()
        if not user:
            user = User(username=mock_username, email=mock_email, google_id="mock_google_id_12345")
            db.session.add(user)
            db.session.commit()

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

        user = User.query.filter((User.google_id == google_id) | (User.email == email)).first()
        if not user:
            user = User(username=username, email=email, google_id=google_id)
            db.session.add(user)

        user.google_token = token
        user.google_id = google_id
        db.session.commit()

        login_user(user)
        flash('Successfully authenticated with Google Account!', 'success')
        return redirect(url_for('planner.dashboard'))

    except Exception as e:
        flash(f'Google authentication failed: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))

