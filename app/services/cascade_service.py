from datetime import datetime, date
from app.models import YearlyPlan, MonthlyPlan, WeeklyPlan

def get_yearly_events_for_month(user_id, year, month):
    """
    Yearly -> Monthly Cascade
    Retrieves events/goals from YearlyPlan that belong to the specified year and month.
    """
    yearly_plan = YearlyPlan.query.filter_by(user_id=user_id, year=year).first()
    if not yearly_plan or not yearly_plan.events:
        return []

    month_events = []
    for ev in yearly_plan.events:
        ev_date_str = ev.get('date', '')
        if not ev_date_str:
            continue
        try:
            ev_date = datetime.strptime(ev_date_str, '%Y-%m-%d').date()
            if ev_date.month == month and ev_date.year == year:
                item = dict(ev)
                item['source'] = 'yearly'
                month_events.append(item)
        except ValueError:
            # Check if it's MM-DD format for annual recurring events
            try:
                parts = ev_date_str.split('-')
                if len(parts) == 2 and int(parts[0]) == month:
                    item = dict(ev)
                    item['source'] = 'yearly'
                    month_events.append(item)
            except Exception:
                pass
    return month_events


def get_monthly_items_for_date(user_id, date_obj, monthly_plan=None):
    """
    Monthly -> Weekly/Daily Cascade
    Retrieves calendar items and milestones from MonthlyPlan for a specific date.
    """
    year = date_obj.year
    month = date_obj.month
    day_str = str(date_obj.day)

    if monthly_plan is None:
        monthly_plan = MonthlyPlan.query.filter_by(user_id=user_id, year=year, month=month).first()

    if not monthly_plan:
        return []

    cascaded_items = []

    # Calendar items
    calendar_days = monthly_plan.calendar_days or {}
    day_data = calendar_days.get(day_str, {})
    items = day_data.get('items', []) if isinstance(day_data, dict) else []
    for item in items:
        c_item = dict(item)
        c_item['source'] = 'monthly'
        c_item['source_type'] = 'calendar_item'
        cascaded_items.append(c_item)

    # Milestones
    milestones = monthly_plan.milestones or []
    for ms in milestones:
        ms_day = str(ms.get('day', '')).strip()
        if ms_day == day_str:
            c_ms = dict(ms)
            c_ms['source'] = 'monthly'
            c_ms['source_type'] = 'milestone'
            cascaded_items.append(c_ms)

    return cascaded_items


def get_weekly_todos_for_date(user_id, date_obj, weekly_plan=None):
    """
    Weekly -> Daily Cascade
    Retrieves to-do items from WeeklyPlan daily_todos grid matching the specific date.
    """
    year, week_num, weekday = date_obj.isocalendar()
    day_abbrs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_abbr = day_abbrs[weekday - 1]

    if weekly_plan is None:
        weekly_plan = WeeklyPlan.query.filter_by(user_id=user_id, year=year, week_number=week_num).first()

    if not weekly_plan or not weekly_plan.daily_todos:
        return []

    todos = weekly_plan.daily_todos.get(day_abbr, [])
    cascaded_todos = []
    for t in todos:
        c_todo = dict(t)
        c_todo['source'] = 'weekly'
        c_todo['day_abbr'] = day_abbr
        cascaded_todos.append(c_todo)

    return cascaded_todos


def get_all_cascaded_items_for_daily(user_id, date_obj, yearly_plan=None, monthly_plan=None, weekly_plan=None):
    """
    Combines all cascaded items (Yearly -> Daily, Monthly -> Daily, Weekly -> Daily)
    for rendering within the Daily Planner. Accepts pre-fetched plans for maximum performance.
    """
    cascaded_items = []

    # 1. Yearly Events for this date
    if yearly_plan is None:
        yearly_plan = YearlyPlan.query.filter_by(user_id=user_id, year=date_obj.year).first()

    if yearly_plan and yearly_plan.events:
        for ev in yearly_plan.events:
            ev_date_str = ev.get('date', '')
            if not ev_date_str:
                continue
            is_match = False
            try:
                ev_date = datetime.strptime(ev_date_str, '%Y-%m-%d').date()
                if ev_date == date_obj:
                    is_match = True
            except ValueError:
                # Check recurring MM-DD
                try:
                    parts = [int(p) for p in ev_date_str.split('-')]
                    if len(parts) == 2 and parts[0] == date_obj.month and parts[1] == date_obj.day:
                        is_match = True
                except Exception:
                    pass

            if is_match:
                c_ev = dict(ev)
                c_ev['source'] = 'yearly'
                cascaded_items.append(c_ev)

    # 2. Monthly items for this date
    cascaded_items.extend(get_monthly_items_for_date(user_id, date_obj, monthly_plan=monthly_plan))

    # 3. Weekly todos for this date
    cascaded_items.extend(get_weekly_todos_for_date(user_id, date_obj, weekly_plan=weekly_plan))

    return cascaded_items
