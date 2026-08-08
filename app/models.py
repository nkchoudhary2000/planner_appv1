from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Google OAuth2 & Google Drive Sync fields
    google_id = db.Column(db.String(128), unique=True, nullable=True, index=True)
    google_token = db.Column(db.JSON, nullable=True)
    drive_sync_enabled = db.Column(db.Boolean, default=True)
    last_drive_sync = db.Column(db.DateTime, nullable=True)
    google_drive_folder_id = db.Column(db.String(128), nullable=True)
    google_drive_folder_name = db.Column(db.String(255), nullable=True)
    google_drive_folder_path = db.Column(db.String(512), nullable=True)


    daily_plans = db.relationship('DailyPlan', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    monthly_plans = db.relationship('MonthlyPlan', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    yearly_plans = db.relationship('YearlyPlan', backref='owner', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class DailyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    schedule = db.Column(db.JSON, default=dict)   # e.g. {"09:00 AM": {"activity": "Team Sync", "mood": "😄"}}
    tasks = db.Column(db.JSON, default=list)       # e.g. [{"id": "t1", "text": "Draft RFC", "completed": True, "priority": "High"}]
    notes = db.Column(db.Text, default='')
    depression_episodes = db.Column(db.JSON, default=list)  # e.g. [{"id": "ep1", "start_time": "08:30 AM", "duration": "45m", "intensity": 6, ...}]
    memory_logs = db.Column(db.JSON, default=list)          # e.g. [{"id": "mem1", "time": "10:30 AM", "item": "Keys", "category": "Belonging", ...}]
    sleep_log = db.Column(db.JSON, default=dict)            # e.g. {"hours": 7.5, "bedtime": "11:00 PM", "wake_time": "06:30 AM", "quality": 8, ...}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='_user_date_uc'),)

    def __repr__(self):
        return f'<DailyPlan User:{self.user_id} Date:{self.date}>'


class MonthlyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1 to 12
    goals = db.Column(db.JSON, default=list)       # e.g. [{"id": "g1", "title": "Run 50km", "category": "Health", "status": "In Progress"}]
    habits = db.Column(db.JSON, default=list)      # e.g. [{"id": "h1", "name": "Morning Walk", "completed_days": [1, 2, 4]}]
    milestones = db.Column(db.JSON, default=list)  # e.g. [{"id": "m1", "title": "Submit Q3 Report", "date": "15", "completed": False}]
    calendar_days = db.Column(db.JSON, default=dict) # e.g. {"15": {"items": [{"id": "c1", "text": "Target Deadline", "type": "deadline"}], "sticker": "🚀", "image_url": "..."}}
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'year', 'month', name='_user_year_month_uc'),)

    def __repr__(self):
        return f'<MonthlyPlan User:{self.user_id} {self.year}-{self.month:02d}>'


class YearlyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    resolutions = db.Column(db.JSON, default=list)  # e.g. [{"id": "r1", "text": "Read 20 books", "category": "Personal"}]
    objectives = db.Column(db.JSON, default=list)   # e.g. [{"id": "o1", "title": "Master Python", "quarter": "Q1-Q4", "status": "On Track"}]
    reflections = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'year', name='_user_year_uc'),)

    def __repr__(self):
        return f'<YearlyPlan User:{self.user_id} Year:{self.year}>'


class WeeklyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, nullable=False)  # 1 to 53
    start_date = db.Column(db.Date, nullable=False)
    goals = db.Column(db.JSON, default=list)            # e.g. [{"id": "g1", "title": "Finish MVP", "completed": False}]
    daily_todos = db.Column(db.JSON, default=dict)      # e.g. {"Mon": [{"id": "t1", "text": "Gym", "completed": False}], ...}
    shopping_list = db.Column(db.JSON, default=list)    # e.g. [{"id": "s1", "item": "Oat Milk", "category": "Groceries", "bought": False}]
    meals_menu = db.Column(db.JSON, default=dict)       # e.g. {"Mon": {"breakfast": "Oatmeal", "lunch": "Salad", "dinner": "Soup"}, ...}
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'year', 'week_number', name='_user_year_week_uc'),)

    def __repr__(self):
        return f'<WeeklyPlan User:{self.user_id} Year:{self.year} W:{self.week_number}>'

