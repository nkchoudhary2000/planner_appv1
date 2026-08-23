import os
import calendar
import io
from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy.orm.attributes import flag_modified
from app import db
from app.models import DailyPlan, MonthlyPlan, YearlyPlan, WeeklyPlan, User, PlanningTask, PlanningEvent
from app.services.cascade_service import (
    get_yearly_events_for_month,
    get_monthly_items_for_date,
    get_weekly_todos_for_date,
    get_all_cascaded_items_for_daily
)
from app.planner_helpers import (
    DEFAULT_TAGS,
    get_user_tags,
    get_today_date,
    to_24h_time,
    format_time_12h,
    process_task_spillovers,
    populate_daily_defaults,
    carry_forward_unbought_shopping_items,
    create_styled_excel
)

planner_ui = Blueprint('planner_ui', __name__)


@planner_ui.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('planner_ui.dashboard'))
    return redirect(url_for('auth.login'))


@planner_ui.before_app_request
def auto_daily_drive_sync():
    """Triggers automatic Google Drive backup once per day when authenticated user accesses the app."""
    if current_user and current_user.is_authenticated:
        from app.services.google_service import check_and_trigger_daily_drive_sync
        res = check_and_trigger_daily_drive_sync(current_user)
        if res and isinstance(res, dict) and res.get('success'):
            flash('Daily automatic Google Drive backup completed!', 'success')


@planner_ui.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    today = get_today_date()
    current_year = today.year
    current_month = today.month

    # Process automatic task spillovers and daily routine defaults up to today
    process_task_spillovers(current_user.id, today)
    populate_daily_defaults(current_user.id, today)

    # Get or create today's daily plan
    daily_plan = DailyPlan.query.filter_by(user_id=current_user.id, date=today).first()
    today_tasks = list(daily_plan.tasks or []) if daily_plan else []
    today_tasks.sort(key=lambda t: (1 if t.get('completed') else 0, 0 if t.get('priority') == 'High' else (1 if t.get('priority') == 'Medium' else 2)))

    completed_today = sum(1 for t in today_tasks if t.get('completed'))
    total_today = len(today_tasks)
    today_completion_pct = int((completed_today / total_today * 100)) if total_today > 0 else 0

    # Get current month's plan
    monthly_plan = MonthlyPlan.query.filter_by(user_id=current_user.id, year=current_year, month=current_month).first()
    monthly_goals = monthly_plan.goals if monthly_plan and monthly_plan.goals else []
    monthly_habits = monthly_plan.habits if monthly_plan and monthly_plan.habits else []
    goals_completed = sum(1 for g in monthly_goals if g.get('status') == 'Completed')

    # Get current year's plan
    yearly_plan = YearlyPlan.query.filter_by(user_id=current_user.id, year=current_year).first()
    yearly_resolutions = yearly_plan.resolutions if yearly_plan and yearly_plan.resolutions else []
    yearly_objectives = yearly_plan.objectives if yearly_plan and yearly_plan.objectives else []

    # Format month name
    month_name = calendar.month_name[current_month]

    # Aggregate Depression Tracker Analytics across recent DailyPlan entries
    all_daily_plans = DailyPlan.query.filter_by(user_id=current_user.id).order_by(DailyPlan.date.desc()).limit(30).all()
    recent_episodes = []
    total_episodes_count = 0
    intensity_sum = 0
    peak_intensity = 0
    coping_strategies_map = {}

    for dp in all_daily_plans:
        if dp.depression_episodes:
            for ep in dp.depression_episodes:
                total_episodes_count += 1
                intensity = int(ep.get('intensity', 5))
                intensity_sum += intensity
                if intensity > peak_intensity:
                    peak_intensity = intensity

                coping = ep.get('coping_mechanism', '').strip()
                if coping:
                    coping_strategies_map[coping] = coping_strategies_map.get(coping, 0) + 1

                ep_copy = dict(ep)
                ep_copy['date_str'] = dp.date.strftime('%b %d, %Y')
                recent_episodes.append(ep_copy)

    avg_intensity = round(intensity_sum / total_episodes_count, 1) if total_episodes_count > 0 else 0
    top_coping_strategies = sorted(coping_strategies_map.items(), key=lambda x: x[1], reverse=True)[:3]

    # Aggregate Memory Tracker Analytics across recent DailyPlan entries
    recent_memory_logs = []
    total_memory_slips_count = 0
    recovered_slips_count = 0
    memory_category_map = {}

    for dp in all_daily_plans:
        if dp.memory_logs:
            for log in dp.memory_logs:
                total_memory_slips_count += 1
                recovery = log.get('recovery', '').strip()
                if recovery and 'unresolved' not in recovery.lower() and 'still forgot' not in recovery.lower():
                    recovered_slips_count += 1
                
                cat = log.get('category', 'General').strip()
                if cat:
                    memory_category_map[cat] = memory_category_map.get(cat, 0) + 1
                
                log_copy = dict(log)
                log_copy['date_str'] = dp.date.strftime('%b %d, %Y')
                recent_memory_logs.append(log_copy)

    memory_recovery_pct = int((recovered_slips_count / total_memory_slips_count) * 100) if total_memory_slips_count > 0 else 0
    top_memory_categories = sorted(memory_category_map.items(), key=lambda x: x[1], reverse=True)[:3]
    today_memory_count = len(daily_plan.memory_logs or []) if daily_plan and daily_plan.memory_logs else 0

    # Aggregate Sleep Tracker Analytics across recent DailyPlan entries
    recent_sleep_logs = []
    total_sleep_hours_sum = 0
    sleep_days_count = 0
    sleep_quality_sum = 0

    for dp in all_daily_plans:
        if dp.sleep_log and isinstance(dp.sleep_log, dict) and dp.sleep_log.get('hours'):
            try:
                s_hours = float(dp.sleep_log.get('hours', 0))
            except (ValueError, TypeError):
                s_hours = 0
            try:
                s_quality = int(dp.sleep_log.get('quality', 0))
            except (ValueError, TypeError):
                s_quality = 0

            if s_hours > 0:
                total_sleep_hours_sum += s_hours
                sleep_days_count += 1
                sleep_quality_sum += s_quality

                log_copy = dict(dp.sleep_log)
                log_copy['date_str'] = dp.date.strftime('%b %d, %Y')
                recent_sleep_logs.append(log_copy)

    avg_sleep_hours = round(total_sleep_hours_sum / sleep_days_count, 1) if sleep_days_count > 0 else 0
    avg_sleep_quality = round(sleep_quality_sum / sleep_days_count, 1) if sleep_days_count > 0 else 0

    # Dashboard Reminder Panel (Marquee Alerts)
    marquee_alerts = []

    # 1) Unchecked Shopping List Items (Pending for X days)
    recent_weekly_plans = WeeklyPlan.query.filter_by(user_id=current_user.id).order_by(WeeklyPlan.start_date.desc()).limit(8).all()
    for wp in recent_weekly_plans:
        if wp.shopping_list:
            for item in wp.shopping_list:
                if not item.get('bought'):
                    added_str = item.get('added_date')
                    item_name = item.get('item', 'Item')
                    if added_str:
                        try:
                            a_date = datetime.strptime(added_str, '%Y-%m-%d').date()
                            days_pending = (today - a_date).days
                        except ValueError:
                            days_pending = 0
                    else:
                        days_pending = 0

                    if days_pending < 0:
                        days_pending = 0

                    marquee_alerts.append({
                        'type': 'shopping',
                        'icon': 'fa-solid fa-cart-shopping',
                        'badge': '🛒 Shopping Alert',
                        'badge_color': 'bg-amber-500/20 text-amber-300 border-amber-500/30',
                        'text': f'"{item_name}" is pending in your Shopping List for {days_pending} day{"s" if days_pending != 1 else ""}'
                    })

    # 2) Today's Birthdays and Anniversaries
    if yearly_plan and yearly_plan.events:
        for ev in yearly_plan.events:
            ev_date_str = ev.get('date', '')
            ev_type = ev.get('event_type', 'event')
            title = ev.get('title', 'Event')
            
            is_today = False
            if ev_date_str:
                try:
                    ev_date = datetime.strptime(ev_date_str, '%Y-%m-%d').date()
                    if ev_date.month == today.month and ev_date.day == today.day:
                        is_today = True
                except ValueError:
                    try:
                        parts = [p.strip() for p in ev_date_str.split('-') if p.strip()]
                        if len(parts) == 3 and int(parts[1]) == today.month and int(parts[2]) == today.day:
                            is_today = True
                        elif len(parts) == 2 and int(parts[0]) == today.month and int(parts[1]) == today.day:
                            is_today = True
                    except Exception:
                        pass
                
                if is_today:
                    if ev_type == 'birthday':
                        marquee_alerts.append({
                            'type': 'birthday',
                            'icon': 'fa-solid fa-cake-candles',
                            'badge': '🎂 Birthday Today',
                            'badge_color': 'bg-rose-500/20 text-rose-300 border-rose-500/30',
                            'text': f'Wish {title} a Happy Birthday today!'
                        })
                    elif ev_type == 'anniversary':
                        marquee_alerts.append({
                            'type': 'anniversary',
                            'icon': 'fa-solid fa-ring',
                            'badge': '💍 Anniversary Today',
                            'badge_color': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
                            'text': f'Celebration: {title} is today!'
                        })
                    else:
                        marquee_alerts.append({
                            'type': 'annual_event',
                            'icon': 'fa-solid fa-calendar-day',
                            'badge': 'Annual Event',
                            'badge_color': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
                            'text': f'Annual Event Today: "{title}"'
                        })

    # 3) Today's High Priority Events / Tasks / Deadlines
    for t in today_tasks:
        if t.get('priority') == 'High' and not t.get('completed'):
            marquee_alerts.append({
                'type': 'high_priority',
                'icon': 'fa-solid fa-fire',
                'badge': '🔥 High Priority',
                'badge_color': 'bg-rose-500/20 text-rose-300 border-rose-500/40',
                'text': f'High priority task for today: "{t.get("text")}"'
            })

    if monthly_plan and monthly_plan.calendar_days:
        today_day_str = str(today.day)
        for d_key, d_data in monthly_plan.calendar_days.items():
            if str(d_key).lstrip('0') == today_day_str:
                if isinstance(d_data, dict):
                    for citem in d_data.get('items', []):
                        is_remind = citem.get('remind_me') in [True, 'true', 'True', '1', 1, 'on']
                        if is_remind:
                            marquee_alerts.append({
                                'type': 'reminder',
                                'icon': 'fa-solid fa-bell',
                                'badge': 'Remind Me',
                                'badge_color': 'bg-amber-500/20 text-amber-300 border-amber-500/30',
                                'text': f'Reminder for today: "{citem.get("text")}"'
                            })
                        elif citem.get('type') == 'deadline' or 'interview' in citem.get('text', '').lower() or 'deadline' in citem.get('text', '').lower():
                            marquee_alerts.append({
                                'type': 'deadline',
                                'icon': 'fa-solid fa-calendar-check',
                                'badge': '⏰ Today\'s Deadline',
                                'badge_color': 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
                                'text': f'Deadline / Event scheduled today: "{citem.get("text")}"'
                            })

    planning_events = (
        PlanningEvent.query
        .filter_by(user_id=current_user.id)
        .order_by(PlanningEvent.sort_order.asc(), PlanningEvent.target_datetime.asc())
        .all()
    )

    return render_template(
        'planner/dashboard.html',
        today=today,
        today_tasks=today_tasks,
        completed_today=completed_today,
        total_today=total_today,
        today_completion_pct=today_completion_pct,
        daily_plan=daily_plan,
        monthly_plan=monthly_plan,
        monthly_goals=monthly_goals,
        monthly_habits=monthly_habits,
        goals_completed=goals_completed,
        yearly_plan=yearly_plan,
        yearly_resolutions=yearly_resolutions,
        yearly_objectives=yearly_objectives,
        current_year=current_year,
        current_month=current_month,
        month_name=month_name,
        recent_episodes=recent_episodes[:5],
        total_episodes_count=total_episodes_count,
        avg_intensity=avg_intensity,
        peak_intensity=peak_intensity,
        top_coping_strategies=top_coping_strategies,
        recent_memory_logs=recent_memory_logs[:5],
        total_memory_slips_count=total_memory_slips_count,
        memory_recovery_pct=memory_recovery_pct,
        top_memory_categories=top_memory_categories,
        today_memory_count=today_memory_count,
        recent_sleep_logs=recent_sleep_logs[:5],
        avg_sleep_hours=avg_sleep_hours,
        avg_sleep_quality=avg_sleep_quality,
        sleep_days_count=sleep_days_count,
        marquee_alerts=marquee_alerts,
        planning_events=planning_events
    )


@planner_ui.route('/daily', methods=['GET'])
@login_required
def daily():
    today = get_today_date()
    date_param = request.args.get('date')
    if date_param and date_param.lower() != 'today':
        try:
            selected_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Automatically process spillover tasks and daily routine defaults up to selected_date
    process_task_spillovers(current_user.id, selected_date)
    populate_daily_defaults(current_user.id, selected_date)

    plan = DailyPlan.query.filter_by(user_id=current_user.id, date=selected_date).first()

    # Hourly default schedule slots (12:00 - 01:00 AM to 11:00 - 12:00 AM)
    default_slots = [
        "12:00 - 01:00 AM", "01:00 - 02:00 AM", "02:00 - 03:00 AM", "03:00 - 04:00 AM",
        "04:00 - 05:00 AM", "05:00 - 06:00 AM", "06:00 - 07:00 AM", "07:00 - 08:00 AM",
        "08:00 - 09:00 AM", "09:00 - 10:00 AM", "10:00 - 11:00 AM", "11:00 - 12:00 PM",
        "12:00 - 01:00 PM", "01:00 - 02:00 PM", "02:00 - 03:00 PM", "03:00 - 04:00 PM",
        "04:00 - 05:00 PM", "05:00 - 06:00 PM", "06:00 - 07:00 PM", "07:00 - 08:00 PM",
        "08:00 - 09:00 PM", "09:00 - 10:00 PM", "10:00 - 11:00 PM", "11:00 - 12:00 AM"
    ]

    # Normalize schedule dict for 12h format & mood tracking
    raw_schedule = plan.schedule if plan and plan.schedule else {}
    normalized_schedule = {}
    legacy_map = {f'{h:02d}:00': f'{(h if (h % 12 != 0) else 12):02d}:00 {"AM" if h < 12 else "PM"}' for h in range(0, 24)}

    for slot in default_slots:
        val = raw_schedule.get(slot)
        if not val:
            start_time = slot.split(' - ')[0] if ' - ' in slot else slot
            if start_time in raw_schedule:
                val = raw_schedule[start_time]
            else:
                for k24, v12 in legacy_map.items():
                    if v12 == start_time and k24 in raw_schedule:
                        val = raw_schedule[k24]
                        break

        if isinstance(val, dict):
            normalized_schedule[slot] = val
        elif isinstance(val, str) and val:
            normalized_schedule[slot] = {'activity': val, 'mood': ''}
        else:
            normalized_schedule[slot] = {'activity': '', 'mood': ''}
    
    cascaded_items = get_all_cascaded_items_for_daily(current_user.id, selected_date)
    user_tags = get_user_tags(current_user)

    raw_tasks = plan.tasks if plan and plan.tasks else []
    sorted_tasks = sorted(raw_tasks, key=lambda t: 1 if (isinstance(t, dict) and t.get('completed')) else 0)

    # Return JSON response if requested with json format
    if request.is_json or request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        completed_count = sum(1 for t in sorted_tasks if isinstance(t, dict) and t.get('completed'))
        total_count = len(sorted_tasks)
        return jsonify({
            'success': True,
            'date': selected_date.strftime('%Y-%m-%d'),
            'is_today': selected_date == today,
            'summary': {
                'total_tasks': total_count,
                'completed_tasks': completed_count,
                'pending_tasks': total_count - completed_count,
                'completion_pct': int((completed_count / total_count * 100)) if total_count > 0 else 0
            },
            'tasks': sorted_tasks,
            'schedule': normalized_schedule,
            'notes': plan.notes if plan else '',
            'sleep_log': plan.sleep_log if plan and plan.sleep_log else {},
            'memory_logs': plan.memory_logs if plan and plan.memory_logs else [],
            'depression_episodes': plan.depression_episodes if plan and plan.depression_episodes else [],
            'cascaded_items': cascaded_items
        })

    return render_template(
        'planner/daily.html',
        selected_date=selected_date,
        today=today,
        plan=plan,
        tasks=sorted_tasks,
        schedule=normalized_schedule,
        notes=plan.notes if plan else '',
        depression_episodes=plan.depression_episodes if plan and plan.depression_episodes else [],
        memory_logs=plan.memory_logs if plan and plan.memory_logs else [],
        sleep_log=plan.sleep_log if plan and plan.sleep_log else {},
        default_slots=default_slots,
        cascaded_items=cascaded_items,
        user_tags=user_tags
    )


@planner_ui.route('/weekly', methods=['GET'])
@login_required
def weekly():
    today = get_today_date()
    current_year, current_week, _ = today.isocalendar()

    year_param = request.args.get('year', type=int)
    week_param = request.args.get('week', type=int)

    if not year_param or not week_param:
        year_param, week_param = current_year, current_week

    first_day_of_year = date(year_param, 1, 4)
    start_of_week = first_day_of_year + timedelta(weeks=week_param - 1) - timedelta(days=first_day_of_year.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    day_abbrs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    days_of_week = []
    
    # Automatically move unbought shopping list items from prior weeks to target week
    plan = carry_forward_unbought_shopping_items(current_user.id, year_param, week_param)
    if not plan:
        plan = WeeklyPlan.query.filter_by(user_id=current_user.id, year=year_param, week_number=week_param).first()

    start_year = start_of_week.year
    end_year = end_of_week.year

    yearly_plans = YearlyPlan.query.filter(YearlyPlan.user_id == current_user.id, YearlyPlan.year.in_([start_year, end_year])).all()
    yearly_map = {yp.year: yp for yp in yearly_plans}

    month_keys = list({(start_of_week.year, start_of_week.month), (end_of_week.year, end_of_week.month)})
    monthly_plans = MonthlyPlan.query.filter(
        MonthlyPlan.user_id == current_user.id,
        db.or_(*[db.and_(MonthlyPlan.year == y, MonthlyPlan.month == m) for y, m in month_keys])
    ).all()
    monthly_map = {(mp.year, mp.month): mp for mp in monthly_plans}

    days_of_week = []
    for i in range(7):
        d = start_of_week + timedelta(days=i)
        yp = yearly_map.get(d.year)
        mp = monthly_map.get((d.year, d.month))
        days_of_week.append({
            'abbr': day_abbrs[i],
            'name': d.strftime('%A'),
            'date_str': d.strftime('%b %d'),
            'full_date': d.strftime('%Y-%m-%d'),
            'date_obj': d,
            'cascaded_items': get_all_cascaded_items_for_daily(current_user.id, d, yearly_plan=yp, monthly_plan=mp, weekly_plan=plan)
        })

    goals = plan.goals if plan and plan.goals else []
    daily_todos = plan.daily_todos if plan and plan.daily_todos else {abbr: [] for abbr in day_abbrs}
    shopping_list = plan.shopping_list if plan and plan.shopping_list else []
    meals_menu = plan.meals_menu if plan and plan.meals_menu else {abbr: {'breakfast': '', 'lunch': '', 'dinner': ''} for abbr in day_abbrs}
    notes = plan.notes if plan and plan.notes else ''

    for abbr in day_abbrs:
        if abbr not in daily_todos:
            daily_todos[abbr] = []
        if abbr not in meals_menu:
            meals_menu[abbr] = {'breakfast': '', 'lunch': '', 'dinner': ''}

    # Entire Week Report calculations
    total_todos = sum(len(daily_todos.get(abbr, [])) for abbr in day_abbrs)
    completed_todos = sum(sum(1 for t in daily_todos.get(abbr, []) if t.get('completed')) for abbr in day_abbrs)
    todo_completion_pct = int((completed_todos / total_todos * 100)) if total_todos > 0 else 0

    total_goals = len(goals)
    completed_goals = sum(1 for g in goals if g.get('completed'))

    total_shopping = len(shopping_list)
    bought_shopping = sum(1 for s in shopping_list if s.get('bought'))

    meals_planned = sum(sum(1 for m_type in ['breakfast', 'lunch', 'dinner'] if meals_menu.get(abbr, {}).get(m_type)) for abbr in day_abbrs)
    meal_planning_pct = int((meals_planned / 21 * 100))

    # Depression episode summary for this week
    week_episodes = []
    week_daily_plans = DailyPlan.query.filter(
        DailyPlan.user_id == current_user.id,
        DailyPlan.date >= start_of_week,
        DailyPlan.date <= end_of_week
    ).all()
    for dp in week_daily_plans:
        if dp.depression_episodes:
            for ep in dp.depression_episodes:
                ep_copy = dict(ep)
                ep_copy['date_str'] = dp.date.strftime('%b %d')
                week_episodes.append(ep_copy)

    score_components = []
    if total_todos > 0:
        score_components.append(todo_completion_pct)
    if total_goals > 0:
        score_components.append(int(completed_goals / total_goals * 100))
    if meals_planned > 0:
        score_components.append(meal_planning_pct)
    weekly_score = int(sum(score_components) / len(score_components)) if score_components else (100 if completed_todos > 0 or completed_goals > 0 else 0)

    # Daily Planner -> Weekly Summary Cascade
    daily_tasks_done = 0
    daily_tasks_total = 0
    daily_mood_tally = {}
    for dp in week_daily_plans:
        if dp.tasks:
            daily_tasks_total += len(dp.tasks)
            daily_tasks_done += sum(1 for t in dp.tasks if t.get('completed'))
        if dp.schedule:
            for slot, sdata in dp.schedule.items():
                if isinstance(sdata, dict) and sdata.get('mood'):
                    m = sdata.get('mood')
                    daily_mood_tally[m] = daily_mood_tally.get(m, 0) + 1

    # Previous and Next week navigation helpers
    prev_week_date = start_of_week - timedelta(days=7)
    prev_year, prev_week, _ = prev_week_date.isocalendar()
    next_week_date = start_of_week + timedelta(days=7)
    next_year, next_week, _ = next_week_date.isocalendar()

    return render_template(
        'planner/weekly.html',
        selected_year=year_param,
        selected_week=week_param,
        today=today,
        current_year=current_year,
        current_week=current_week,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
        days_of_week=days_of_week,
        plan=plan,
        goals=goals,
        daily_todos=daily_todos,
        shopping_list=shopping_list,
        meals_menu=meals_menu,
        notes=notes,
        total_todos=total_todos,
        completed_todos=completed_todos,
        todo_completion_pct=todo_completion_pct,
        total_goals=total_goals,
        completed_goals=completed_goals,
        total_shopping=total_shopping,
        bought_shopping=bought_shopping,
        meals_planned=meals_planned,
        meal_planning_pct=meal_planning_pct,
        week_episodes=week_episodes,
        weekly_score=weekly_score,
        daily_tasks_done=daily_tasks_done,
        daily_tasks_total=daily_tasks_total,
        daily_mood_tally=daily_mood_tally,
        daily_planned_days=len(week_daily_plans),
        prev_year=prev_year,
        prev_week=prev_week,
        next_year=next_year,
        next_week=next_week
    )


@planner_ui.route('/monthly', methods=['GET'])
@login_required
def monthly():
    today = get_today_date()
    try:
        selected_year = int(request.args.get('year', today.year))
        selected_month = int(request.args.get('month', today.month))
    except (ValueError, TypeError):
        selected_year = today.year
        selected_month = today.month

    # Ensure valid month
    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    plan = MonthlyPlan.query.filter_by(user_id=current_user.id, year=selected_year, month=selected_month).first()

    # Auto-copy habits from the previous month when navigating to a brand-new month
    if plan is None:
        # Calculate the previous month
        if selected_month == 1:
            prev_year, prev_month = selected_year - 1, 12
        else:
            prev_year, prev_month = selected_year, selected_month - 1

        prev_plan = MonthlyPlan.query.filter_by(
            user_id=current_user.id, year=prev_year, month=prev_month
        ).first()

        inherited_habits = []
        if prev_plan and prev_plan.habits:
            inherited_habits = [
                {
                    'id': str(int(datetime.utcnow().timestamp() * 1000) + idx),
                    'name': h.get('name', ''),
                    'completed_days': []          # fresh slate for the new month
                }
                for idx, h in enumerate(prev_plan.habits)
                if h.get('name', '').strip()
            ]

        plan = MonthlyPlan(
            user_id=current_user.id,
            year=selected_year,
            month=selected_month,
            goals=[],
            habits=inherited_habits,
            milestones=[],
            calendar_days={},
            notes=''
        )
        db.session.add(plan)
        db.session.commit()

    days_in_month = calendar.monthrange(selected_year, selected_month)[1]
    month_name = calendar.month_name[selected_month]

    # Calculate exact calendar weeks for grid view (Monday to Sunday)
    cal = calendar.Calendar(firstweekday=0)
    month_weeks = cal.monthdatescalendar(selected_year, selected_month)

    # Weekly Summaries Cascade -> Monthly Planner
    first_day_of_month = date(selected_year, selected_month, 1)
    last_day_of_month = date(selected_year, selected_month, days_in_month)
    month_weekly_plans = WeeklyPlan.query.filter(
        WeeklyPlan.user_id == current_user.id,
        WeeklyPlan.start_date >= (first_day_of_month - timedelta(days=6)),
        WeeklyPlan.start_date <= last_day_of_month
    ).order_by(WeeklyPlan.start_date.asc()).all()

    weekly_summaries_list = []
    for wp in month_weekly_plans:
        w_goals = wp.goals or []
        w_goals_completed = sum(1 for g in w_goals if g.get('completed'))
        w_todos = wp.daily_todos or {}
        w_todos_total = sum(len(w_todos.get(d, [])) for d in ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])
        w_todos_completed = sum(sum(1 for t in w_todos.get(d, []) if t.get('completed')) for d in ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])

        weekly_summaries_list.append({
            'week_number': wp.week_number,
            'start_date_str': wp.start_date.strftime('%b %d'),
            'goals_done': f"{w_goals_completed}/{len(w_goals)}",
            'todos_done': f"{w_todos_completed}/{w_todos_total}",
            'notes': wp.notes or ''
        })

    cascaded_yearly_events = get_yearly_events_for_month(current_user.id, selected_year, selected_month)

    return render_template(
        'planner/monthly.html',
        selected_year=selected_year,
        selected_month=selected_month,
        month_name=month_name,
        days_in_month=days_in_month,
        month_weeks=month_weeks,
        today=today,
        plan=plan,
        goals=plan.goals if plan else [],
        habits=plan.habits if plan else [],
        milestones=plan.milestones if plan else [],
        calendar_days=plan.calendar_days if (plan and plan.calendar_days) else {},
        notes=plan.notes if plan else '',
        weekly_summaries_list=weekly_summaries_list,
        cascaded_yearly_events=cascaded_yearly_events,
        calendar=calendar
    )


@planner_ui.route('/yearly', methods=['GET'])
@login_required
def yearly():
    today = get_today_date()
    try:
        selected_year = int(request.args.get('year', today.year))
    except (ValueError, TypeError):
        selected_year = today.year

    plan = YearlyPlan.query.filter_by(user_id=current_user.id, year=selected_year).first()

    resolutions = plan.resolutions if plan and plan.resolutions else []
    objectives = plan.objectives if plan and plan.objectives else []
    events = plan.events if plan and plan.events else []
    reflections = plan.reflections if plan and plan.reflections else ''

    # Objectives grouped by quarters
    q_objectives = {
        'Q1': [o for o in objectives if o.get('quarter') == 'Q1'],
        'Q2': [o for o in objectives if o.get('quarter') == 'Q2'],
        'Q3': [o for o in objectives if o.get('quarter') == 'Q3'],
        'Q4': [o for o in objectives if o.get('quarter') == 'Q4']
    }

    # Monthly Overview Grid
    month_grid_data = []
    all_monthly_plans = MonthlyPlan.query.filter_by(user_id=current_user.id, year=selected_year).all()
    monthly_plan_map = {p.month: p for p in all_monthly_plans}

    for m in range(1, 13):
        m_plan = monthly_plan_map.get(m)
        m_goals = m_plan.goals if m_plan and m_plan.goals else []
        m_completed_goals = sum(1 for g in m_goals if g.get('status') == 'Completed')
        m_habits = m_plan.habits if m_plan and m_plan.habits else []
        m_milestones = m_plan.milestones if m_plan and m_plan.milestones else []

        month_grid_data.append({
            'month_num': m,
            'month_name': calendar.month_name[m],
            'month_abbr': calendar.month_abbr[m],
            'total_goals': len(m_goals),
            'completed_goals': m_completed_goals,
            'total_habits': len(m_habits),
            'total_milestones': len(m_milestones),
            'has_plan': m_plan is not None
        })

    # Summary metrics
    tot_events = len(events)
    tot_res = len(resolutions)
    acc_res = sum(1 for r in resolutions if r.get('completed'))
    res_pct = int((acc_res / tot_res * 100)) if tot_res > 0 else 0

    tot_obj = len(objectives)
    ach_obj = sum(1 for o in objectives if o.get('status') == 'Achieved')
    obj_pct = int((ach_obj / tot_obj * 100)) if tot_obj > 0 else 0

    return render_template(
        'planner/yearly.html',
        selected_year=selected_year,
        today=today,
        plan=plan,
        resolutions=resolutions,
        objectives=objectives,
        q_objectives=q_objectives,
        events=events,
        reflections=reflections,
        month_grid_data=month_grid_data,
        tot_events=tot_events,
        tot_res=tot_res,
        acc_res=acc_res,
        res_pct=res_pct,
        tot_obj=tot_obj,
        ach_obj=ach_obj,
        obj_pct=obj_pct
    )


@planner_ui.route('/planning', methods=['GET'])
@login_required
def planning():
    """Render the Planning page. Pending tasks: all. Completed tasks: only 10 most recent."""
    COMPLETED_PAGE_SIZE = 10
    user_tags = get_user_tags(current_user)

    # All pending tasks (ordered by sort_order, then created_at)
    pending_tasks = (
        PlanningTask.query
        .filter_by(user_id=current_user.id, completed=False)
        .order_by(PlanningTask.sort_order.asc(), PlanningTask.created_at.asc())
        .all()
    )

    # Total completed count (used to show pagination hint)
    total_completed = (
        PlanningTask.query
        .filter_by(user_id=current_user.id, completed=True)
        .count()
    )

    # Only 10 most recently completed tasks for the initial render
    recent_completed = (
        PlanningTask.query
        .filter_by(user_id=current_user.id, completed=True)
        .order_by(PlanningTask.updated_at.desc(), PlanningTask.id.desc())
        .limit(COMPLETED_PAGE_SIZE)
        .all()
    )

    tasks = pending_tasks + recent_completed

    events = (
        PlanningEvent.query
        .filter_by(user_id=current_user.id)
        .order_by(PlanningEvent.sort_order.asc(), PlanningEvent.target_datetime.asc())
        .all()
    )

    return render_template(
        'planner/planning.html',
        tasks=tasks,
        events=events,
        user_tags=user_tags,
        today=get_today_date(),
        total_completed=total_completed,
        completed_page_size=COMPLETED_PAGE_SIZE
    )


# 1. Daily Planner Excel Export
@planner_ui.route('/daily/export_excel')
@login_required
def export_daily_excel():
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = get_today_date()
    else:
        target_date = get_today_date()

    plan = DailyPlan.query.filter_by(user_id=current_user.id, date=target_date).first()

    # Tasks Sheet
    tasks_rows = [["Task ID", "Task Description", "Priority Level", "Completion Status"]]
    if plan and plan.tasks:
        for t in plan.tasks:
            tasks_rows.append([
                str(t.get('id', '')),
                str(t.get('text', '')),
                str(t.get('priority', 'Medium')),
                "Completed" if t.get('completed') else "Pending"
            ])

    # Hourly Schedule & Mood Sheet
    default_slots = [
        "12:00 - 01:00 AM", "01:00 - 02:00 AM", "02:00 - 03:00 AM", "03:00 - 04:00 AM",
        "04:00 - 05:00 AM", "05:00 - 06:00 AM", "06:00 - 07:00 AM", "07:00 - 08:00 AM",
        "08:00 - 09:00 AM", "09:00 - 10:00 AM", "10:00 - 11:00 AM", "11:00 - 12:00 PM",
        "12:00 - 01:00 PM", "01:00 - 02:00 PM", "02:00 - 03:00 PM", "03:00 - 04:00 PM",
        "04:00 - 05:00 PM", "05:00 - 06:00 PM", "06:00 - 07:00 PM", "07:00 - 08:00 PM",
        "08:00 - 09:00 PM", "09:00 - 10:00 PM", "10:00 - 11:00 PM", "11:00 - 12:00 AM"
    ]
    schedule_rows = [["Time Slot", "Activity Details", "Hourly Mood Tag"]]
    raw_schedule = plan.schedule if plan and plan.schedule else {}
    for slot in default_slots:
        val = raw_schedule.get(slot, {})
        act = val.get('activity', '') if isinstance(val, dict) else str(val or '')
        mood = val.get('mood', '') if isinstance(val, dict) else ''
        schedule_rows.append([slot, act, mood])

    # Depression Episodes Sheet
    episodes_rows = [["Episode ID", "Time Logged", "Start Time", "Duration", "Intensity (1-10)", "Triggers / Symptoms", "Coping Mechanism", "Effectiveness", "Personal Notes"]]
    if plan and plan.depression_episodes:
        for ep in plan.depression_episodes:
            episodes_rows.append([
                str(ep.get('id', '')),
                str(ep.get('entry_time', '')),
                str(ep.get('start_time', '')),
                str(ep.get('duration', '')),
                str(ep.get('intensity', 5)),
                str(ep.get('triggers', '')),
                str(ep.get('coping_mechanism', '')),
                str(ep.get('coping_effectiveness', '')),
                str(ep.get('notes', ''))
            ])

    # Memory Tracker Sheet
    memory_rows = [["Log ID", "Time Logged", "Time of Slip", "Forgotten Detail / Task", "Category", "Trigger / Context", "Impact Level", "Recovery Status", "Notes"]]
    if plan and plan.memory_logs:
        for m in plan.memory_logs:
            memory_rows.append([
                str(m.get('id', '')),
                str(m.get('entry_time', '')),
                str(m.get('time', '')),
                str(m.get('item', '')),
                str(m.get('category', '')),
                str(m.get('context', '')),
                str(m.get('impact', '')),
                str(m.get('recovery', '')),
                str(m.get('notes', ''))
            ])

    # Sleep Tracker Sheet
    s_log = plan.sleep_log if plan and plan.sleep_log else {}
    sleep_rows = [
        ["Metric", "Value"],
        ["Sleep Duration (Hours)", f"{s_log.get('hours', 0)} hrs"],
        ["Bedtime", s_log.get('bedtime', 'N/A')],
        ["Wake-up Time", s_log.get('wake_time', 'N/A')],
        ["Sleep Quality (1-10)", s_log.get('quality', 'N/A')],
        ["Disruptions", s_log.get('disruptions', 'None')],
        ["Sleep Notes & Factors", s_log.get('notes', '')]
    ]

    # Notes Sheet
    notes_rows = [["Section", "Content"], ["Daily Reflection & Notes", plan.notes if plan else '']]

    excel_file = create_styled_excel(
        f"Chronos Daily Planner - {target_date.strftime('%B %d, %Y')}",
        {
            "Daily Tasks": tasks_rows,
            "Hourly Activity & Mood": schedule_rows,
            "Sleep Tracker": sleep_rows,
            "Depression Tracker": episodes_rows,
            "Memory Tracker": memory_rows,
            "Daily Reflection": notes_rows
        }
    )

    filename = f"Daily_Planner_{target_date.strftime('%Y_%m_%d')}.xlsx"
    return send_file(excel_file, download_name=filename, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# 2. Weekly Planner Excel Export
@planner_ui.route('/weekly/export_excel')
@login_required
def export_weekly_excel():
    year_param = request.args.get('year', type=int)
    week_param = request.args.get('week', type=int)
    today = get_today_date()
    if not year_param or not week_param:
        year_param, week_param, _ = today.isocalendar()

    plan = WeeklyPlan.query.filter_by(user_id=current_user.id, year=year_param, week_number=week_param).first()

    # Goals Sheet
    goals_rows = [["Goal ID", "Weekly Goal Title", "Status"]]
    if plan and plan.goals:
        for g in plan.goals:
            goals_rows.append([str(g.get('id', '')), str(g.get('title', '')), "Achieved" if g.get('completed') else "In Progress"])

    # Shopping List Sheet
    shopping_rows = [["Item ID", "Shopping Item Name", "Category", "Bought Status"]]
    if plan and plan.shopping_list:
        for s in plan.shopping_list:
            shopping_rows.append([str(s.get('id', '')), str(s.get('item', '')), str(s.get('category', 'Groceries')), "Bought" if s.get('bought') else "Pending"])

    # 7-Day To-Dos Grid Sheet
    day_abbrs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    todos_rows = [["Day", "To-Do Description", "Status"]]
    daily_todos = plan.daily_todos if plan and plan.daily_todos else {}
    for d in day_abbrs:
        for t in daily_todos.get(d, []):
            todos_rows.append([d, str(t.get('text', '')), "Completed" if t.get('completed') else "Pending"])

    # Meals Menu Sheet
    meals_rows = [["Day", "Breakfast", "Lunch", "Dinner"]]
    meals_menu = plan.meals_menu if plan and plan.meals_menu else {}
    for d in day_abbrs:
        dm = meals_menu.get(d, {})
        meals_rows.append([d, str(dm.get('breakfast', '')), str(dm.get('lunch', '')), str(dm.get('dinner', ''))])

    # Notes Sheet
    notes_rows = [["Section", "Content"], ["Weekly Reflection & Notes", plan.notes if plan else '']]

    excel_file = create_styled_excel(
        f"Chronos Weekly Planner - Week {week_param}, {year_param}",
        {
            "Weekly Goals": goals_rows,
            "Shopping List": shopping_rows,
            "7-Day To-Dos": todos_rows,
            "Meals Menu": meals_rows,
            "Weekly Reflection": notes_rows
        }
    )

    filename = f"Weekly_Planner_{year_param}_W{week_param:02d}.xlsx"
    return send_file(excel_file, download_name=filename, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# 3. Monthly Planner Excel Export
@planner_ui.route('/monthly/export_excel')
@login_required
def export_monthly_excel():
    today = get_today_date()
    try:
        selected_year = int(request.args.get('year', today.year))
        selected_month = int(request.args.get('month', today.month))
    except (ValueError, TypeError):
        selected_year = today.year
        selected_month = today.month

    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    plan = MonthlyPlan.query.filter_by(user_id=current_user.id, year=selected_year, month=selected_month).first()
    month_name = calendar.month_name[selected_month]

    # Goals Sheet
    goals_rows = [["Goal ID", "Goal Title", "Category", "Target Deadline", "Status"]]
    if plan and plan.goals:
        for g in plan.goals:
            goals_rows.append([
                str(g.get('id', '')),
                str(g.get('title', '')),
                str(g.get('category', 'General')),
                str(g.get('deadline', '')),
                str(g.get('status', 'In Progress'))
            ])

    # Habits Sheet
    days_in_month = calendar.monthrange(selected_year, selected_month)[1]
    habit_headers = ["Habit ID", "Habit Name", "Total Days Completed", "Completion Pct", "Completed Days"]
    habits_rows = [habit_headers]
    if plan and plan.habits:
        for h in plan.habits:
            cdays = h.get('completed_days', [])
            c_count = len(cdays)
            pct = f"{int(c_count / days_in_month * 100)}%" if days_in_month > 0 else "0%"
            habits_rows.append([
                str(h.get('id', '')),
                str(h.get('name', '')),
                c_count,
                pct,
                ", ".join(str(d) for d in sorted(cdays))
            ])

    # Milestones Sheet
    milestones_rows = [["Milestone ID", "Milestone Title", "Target Day", "Status"]]
    if plan and plan.milestones:
        for m in plan.milestones:
            milestones_rows.append([
                str(m.get('id', '')),
                str(m.get('title', '')),
                f"Day {m.get('date', '')}",
                "Achieved" if m.get('completed') else "Pending"
            ])

    # Calendar Days Sheet
    calendar_rows = [["Day", "Type", "Event / Task / Reminder Text", "Remind Me Alert"]]
    if plan and plan.calendar_days:
        for d in range(1, days_in_month + 1):
            d_str = str(d)
            d_data = plan.calendar_days.get(d_str, {})
            if isinstance(d_data, dict):
                items = d_data.get('items', [])
                for item in items:
                    calendar_rows.append([
                        f"{month_name} {d}",
                        str(item.get('type', 'task')),
                        str(item.get('text', '')),
                        "Yes" if item.get('remind_me') else "No"
                    ])

    # Notes Sheet
    notes_rows = [["Section", "Content"], ["Monthly Reflection & Notes", plan.notes if plan else '']]

    excel_file = create_styled_excel(
        f"Chronos Monthly Planner - {month_name} {selected_year}",
        {
            "Monthly Goals": goals_rows,
            "Habit Tracker": habits_rows,
            "Key Milestones": milestones_rows,
            "Calendar Events": calendar_rows,
            "Monthly Reflection": notes_rows
        }
    )

    filename = f"Monthly_Planner_{selected_year}_{selected_month:02d}.xlsx"
    return send_file(excel_file, download_name=filename, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# 4. Yearly Planner Excel Export
@planner_ui.route('/yearly/export_excel')
@login_required
def export_yearly_excel():
    today = get_today_date()
    try:
        selected_year = int(request.args.get('year', today.year))
    except (ValueError, TypeError):
        selected_year = today.year

    plan = YearlyPlan.query.filter_by(user_id=current_user.id, year=selected_year).first()

    # Resolutions Sheet
    res_rows = [["Resolution ID", "Resolution Description", "Category", "Status"]]
    if plan and plan.resolutions:
        for r in plan.resolutions:
            res_rows.append([
                str(r.get('id', '')),
                str(r.get('text', '')),
                str(r.get('category', 'Personal')),
                "Accomplished" if r.get('completed') else "In Progress"
            ])

    # Objectives Sheet
    obj_rows = [["Objective ID", "Quarter", "Objective Title", "Status"]]
    if plan and plan.objectives:
        for o in plan.objectives:
            obj_rows.append([
                str(o.get('id', '')),
                str(o.get('quarter', 'Q1')),
                str(o.get('title', '')),
                str(o.get('status', 'In Progress'))
            ])

    # Yearly Events & Milestones Sheet
    events_rows = [["Event ID", "Date", "Event Title", "Type", "Notes", "Status"]]
    if plan and plan.events:
        for ev in plan.events:
            events_rows.append([
                str(ev.get('id', '')),
                str(ev.get('date', '')),
                str(ev.get('title', '')),
                str(ev.get('event_type', 'goal')),
                str(ev.get('notes', '')),
                "Completed" if ev.get('completed') else "Pending"
            ])

    # Reflections Sheet
    ref_rows = [["Section", "Content"], ["Yearly Reflections & Summary", plan.reflections if plan else '']]

    excel_file = create_styled_excel(
        f"Chronos Yearly Planner - {selected_year}",
        {
            "Resolutions": res_rows,
            "Quarterly Objectives": obj_rows,
            "Yearly Events": events_rows,
            "Yearly Reflections": ref_rows
        }
    )

    filename = f"Yearly_Planner_{selected_year}.xlsx"
    return send_file(excel_file, download_name=filename, as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
