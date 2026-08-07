from functools import wraps
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.admin import admin
from app.models import User, DailyPlan, WeeklyPlan, MonthlyPlan, YearlyPlan

ADMIN_EMAIL = 'niraj.choudhary1995@gmail.com'

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or (current_user.email or '').strip().lower() != ADMIN_EMAIL:
            flash('Access restricted. Admin privileges required.', 'danger')
            return redirect(url_for('planner.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin.route('/')
@admin_required
def dashboard():
    users = User.query.order_by(User.id.asc()).all()
    
    # Statistics
    total_users = len(users)
    total_daily_plans = DailyPlan.query.count()
    total_weekly_plans = WeeklyPlan.query.count()
    total_monthly_plans = MonthlyPlan.query.count()
    total_yearly_plans = YearlyPlan.query.count()
    
    # Prepare enriched user list with plan counts
    user_list = []
    for u in users:
        d_count = DailyPlan.query.filter_by(user_id=u.id).count()
        w_count = WeeklyPlan.query.filter_by(user_id=u.id).count()
        m_count = MonthlyPlan.query.filter_by(user_id=u.id).count()
        y_count = YearlyPlan.query.filter_by(user_id=u.id).count()
        
        user_list.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'created_at': u.created_at,
            'is_admin': (u.email or '').strip().lower() == ADMIN_EMAIL,
            'google_connected': bool(u.google_id or u.google_token),
            'daily_count': d_count,
            'weekly_count': w_count,
            'monthly_count': m_count,
            'yearly_count': y_count,
            'total_plans': d_count + w_count + m_count + y_count
        })
        
    return render_template(
        'admin/index.html',
        admin_email=ADMIN_EMAIL,
        total_users=total_users,
        total_daily_plans=total_daily_plans,
        total_weekly_plans=total_weekly_plans,
        total_monthly_plans=total_monthly_plans,
        total_yearly_plans=total_yearly_plans,
        users=user_list
    )


@admin.route('/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    target_user = User.query.get_or_404(user_id)
    
    if (target_user.email or '').strip().lower() == ADMIN_EMAIL:
        flash('Administrator account cannot be deleted.', 'danger')
        return redirect(url_for('admin.dashboard'))
        
    username = target_user.username
    db.session.delete(target_user)
    db.session.commit()
    
    flash(f'User "{username}" and all associated data have been deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/user/clear-plans/<int:user_id>', methods=['POST'])
@admin_required
def clear_user_plans(user_id):
    target_user = User.query.get_or_404(user_id)
    
    DailyPlan.query.filter_by(user_id=user_id).delete()
    WeeklyPlan.query.filter_by(user_id=user_id).delete()
    MonthlyPlan.query.filter_by(user_id=user_id).delete()
    YearlyPlan.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    
    flash(f'All planner records for user "{target_user.username}" have been purged successfully.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin.route('/db/clear-plans', methods=['POST'])
@admin_required
def clear_plans():
    db.session.query(DailyPlan).delete()
    db.session.query(WeeklyPlan).delete()
    db.session.query(MonthlyPlan).delete()
    db.session.query(YearlyPlan).delete()
    db.session.commit()
    
    flash('All plan records across all users have been successfully cleared.', 'success')
    return redirect(url_for('admin.dashboard'))
