import os
import io
import json
import calendar
from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, redirect, url_for, flash, send_file
from sqlalchemy.orm.attributes import flag_modified
from app import db
from app.models import DailyPlan, MonthlyPlan, YearlyPlan, WeeklyPlan, User, PlanningTask, PlanningEvent
from app.auth_middleware import token_required
from app.services.cascade_service import (
    get_yearly_events_for_month,
    get_monthly_items_for_date,
    get_weekly_todos_for_date,
    get_all_cascaded_items_for_daily
)
from app.planner_helpers import (
    DEFAULT_TAGS,
    get_current_user_safe,
    get_user_tags,
    get_today_date,
    to_24h_time,
    format_time_12h,
    process_task_spillovers,
    populate_daily_defaults,
    carry_forward_unbought_shopping_items
)

planner_api = Blueprint('planner_api', __name__)


# ============================================================================
# DAILY PLANNER REST API ENDPOINTS
# ============================================================================

@planner_api.route('/api/daily/today', methods=['GET'])
@planner_api.route('/api/daily', methods=['GET'])
@token_required
def api_daily_plan():
    """
    Get daily plan details, tasks, schedule, and mood trackers for a given date.
    ---
    tags:
      - Daily Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: date
        type: string
        required: false
        description: Date in YYYY-MM-DD format (defaults to current date in configured timezone)
    responses:
      200:
        description: Daily plan data retrieved successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            date:
              type: string
              example: "2026-08-19"
            is_today:
              type: boolean
              example: true
            summary:
              type: object
              properties:
                total_tasks:
                  type: integer
                completed_tasks:
                  type: integer
                pending_tasks:
                  type: integer
                completion_pct:
                  type: integer
            tasks:
              type: array
              items:
                type: object
            schedule:
              type: object
            notes:
              type: string
      401:
        description: Unauthorized - Invalid or missing token
    """
    user = get_current_user_safe()
    today = get_today_date()
    date_param = request.args.get('date')
    if date_param and date_param.lower() != 'today':
        try:
            selected_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Process spillovers and defaults up to selected_date
    process_task_spillovers(user.id, selected_date)
    populate_daily_defaults(user.id, selected_date)

    plan = DailyPlan.query.filter_by(user_id=user.id, date=selected_date).first()

    default_slots = [
        "12:00 - 01:00 AM", "01:00 - 02:00 AM", "02:00 - 03:00 AM", "03:00 - 04:00 AM",
        "04:00 - 05:00 AM", "05:00 - 06:00 AM", "06:00 - 07:00 AM", "07:00 - 08:00 AM",
        "08:00 - 09:00 AM", "09:00 - 10:00 AM", "10:00 - 11:00 AM", "11:00 - 12:00 PM",
        "12:00 - 01:00 PM", "01:00 - 02:00 PM", "02:00 - 03:00 PM", "03:00 - 04:00 PM",
        "04:00 - 05:00 PM", "05:00 - 06:00 PM", "06:00 - 07:00 PM", "07:00 - 08:00 PM",
        "08:00 - 09:00 PM", "09:00 - 10:00 PM", "10:00 - 11:00 PM", "11:00 - 12:00 AM"
    ]

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

    cascaded_items = get_all_cascaded_items_for_daily(user.id, selected_date)
    raw_tasks = plan.tasks if plan and plan.tasks else []
    sorted_tasks = sorted(raw_tasks, key=lambda t: 1 if (isinstance(t, dict) and t.get('completed')) else 0)

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


@planner_api.route('/daily', methods=['POST'])
@token_required
def api_daily_post():
    """
    Handle daily plan mutations (adding/deleting tasks, saving schedule, notes, sleep log, symptom logs).
    ---
    tags:
      - Daily Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: date
        type: string
        required: false
        description: Target date in YYYY-MM-DD format
      - in: body
        name: body
        schema:
          type: object
          properties:
            action:
              type: string
              enum: [add_task, delete_task, save_schedule, save_notes, add_depression_episode, delete_depression_episode, add_memory_log, delete_memory_log, save_sleep_log]
            task_text:
              type: string
            priority:
              type: string
            tags:
              type: array
              items:
                type: string
    responses:
      200:
        description: Operation completed successfully
      400:
        description: Invalid action or parameters
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    today = get_today_date()
    date_param = request.args.get('date') or (request.get_json(silent=True) or {}).get('date')
    if date_param and str(date_param).lower() != 'today':
        try:
            selected_date = datetime.strptime(str(date_param), '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    process_task_spillovers(user.id, selected_date)
    populate_daily_defaults(user.id, selected_date)

    plan = DailyPlan.query.filter_by(user_id=user.id, date=selected_date).first()
    if not plan:
        plan = DailyPlan(user_id=user.id, date=selected_date, schedule={}, tasks=[], notes='')
        db.session.add(plan)

    json_data = request.get_json(silent=True) or {}
    action = json_data.get('action') or request.form.get('action')
    tasks = plan.tasks or []

    if action == 'add_task':
        task_text = (json_data.get('task_text') or request.form.get('task_text', '')).strip()
        priority = json_data.get('priority') or request.form.get('priority', 'Medium')
        is_default = bool(json_data.get('is_default') or request.form.get('is_default'))
        task_tags = json_data.get('tags') or request.form.getlist('tags') or (request.form.get('tags', '').split(',') if request.form.get('tags') else [])
        if isinstance(task_tags, str):
            task_tags = [t.strip() for t in task_tags.split(',') if t.strip()]
        else:
            task_tags = [t.strip() for t in task_tags if isinstance(t, str) and t.strip()]

        if task_text:
            new_task = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'text': task_text,
                'priority': priority,
                'tags': task_tags,
                'completed': False,
                'is_default': is_default,
                'is_spillover': False,
                'spillover_count': 0,
                'original_date': selected_date.strftime('%Y-%m-%d')
            }
            tasks.append(new_task)
            plan.tasks = tasks
            flag_modified(plan, 'tasks')

            raw_sched = plan.schedule or {}
            if isinstance(raw_sched, dict):
                t_key = task_text.lower()
                deleted_defs = [d for d in raw_sched.get('_deleted_defaults', []) if str(d).lower() != t_key]
                dismissed = [d for d in raw_sched.get('_dismissed_tasks', []) if str(d).lower() != t_key]
                if len(deleted_defs) != len(raw_sched.get('_deleted_defaults', [])) or len(dismissed) != len(raw_sched.get('_dismissed_tasks', [])):
                    raw_sched['_deleted_defaults'] = deleted_defs
                    raw_sched['_dismissed_tasks'] = dismissed
                    plan.schedule = raw_sched
                    flag_modified(plan, 'schedule')

            db.session.commit()
            flash('Task added successfully!', 'success')

    elif action == 'delete_task':
        task_id = json_data.get('task_id') or request.form.get('task_id')
        deleted_task = None
        for t in tasks:
            if isinstance(t, dict) and t.get('id') == task_id:
                deleted_task = t
                break

        plan.tasks = [t for t in tasks if isinstance(t, dict) and t.get('id') != task_id]
        raw_sched = plan.schedule or {}
        if not isinstance(raw_sched, dict):
            raw_sched = {}

        dismissed = list(raw_sched.get('_dismissed_tasks', []))
        deleted_defs = list(raw_sched.get('_deleted_defaults', []))

        if task_id not in dismissed:
            dismissed.append(task_id)

        if deleted_task:
            t_text = deleted_task.get('text', '').strip().lower()
            if t_text and t_text not in deleted_defs:
                deleted_defs.append(t_text)
            if task_id not in deleted_defs:
                deleted_defs.append(task_id)

        raw_sched['_dismissed_tasks'] = dismissed
        raw_sched['_deleted_defaults'] = deleted_defs
        plan.schedule = raw_sched
        flag_modified(plan, 'schedule')
        flag_modified(plan, 'tasks')
        db.session.commit()
        flash('Task deleted.', 'info')

    elif action == 'save_schedule':
        new_schedule = {}
        default_slots = [
            "12:00 - 01:00 AM", "01:00 - 02:00 AM", "02:00 - 03:00 AM", "03:00 - 04:00 AM",
            "04:00 - 05:00 AM", "05:00 - 06:00 AM", "06:00 - 07:00 AM", "07:00 - 08:00 AM",
            "08:00 - 09:00 AM", "09:00 - 10:00 AM", "10:00 - 11:00 AM", "11:00 - 12:00 PM",
            "12:00 - 01:00 PM", "01:00 - 02:00 PM", "02:00 - 03:00 PM", "03:00 - 04:00 PM",
            "04:00 - 05:00 PM", "05:00 - 06:00 PM", "06:00 - 07:00 PM", "07:00 - 08:00 PM",
            "08:00 - 09:00 PM", "09:00 - 10:00 PM", "10:00 - 11:00 PM", "11:00 - 12:00 AM"
        ]
        raw_sched = plan.schedule or {}
        if isinstance(raw_sched, dict):
            for k, v in raw_sched.items():
                if k.startswith('_'):
                    new_schedule[k] = v

        for time_slot in default_slots:
            slot_id = time_slot.replace(':', '_').replace(' ', '_').replace('-', '_')
            meridiem = time_slot.split(' ')[-1] if ' ' in time_slot else ''
            start_part = time_slot.split(' - ')[0] if ' - ' in time_slot else time_slot
            start_time = f"{start_part} {meridiem}".strip() if meridiem and not start_part.endswith(meridiem) else start_part
            start_slot_id = start_time.replace(':', '_').replace(' ', '_')
            json_slot = json_data.get(time_slot) if isinstance(json_data.get(time_slot), dict) else {}
            act = (request.form.get(f'slot_act_{slot_id}') or request.form.get(f'slot_act_{start_slot_id}') or request.form.get(f'slot_{time_slot}') or json_slot.get('activity', '') or '').strip()
            mood = (request.form.get(f'slot_mood_{slot_id}') or request.form.get(f'slot_mood_{start_slot_id}') or json_slot.get('mood', '') or '').strip()
            is_def = bool(request.form.get(f'slot_def_{slot_id}') or request.form.get(f'slot_def_{start_slot_id}') or json_slot.get('is_default', False))

            if act or mood or is_def or (isinstance(raw_sched, dict) and time_slot in raw_sched):
                new_schedule[time_slot] = {'activity': act, 'mood': mood, 'is_default': is_def}

        plan.schedule = new_schedule
        flag_modified(plan, 'schedule')
        db.session.commit()
        if not (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == 'true'):
            flash('Hourly activity & mood tracker saved successfully!', 'success')

    elif action == 'save_notes':
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()
        plan.notes = notes
        db.session.commit()
        if not (request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == 'true'):
            flash('Notes updated!', 'success')

    elif action == 'add_depression_episode':
        start_time = (json_data.get('start_time') or request.form.get('start_time', '')).strip() or 'N/A'
        duration = (json_data.get('duration') or request.form.get('duration', '')).strip() or 'N/A'
        try:
            intensity = int(json_data.get('intensity') or request.form.get('intensity', 5))
        except ValueError:
            intensity = 5
        triggers = (json_data.get('triggers') or request.form.get('triggers', '')).strip()
        coping_mechanism = (json_data.get('coping_mechanism') or request.form.get('coping_mechanism', '')).strip()
        coping_effectiveness = (json_data.get('coping_effectiveness') or request.form.get('coping_effectiveness', 'Helpful')).strip()
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()
        entry_time = datetime.now().strftime('%I:%M %p')

        new_episode = {
            'id': str(int(datetime.utcnow().timestamp() * 1000)),
            'entry_time': entry_time,
            'start_time': start_time,
            'duration': duration,
            'intensity': intensity,
            'triggers': triggers,
            'coping_mechanism': coping_mechanism,
            'coping_effectiveness': coping_effectiveness,
            'notes': notes
        }

        episodes = plan.depression_episodes or []
        episodes.append(new_episode)
        plan.depression_episodes = episodes
        flag_modified(plan, 'depression_episodes')
        db.session.commit()
        flash('Depression episode & symptom logged.', 'success')

    elif action == 'delete_depression_episode':
        episode_id = json_data.get('episode_id') or request.form.get('episode_id')
        episodes = plan.depression_episodes or []
        plan.depression_episodes = [ep for ep in episodes if ep.get('id') != episode_id]
        flag_modified(plan, 'depression_episodes')
        db.session.commit()
        flash('Depression episode record deleted.', 'info')

    elif action == 'add_memory_log':
        time_val = (json_data.get('time') or request.form.get('time', '')).strip() or 'N/A'
        item = (json_data.get('item') or request.form.get('item', '')).strip()
        category = (json_data.get('category') or request.form.get('category', 'General')).strip()
        context = (json_data.get('context') or request.form.get('context', '')).strip()
        impact = (json_data.get('impact') or request.form.get('impact', 'Mild')).strip()
        recovery = (json_data.get('recovery') or request.form.get('recovery', 'Remembered later')).strip()
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()
        entry_time = datetime.now().strftime('%I:%M %p')

        new_log = {
            'id': str(int(datetime.utcnow().timestamp() * 1000)),
            'entry_time': entry_time,
            'time': time_val,
            'item': item,
            'category': category,
            'context': context,
            'impact': impact,
            'recovery': recovery,
            'notes': notes
        }

        logs = plan.memory_logs or []
        logs.append(new_log)
        plan.memory_logs = logs
        flag_modified(plan, 'memory_logs')
        db.session.commit()
        flash('Memory slip logged successfully.', 'success')

    elif action == 'delete_memory_log':
        log_id = json_data.get('log_id') or request.form.get('log_id')
        logs = plan.memory_logs or []
        plan.memory_logs = [m for m in logs if m.get('id') != log_id]
        flag_modified(plan, 'memory_logs')
        db.session.commit()
        flash('Memory log record deleted.', 'info')

    elif action == 'save_sleep_log':
        try:
            hours = float(json_data.get('sleep_hours') or request.form.get('sleep_hours', 7.0))
        except ValueError:
            hours = 7.0
        try:
            quality = int(json_data.get('sleep_quality') or request.form.get('sleep_quality', 8))
        except ValueError:
            quality = 8

        bedtime_24h = (json_data.get('bedtime') or request.form.get('bedtime', '')).strip() or '23:00'
        wake_time_24h = (json_data.get('wake_time') or request.form.get('wake_time', '')).strip() or '06:30'
        disruptions = (json_data.get('disruptions') or request.form.get('disruptions', 'None')).strip()
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()

        plan.sleep_log = {
            'hours': hours,
            'bedtime': format_time_12h(bedtime_24h, '11:00 PM'),
            'bedtime_24h': bedtime_24h,
            'wake_time': format_time_12h(wake_time_24h, '6:30 AM'),
            'wake_time_24h': wake_time_24h,
            'quality': quality,
            'disruptions': disruptions,
            'notes': notes,
            'updated_at': datetime.now().strftime('%I:%M %p')
        }
        flag_modified(plan, 'sleep_log')
        db.session.commit()
        flash('Sleep tracker metrics saved successfully.', 'success')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == 'true':
        return jsonify({'success': True, 'action': action, 'message': 'Operation completed successfully'})
    return redirect(url_for('planner_ui.daily', date=selected_date.strftime('%Y-%m-%d')))


@planner_api.route('/api/daily/task/toggle', methods=['POST'])
@token_required
def api_toggle_task():
    """
    Toggle a daily task's completion status.
    ---
    tags:
      - Daily Tasks
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - task_id
          properties:
            date:
              type: string
              description: Date of the plan (YYYY-MM-DD)
            task_id:
              type: string
              description: ID of the task to toggle
    responses:
      200:
        description: Task toggled successfully
      400:
        description: Missing arguments or invalid date
      401:
        description: Unauthorized
      404:
        description: Plan or task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    task_id = data.get('task_id')

    if not date_str or not task_id:
        return jsonify({'success': False, 'message': 'Missing arguments'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Plan not found'}), 404

    tasks = plan.tasks or []
    updated = False
    new_state = False

    for t in tasks:
        if t.get('id') == task_id:
            t['completed'] = not t.get('completed', False)
            new_state = t['completed']
            updated = True
            break

    if updated:
        plan.tasks = tasks
        flag_modified(plan, 'tasks')
        db.session.commit()
        return jsonify({'success': True, 'completed': new_state})
    
    return jsonify({'success': False, 'message': 'Task not found'}), 404


@planner_api.route('/api/daily/task/reorder', methods=['POST'])
@token_required
def api_reorder_tasks():
    """
    Reorder tasks for a specific daily plan.
    ---
    tags:
      - Daily Tasks
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - task_ids
          properties:
            date:
              type: string
            task_ids:
              type: array
              items:
                type: string
    responses:
      200:
        description: Tasks reordered successfully
      400:
        description: Invalid arguments
      401:
        description: Unauthorized
      404:
        description: Plan not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    task_ids = data.get('task_ids', [])

    if not date_str or not isinstance(task_ids, list):
        return jsonify({'success': False, 'message': 'Missing or invalid arguments'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Plan not found'}), 404

    tasks = plan.tasks or []
    task_map = {t.get('id'): t for t in tasks if isinstance(t, dict) and t.get('id')}

    reordered = []
    for tid in task_ids:
        if tid in task_map:
            reordered.append(task_map.pop(tid))

    reordered.extend(task_map.values())
    plan.tasks = reordered
    flag_modified(plan, 'tasks')
    db.session.commit()
    return jsonify({'success': True})


@planner_api.route('/api/daily/task/edit', methods=['POST'])
@token_required
def api_edit_task():
    """
    Edit attributes of an existing daily task (text, priority, status, tags, note, default).
    ---
    tags:
      - Daily Tasks
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - task_id
          properties:
            date:
              type: string
            task_id:
              type: string
            text:
              type: string
            priority:
              type: string
            tags:
              type: array
              items:
                type: string
            status:
              type: string
            note:
              type: string
            is_default:
              type: boolean
    responses:
      200:
        description: Task updated successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
      404:
        description: Task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    task_id = data.get('task_id')
    new_text = data.get('text', '').strip() if 'text' in data else None
    new_priority = data.get('priority')
    is_default = bool(data.get('is_default')) if 'is_default' in data else None
    new_tags = data.get('tags')
    new_status = data.get('status')
    new_note = data.get('note')

    if not date_str or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Plan not found'}), 404

    tasks = plan.tasks or []
    updated = False

    for t in tasks:
        if isinstance(t, dict) and t.get('id') == task_id:
            old_text = t.get('text', '').strip().lower()
            old_is_default = t.get('is_default', False)

            if new_text is not None:
                t['text'] = new_text
            if new_priority is not None:
                t['priority'] = new_priority
            if is_default is not None:
                t['is_default'] = is_default
                if old_is_default and not is_default:
                    raw_sched = plan.schedule or {}
                    if not isinstance(raw_sched, dict):
                        raw_sched = {}
                    deleted_defs = list(raw_sched.get('_deleted_defaults', []))
                    if old_text and old_text not in deleted_defs:
                        deleted_defs.append(old_text)
                    if task_id not in deleted_defs:
                        deleted_defs.append(task_id)
                    raw_sched['_deleted_defaults'] = deleted_defs
                    plan.schedule = raw_sched
                    flag_modified(plan, 'schedule')
                elif is_default:
                    raw_sched = plan.schedule or {}
                    if isinstance(raw_sched, dict):
                        t_key = (new_text or t.get('text', '')).lower()
                        deleted_defs = [d for d in raw_sched.get('_deleted_defaults', []) if str(d).lower() != t_key and str(d) != task_id]
                        dismissed = [d for d in raw_sched.get('_dismissed_tasks', []) if str(d).lower() != t_key and str(d) != task_id]
                        raw_sched['_deleted_defaults'] = deleted_defs
                        raw_sched['_dismissed_tasks'] = dismissed
                        plan.schedule = raw_sched
                        flag_modified(plan, 'schedule')
            if new_tags is not None:
                if isinstance(new_tags, str):
                    new_tags = [x.strip() for x in new_tags.split(',') if x.strip()]
                t['tags'] = new_tags
            if new_status is not None:
                st = str(new_status).strip()
                t['status'] = st
                if st == 'Completed':
                    t['completed'] = True
                elif st in ['To Do', 'In Progress', 'Undone']:
                    t['completed'] = False
            if new_note is not None:
                t['note'] = str(new_note).strip()
            updated = True
            break

    if updated:
        plan.tasks = tasks
        flag_modified(plan, 'tasks')
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Task not found'}), 404


@planner_api.route('/api/daily/task/add', methods=['POST'])
@token_required
def api_add_task():
    """
    Add a new daily task.
    ---
    tags:
      - Daily Tasks
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - text
          properties:
            date:
              type: string
              description: Date of the plan (YYYY-MM-DD)
            text:
              type: string
              description: Task description
            priority:
              type: string
              default: Medium
            is_default:
              type: boolean
            tags:
              type: array
              items:
                type: string
            note:
              type: string
            status:
              type: string
              default: To Do
    responses:
      200:
        description: Task added successfully
      400:
        description: Missing text or invalid date
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    task_text = data.get('text', '').strip()
    priority = data.get('priority', 'Medium')
    is_default = bool(data.get('is_default'))
    tags = data.get('tags', [])
    note = data.get('note', '').strip()
    status = data.get('status', 'To Do')
    if isinstance(tags, str):
        tags = [x.strip() for x in tags.split(',') if x.strip()]

    if not date_str or not task_text:
        return jsonify({'success': False, 'message': 'Task text is required'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        plan = DailyPlan(user_id=user.id, date=target_date, schedule={}, tasks=[], notes='')
        db.session.add(plan)

    tasks = list(plan.tasks or [])
    new_task = {
        'id': str(int(datetime.utcnow().timestamp() * 1000)),
        'text': task_text,
        'priority': priority,
        'tags': tags,
        'status': status,
        'note': note,
        'completed': False,
        'is_default': is_default,
        'is_spillover': False,
        'spillover_count': 0,
        'original_date': target_date.strftime('%Y-%m-%d')
    }
    tasks.append(new_task)
    plan.tasks = tasks
    flag_modified(plan, 'tasks')

    # Clear previous deletion/dismissal records on this plan for this task text
    raw_sched = plan.schedule or {}
    if isinstance(raw_sched, dict):
        t_key = task_text.lower()
        deleted_defs = [d for d in raw_sched.get('_deleted_defaults', []) if str(d).lower() != t_key]
        dismissed = [d for d in raw_sched.get('_dismissed_tasks', []) if str(d).lower() != t_key]
        if len(deleted_defs) != len(raw_sched.get('_deleted_defaults', [])) or len(dismissed) != len(raw_sched.get('_dismissed_tasks', [])):
            raw_sched['_deleted_defaults'] = deleted_defs
            raw_sched['_dismissed_tasks'] = dismissed
            plan.schedule = raw_sched
            flag_modified(plan, 'schedule')

    db.session.commit()
    return jsonify({'success': True, 'task': new_task})


@planner_api.route('/api/daily/task/duplicate', methods=['POST'])
@token_required
def api_duplicate_task():
    """
    Duplicate an existing daily task.
    ---
    tags:
      - Daily Tasks
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - task_id
          properties:
            date:
              type: string
            task_id:
              type: string
    responses:
      200:
        description: Task duplicated successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
      404:
        description: Source task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    task_id = data.get('task_id')

    if not date_str or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Plan not found'}), 404

    tasks = plan.tasks or []
    source_task = None
    for t in tasks:
        if isinstance(t, dict) and t.get('id') == task_id:
            source_task = t
            break

    if not source_task:
        return jsonify({'success': False, 'message': 'Source task not found'}), 404

    new_task = dict(source_task)
    new_task['id'] = str(int(datetime.utcnow().timestamp() * 1000))
    new_task['completed'] = False
    new_task['status'] = 'To Do'
    
    tasks.append(new_task)
    plan.tasks = tasks
    flag_modified(plan, 'tasks')
    db.session.commit()

    return jsonify({'success': True, 'task': new_task})


@planner_api.route('/api/daily/task/delete', methods=['POST'])
@token_required
def api_delete_task():
    """
    Delete a daily task.
    ---
    tags:
      - Daily Tasks
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - task_id
          properties:
            date:
              type: string
              description: Date of the plan (YYYY-MM-DD)
            task_id:
              type: string
              description: ID of the task to delete
    responses:
      200:
        description: Task deleted successfully
      400:
        description: Missing arguments or invalid date
      401:
        description: Unauthorized
      404:
        description: Plan or task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    task_id = data.get('task_id')

    if not date_str or not task_id:
        return jsonify({'success': False, 'message': 'Missing task_id or date'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Plan not found'}), 404

    tasks = plan.tasks or []
    deleted_task = None
    for t in tasks:
        if isinstance(t, dict) and t.get('id') == task_id:
            deleted_task = t
            break

    if not deleted_task:
        return jsonify({'success': False, 'message': 'Task not found'}), 404

    plan.tasks = [t for t in tasks if isinstance(t, dict) and t.get('id') != task_id]
    
    raw_sched = plan.schedule or {}
    if not isinstance(raw_sched, dict):
        raw_sched = {}

    dismissed = list(raw_sched.get('_dismissed_tasks', []))
    deleted_defs = list(raw_sched.get('_deleted_defaults', []))

    if task_id not in dismissed:
        dismissed.append(task_id)

    t_text = deleted_task.get('text', '').strip().lower()
    if t_text and t_text not in deleted_defs:
        deleted_defs.append(t_text)
    if task_id not in deleted_defs:
        deleted_defs.append(task_id)

    raw_sched['_dismissed_tasks'] = dismissed
    raw_sched['_deleted_defaults'] = deleted_defs
    plan.schedule = raw_sched
    flag_modified(plan, 'schedule')
    flag_modified(plan, 'tasks')
    db.session.commit()

    return jsonify({'success': True})


@planner_api.route('/api/daily/schedule/update', methods=['POST'])
@token_required
def api_update_schedule():
    """
    Update an hourly schedule and mood slot in real-time.
    ---
    tags:
      - Daily Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
            - slot
          properties:
            date:
              type: string
            slot:
              type: string
              description: "Time slot label (e.g. 09:00 - 10:00 AM)"
            activity:
              type: string
            mood:
              type: string
            is_default:
              type: boolean
    responses:
      200:
        description: Schedule slot updated successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    slot = data.get('slot')
    activity = data.get('activity', '').strip()
    mood = data.get('mood', '').strip()
    is_default = bool(data.get('is_default'))

    if not date_str or not slot:
        return jsonify({'success': False, 'message': 'Missing date or slot'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        plan = DailyPlan(user_id=user.id, date=target_date, schedule={}, tasks=[], notes='')
        db.session.add(plan)

    schedule = dict(plan.schedule or {})
    schedule[slot] = {
        'activity': activity,
        'mood': mood,
        'is_default': is_default
    }

    plan.schedule = schedule
    flag_modified(plan, 'schedule')
    db.session.commit()

    return jsonify({'success': True})


@planner_api.route('/api/daily/notes/update', methods=['POST'])
@token_required
def api_update_notes():
    """
    Update daily reflection and notes in real-time.
    ---
    tags:
      - Daily Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - date
          properties:
            date:
              type: string
            notes:
              type: string
    responses:
      200:
        description: Notes updated successfully
      400:
        description: Missing date parameter
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    date_str = data.get('date')
    notes = data.get('notes', '').strip()

    if not date_str:
        return jsonify({'success': False, 'message': 'Missing date'}), 400

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    plan = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()
    if not plan:
        plan = DailyPlan(user_id=user.id, date=target_date, schedule={}, tasks=[], notes='')
        db.session.add(plan)

    plan.notes = notes
    db.session.commit()

    return jsonify({'success': True})


@planner_api.route('/daily/fetch_activity', methods=['GET'])
@token_required
def fetch_daily_activity():
    """
    Fetch formatted plain-text dataset summary of a daily activity log for copy/analysis.
    ---
    tags:
      - Daily Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: date
        type: string
        required: false
        description: Date in YYYY-MM-DD format
    responses:
      200:
        description: Formatted text dataset returned
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = get_today_date()
    else:
        target_date = get_today_date()

    dp = DailyPlan.query.filter_by(user_id=user.id, date=target_date).first()

    formatted_lines = []
    formatted_lines.append(f"=== DATASET: DAILY ACTIVITY LOG ({target_date.strftime('%Y-%m-%d, %A')}) ===")
    formatted_lines.append("")

    if not dp:
        formatted_lines.append("(No daily plan or activities logged for this date)")
    else:
        sched = dp.schedule or {}
        if sched and isinstance(sched, dict):
            formatted_lines.append("Hourly Time Slots & Activities:")
            has_slots = False
            for slot, sdata in sched.items():
                if str(slot).startswith('_'):
                    continue
                has_slots = True
                if isinstance(sdata, dict):
                    activity = sdata.get('activity', '').strip() or 'No activity recorded'
                    mood = sdata.get('mood', '').strip()
                    context = sdata.get('context', '').strip() or sdata.get('notes', '').strip()
                    tag = sdata.get('tag', '').strip()
                    details = []
                    if mood:
                        details.append(f"Mood: {mood}")
                    if context:
                        details.append(f"Context/Notes: {context}")
                    if tag:
                        details.append(f"Tag: {tag}")
                    detail_str = f" [{', '.join(details)}]" if details else ""
                    formatted_lines.append(f"  - {slot}: {activity}{detail_str}")
                else:
                    formatted_lines.append(f"  - {slot}: {sdata}")
            if not has_slots:
                formatted_lines.append("  - No hourly time slots logged.")
        else:
            formatted_lines.append("Hourly Time Slots & Activities: None logged.")

        formatted_lines.append("")

        tasks = dp.tasks or []
        if tasks and isinstance(tasks, list):
            formatted_lines.append("Daily Tasks:")
            for t in tasks:
                if isinstance(t, dict):
                    status = "Completed" if t.get('completed') else "Pending"
                    prio = f" (Priority: {t.get('priority')})" if t.get('priority') else ""
                    spill = f" [Spillover: {t.get('spillover_count')}d]" if t.get('is_spillover') else ""
                    formatted_lines.append(f"  - [{status}] {t.get('text', '')}{prio}{spill}")
        else:
            formatted_lines.append("Daily Tasks: None logged.")

        formatted_lines.append("")

        sleep = dp.sleep_log
        if sleep and isinstance(sleep, dict) and any(sleep.values()):
            formatted_lines.append(f"Sleep Log: {sleep.get('hours', 'N/A')} hrs (Bed: {sleep.get('bedtime', 'N/A')}, Wake: {sleep.get('wake_time', 'N/A')}, Quality: {sleep.get('quality', 'N/A')}/10)")

        episodes = dp.depression_episodes or []
        if episodes and isinstance(episodes, list):
            ep_texts = [f"Intensity {ep.get('intensity')}/10 ({ep.get('start_time', 'N/A')}, {ep.get('duration', 'N/A')})" for ep in episodes if isinstance(ep, dict)]
            if ep_texts:
                formatted_lines.append(f"Depression Episodes: {'; '.join(ep_texts)}")

        if dp.notes and dp.notes.strip():
            formatted_lines.append("")
            formatted_lines.append(f"End of Day Reflection & Notes: {dp.notes.strip()}")

    formatted_text = "\n".join(formatted_lines)
    return jsonify({
        'success': True,
        'date': target_date.strftime('%Y-%m-%d'),
        'formatted_text': formatted_text
    })


# ============================================================================
# WEEKLY PLANNER REST API ENDPOINTS
# ============================================================================

@planner_api.route('/weekly', methods=['POST'])
@token_required
def api_weekly_post():
    """
    Handle weekly plan mutations (goals, 7-day to-dos, shopping list, meal planning, weekly notes).
    ---
    tags:
      - Weekly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: year
        type: integer
      - in: query
        name: week
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            action:
              type: string
              enum: [add_weekly_goal, toggle_weekly_goal, delete_weekly_goal, add_daily_todo, toggle_daily_todo, delete_daily_todo, add_shopping_item, toggle_shopping_item, delete_shopping_item, save_meals_menu, save_weekly_notes]
    responses:
      200:
        description: Weekly plan operation completed successfully
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    today = get_today_date()
    current_year, current_week, _ = today.isocalendar()

    year_param = request.args.get('year', type=int)
    week_param = request.args.get('week', type=int)
    if not year_param or not week_param:
        year_param, week_param = current_year, current_week

    first_day_of_year = date(year_param, 1, 4)
    start_of_week = first_day_of_year + timedelta(weeks=week_param - 1) - timedelta(days=first_day_of_year.weekday())

    day_abbrs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    plan = carry_forward_unbought_shopping_items(user.id, year_param, week_param)
    if not plan:
        plan = WeeklyPlan.query.filter_by(user_id=user.id, year=year_param, week_number=week_param).first()

    json_data = request.get_json(silent=True) or {}
    action = json_data.get('action') or request.form.get('action')

    if not plan:
        plan = WeeklyPlan(
            user_id=user.id,
            year=year_param,
            week_number=week_param,
            start_date=start_of_week,
            goals=[],
            daily_todos={abbr: [] for abbr in day_abbrs},
            shopping_list=[],
            meals_menu={abbr: {'breakfast': '', 'lunch': '', 'dinner': ''} for abbr in day_abbrs},
            notes=''
        )
        db.session.add(plan)

    goals = plan.goals or []
    daily_todos = plan.daily_todos or {abbr: [] for abbr in day_abbrs}
    shopping_list = plan.shopping_list or []
    meals_menu = plan.meals_menu or {abbr: {'breakfast': '', 'lunch': '', 'dinner': ''} for abbr in day_abbrs}

    if action == 'add_weekly_goal':
        goal_title = (json_data.get('goal_title') or request.form.get('goal_title', '')).strip()
        if goal_title:
            goals.append({
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'title': goal_title,
                'completed': False
            })
            plan.goals = goals
            flag_modified(plan, 'goals')
            db.session.commit()
            flash('Weekly goal added!', 'success')

    elif action == 'toggle_weekly_goal':
        goal_id = json_data.get('goal_id') or request.form.get('goal_id')
        for g in goals:
            if g.get('id') == goal_id:
                g['completed'] = not g.get('completed', False)
        plan.goals = goals
        flag_modified(plan, 'goals')
        db.session.commit()

    elif action == 'delete_weekly_goal':
        goal_id = json_data.get('goal_id') or request.form.get('goal_id')
        plan.goals = [g for g in goals if g.get('id') != goal_id]
        flag_modified(plan, 'goals')
        db.session.commit()
        flash('Weekly goal removed.', 'info')

    elif action == 'add_daily_todo':
        day_abbr = json_data.get('day_abbr') or request.form.get('day_abbr')
        todo_text = (json_data.get('todo_text') or request.form.get('todo_text', '')).strip()
        if day_abbr in day_abbrs and todo_text:
            if day_abbr not in daily_todos:
                daily_todos[day_abbr] = []
            daily_todos[day_abbr].append({
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'text': todo_text,
                'completed': False
            })
            plan.daily_todos = daily_todos
            flag_modified(plan, 'daily_todos')
            db.session.commit()
            flash(f'To-do added to {day_abbr}!', 'success')

    elif action == 'toggle_daily_todo':
        day_abbr = json_data.get('day_abbr') or request.form.get('day_abbr')
        todo_id = json_data.get('todo_id') or request.form.get('todo_id')
        if day_abbr in daily_todos:
            for t in daily_todos[day_abbr]:
                if t.get('id') == todo_id:
                    t['completed'] = not t.get('completed', False)
            plan.daily_todos = daily_todos
            flag_modified(plan, 'daily_todos')
            db.session.commit()

    elif action == 'delete_daily_todo':
        day_abbr = json_data.get('day_abbr') or request.form.get('day_abbr')
        todo_id = json_data.get('todo_id') or request.form.get('todo_id')
        if day_abbr in daily_todos:
            daily_todos[day_abbr] = [t for t in daily_todos[day_abbr] if t.get('id') != todo_id]
            plan.daily_todos = daily_todos
            flag_modified(plan, 'daily_todos')
            db.session.commit()
            flash('To-do item deleted.', 'info')

    elif action == 'add_shopping_item':
        item_name = (json_data.get('item_name') or request.form.get('item_name', '')).strip()
        category = (json_data.get('category') or request.form.get('category', 'Groceries')).strip()
        if item_name:
            shopping_list.append({
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'item': item_name,
                'category': category,
                'bought': False,
                'added_date': get_today_date().strftime('%Y-%m-%d')
            })
            plan.shopping_list = shopping_list
            flag_modified(plan, 'shopping_list')
            db.session.commit()
            flash('Shopping item added!', 'success')

    elif action == 'toggle_shopping_item':
        item_id = json_data.get('item_id') or request.form.get('item_id')
        for s in shopping_list:
            if s.get('id') == item_id:
                s['bought'] = not s.get('bought', False)
        plan.shopping_list = shopping_list
        flag_modified(plan, 'shopping_list')
        db.session.commit()

    elif action == 'delete_shopping_item':
        item_id = json_data.get('item_id') or request.form.get('item_id')
        plan.shopping_list = [s for s in shopping_list if s.get('id') != item_id]
        flag_modified(plan, 'shopping_list')
        db.session.commit()
        flash('Shopping item deleted.', 'info')

    elif action == 'save_meals_menu':
        for abbr in day_abbrs:
            meals_menu[abbr] = {
                'breakfast': (json_data.get(f'meal_bf_{abbr}') or request.form.get(f'meal_bf_{abbr}', '')).strip(),
                'lunch': (json_data.get(f'meal_lu_{abbr}') or request.form.get(f'meal_lu_{abbr}', '')).strip(),
                'dinner': (json_data.get(f'meal_dn_{abbr}') or request.form.get(f'meal_dn_{abbr}', '')).strip()
            }
        plan.meals_menu = meals_menu
        flag_modified(plan, 'meals_menu')
        db.session.commit()
        flash('Weekly meal menu saved!', 'success')

    elif action == 'save_weekly_notes':
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()
        plan.notes = notes
        db.session.commit()
        flash('Weekly notes updated!', 'success')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == 'true':
        tot_todos = sum(len(daily_todos.get(abbr, [])) for abbr in day_abbrs)
        comp_todos = sum(sum(1 for t in daily_todos.get(abbr, []) if t.get('completed')) for abbr in day_abbrs)
        todo_pct = int((comp_todos / tot_todos * 100)) if tot_todos > 0 else 0

        tot_goals = len(goals)
        comp_goals = sum(1 for g in goals if g.get('completed'))

        tot_shopping = len(shopping_list)
        bought_shop = sum(1 for s in shopping_list if s.get('bought'))

        meals_p = sum(sum(1 for m_type in ['breakfast', 'lunch', 'dinner'] if meals_menu.get(abbr, {}).get(m_type)) for abbr in day_abbrs)
        meal_pct = int((meals_p / 21 * 100))

        s_comps = []
        if tot_todos > 0:
            s_comps.append(todo_pct)
        if tot_goals > 0:
            s_comps.append(int(comp_goals / tot_goals * 100))
        if meals_p > 0:
            s_comps.append(meal_pct)
        w_score = int(sum(s_comps) / len(s_comps)) if s_comps else (100 if comp_todos > 0 or comp_goals > 0 else 0)

        resp_data = {
            'success': True,
            'action': action,
            'todo_pct': todo_pct,
            'comp_goals': comp_goals,
            'tot_goals': tot_goals,
            'bought_shop': bought_shop,
            'tot_shopping': tot_shopping,
            'meals_p': meals_p,
            'weekly_score': w_score,
            'message': 'Operation completed successfully'
        }

        if action == 'add_weekly_goal' and goals:
            resp_data['goal'] = goals[-1]
            resp_data['message'] = 'Weekly goal added!'
        elif action == 'toggle_weekly_goal':
            goal_id = json_data.get('goal_id') or request.form.get('goal_id')
            g_comp = next((g.get('completed') for g in goals if g.get('id') == goal_id), False)
            resp_data['goal_id'] = goal_id
            resp_data['completed'] = g_comp
            resp_data['message'] = 'Weekly goal updated!'
        elif action == 'delete_weekly_goal':
            resp_data['goal_id'] = json_data.get('goal_id') or request.form.get('goal_id')
            resp_data['message'] = 'Weekly goal removed.'
        elif action == 'add_daily_todo':
            day_abbr = json_data.get('day_abbr') or request.form.get('day_abbr')
            resp_data['day_abbr'] = day_abbr
            resp_data['todo'] = daily_todos.get(day_abbr, [])[-1] if daily_todos.get(day_abbr) else None
            resp_data['message'] = f'To-do added to {day_abbr}!'
        elif action == 'toggle_daily_todo':
            day_abbr = json_data.get('day_abbr') or request.form.get('day_abbr')
            todo_id = json_data.get('todo_id') or request.form.get('todo_id')
            t_comp = False
            for t in daily_todos.get(day_abbr, []):
                if t.get('id') == todo_id:
                    t_comp = t.get('completed', False)
                    break
            resp_data['day_abbr'] = day_abbr
            resp_data['todo_id'] = todo_id
            resp_data['completed'] = t_comp
            resp_data['message'] = f'To-do updated for {day_abbr}!'
        elif action == 'delete_daily_todo':
            resp_data['day_abbr'] = json_data.get('day_abbr') or request.form.get('day_abbr')
            resp_data['todo_id'] = json_data.get('todo_id') or request.form.get('todo_id')
            resp_data['message'] = 'To-do deleted.'
        elif action == 'add_shopping_item' and shopping_list:
            resp_data['item'] = shopping_list[-1]
            resp_data['message'] = 'Shopping item added!'
        elif action == 'toggle_shopping_item':
            item_id = json_data.get('item_id') or request.form.get('item_id')
            s_bought = next((s.get('bought') for s in shopping_list if s.get('id') == item_id), False)
            resp_data['item_id'] = item_id
            resp_data['bought'] = s_bought
            resp_data['message'] = 'Shopping item updated!'
        elif action == 'delete_shopping_item':
            resp_data['item_id'] = json_data.get('item_id') or request.form.get('item_id')
            resp_data['message'] = 'Shopping item deleted.'

        return jsonify(resp_data)
    return redirect(url_for('planner_ui.weekly', year=year_param, week=week_param))


@planner_api.route('/weekly/fetch_activity', methods=['GET'])
@token_required
def fetch_weekly_activity():
    """
    Fetch formatted plain-text dataset summary of all 7 days of daily activity logs for a week.
    ---
    tags:
      - Weekly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: year
        type: integer
      - in: query
        name: week
        type: integer
    responses:
      200:
        description: Formatted weekly dataset returned
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    year_param = request.args.get('year', type=int)
    week_param = request.args.get('week', type=int)
    today = get_today_date()
    if not year_param or not week_param:
        year_param, week_param, _ = today.isocalendar()

    first_day_of_year = date(year_param, 1, 4)
    start_of_week = first_day_of_year + timedelta(weeks=week_param - 1) - timedelta(days=first_day_of_year.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    week_daily_plans = DailyPlan.query.filter(
        DailyPlan.user_id == user.id,
        DailyPlan.date >= start_of_week,
        DailyPlan.date <= end_of_week
    ).order_by(DailyPlan.date.asc()).all()

    plan_by_date = {dp.date: dp for dp in week_daily_plans}

    formatted_lines = []
    formatted_lines.append(f"=== DATASET: DAILY ACTIVITY LOGS (Week {week_param}, {year_param}: {start_of_week.strftime('%b %d, %Y')} - {end_of_week.strftime('%b %d, %Y')}) ===")
    formatted_lines.append("")

    day_abbrs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    for i in range(7):
        curr_date = start_of_week + timedelta(days=i)
        day_abbr = day_abbrs[i]
        date_str = curr_date.strftime('%Y-%m-%d (%A)')
        dp = plan_by_date.get(curr_date)

        formatted_lines.append(f"--- Day {i+1}: {day_abbr} {date_str} ---")

        if not dp:
            formatted_lines.append("  (No daily plan logged for this date)")
            formatted_lines.append("")
            continue

        sched = dp.schedule or {}
        if sched and isinstance(sched, dict):
            has_slots = False
            for slot, sdata in sched.items():
                if str(slot).startswith('_'):
                    continue
                has_slots = True
                if isinstance(sdata, dict):
                    activity = sdata.get('activity', '').strip() or 'No activity recorded'
                    mood = sdata.get('mood', '').strip()
                    context = sdata.get('context', '').strip() or sdata.get('notes', '').strip()
                    tag = sdata.get('tag', '').strip()
                    details = []
                    if mood:
                        details.append(f"Mood: {mood}")
                    if context:
                        details.append(f"Notes: {context}")
                    if tag:
                        details.append(f"Tag: {tag}")
                    detail_str = f" [{', '.join(details)}]" if details else ""
                    formatted_lines.append(f"  - {slot}: {activity}{detail_str}")
                else:
                    formatted_lines.append(f"  - {slot}: {sdata}")
            if not has_slots:
                formatted_lines.append("  - No hourly time slots logged.")
        else:
            formatted_lines.append("  - No hourly time slots logged.")

        tasks = dp.tasks or []
        if tasks and isinstance(tasks, list):
            task_strings = []
            for t in tasks:
                if isinstance(t, dict):
                    status = "Completed" if t.get('completed') else "Pending"
                    prio = f" ({t.get('priority')})" if t.get('priority') else ""
                    task_strings.append(f"[{status}] {t.get('text', '')}{prio}")
            if task_strings:
                formatted_lines.append(f"  Tasks: {'; '.join(task_strings)}")

        sleep = dp.sleep_log
        if sleep and isinstance(sleep, dict) and any(sleep.values()):
            formatted_lines.append(f"  Sleep: {sleep.get('hours', 'N/A')} hrs (Bed: {sleep.get('bedtime', 'N/A')}, Wake: {sleep.get('wake_time', 'N/A')}, Quality: {sleep.get('quality', 'N/A')}/10)")

        if dp.notes and dp.notes.strip():
            formatted_lines.append(f"  Daily Notes: {dp.notes.strip()}")

        formatted_lines.append("")

    formatted_text = "\n".join(formatted_lines)
    return jsonify({
        'success': True,
        'year': year_param,
        'week': week_param,
        'formatted_text': formatted_text
    })


# ============================================================================
# MONTHLY PLANNER REST API ENDPOINTS
# ============================================================================

@planner_api.route('/monthly', methods=['POST'])
@token_required
def api_monthly_post():
    """
    Handle monthly plan mutations (goals, habits, milestones, calendar day items/stickers, notes).
    ---
    tags:
      - Monthly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: year
        type: integer
      - in: query
        name: month
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            action:
              type: string
              enum: [add_goal, toggle_goal, delete_goal, add_milestone, toggle_milestone, delete_milestone, save_notes, save_calendar_day, delete_calendar_item, delete_day_sticker, add_habit, delete_habit]
    responses:
      200:
        description: Monthly operation completed successfully
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    today = get_today_date()
    try:
        selected_year = int(request.args.get('year', today.year))
        selected_month = int(request.args.get('month', today.month))
    except (ValueError, TypeError):
        selected_year = today.year
        selected_month = today.month

    if selected_month < 1 or selected_month > 12:
        selected_month = today.month

    plan = MonthlyPlan.query.filter_by(user_id=user.id, year=selected_year, month=selected_month).first()
    if not plan:
        plan = MonthlyPlan(user_id=user.id, year=selected_year, month=selected_month, goals=[], habits=[], milestones=[], calendar_days={}, notes='')
        db.session.add(plan)

    json_data = request.get_json(silent=True) or {}
    action = json_data.get('action') or request.form.get('action')

    goals = plan.goals or []
    habits = plan.habits or []
    milestones = plan.milestones or []
    calendar_days = plan.calendar_days or {}

    if action == 'add_goal':
        title = (json_data.get('goal_title') or request.form.get('goal_title', '')).strip()
        category = (json_data.get('category') or request.form.get('category', 'General')).strip()
        deadline = (json_data.get('deadline') or request.form.get('deadline', '')).strip()
        if title:
            new_goal = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'title': title,
                'category': category,
                'deadline': deadline,
                'status': 'In Progress'
            }
            goals.append(new_goal)
            plan.goals = goals
            flag_modified(plan, 'goals')
            db.session.commit()
            flash('Monthly goal added!', 'success')

    elif action in ['toggle_goal', 'toggle_goal_status']:
        goal_id = json_data.get('goal_id') or request.form.get('goal_id')
        for g in goals:
            if g.get('id') == goal_id:
                g['status'] = 'Completed' if g.get('status') != 'Completed' else 'In Progress'
        plan.goals = goals
        flag_modified(plan, 'goals')
        db.session.commit()

    elif action == 'delete_goal':
        goal_id = json_data.get('goal_id') or request.form.get('goal_id')
        plan.goals = [g for g in goals if g.get('id') != goal_id]
        flag_modified(plan, 'goals')
        db.session.commit()
        flash('Monthly goal removed.', 'info')

    elif action == 'add_milestone':
        title = (json_data.get('milestone_title') or request.form.get('milestone_title', '')).strip()
        day_str = (json_data.get('milestone_date') or request.form.get('milestone_date', '1')).strip()
        if title:
            new_milestone = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'title': title,
                'date': day_str,
                'completed': False
            }
            milestones.append(new_milestone)
            plan.milestones = milestones
            flag_modified(plan, 'milestones')
            db.session.commit()
            flash('Key milestone added!', 'success')

    elif action == 'toggle_milestone':
        m_id = json_data.get('milestone_id') or request.form.get('milestone_id')
        for m in milestones:
            if m.get('id') == m_id:
                m['completed'] = not m.get('completed', False)
        plan.milestones = milestones
        flag_modified(plan, 'milestones')
        db.session.commit()

    elif action == 'delete_milestone':
        m_id = json_data.get('milestone_id') or request.form.get('milestone_id')
        plan.milestones = [m for m in milestones if m.get('id') != m_id]
        flag_modified(plan, 'milestones')
        db.session.commit()
        flash('Milestone removed.', 'info')

    elif action == 'save_notes':
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()
        plan.notes = notes
        db.session.commit()
        flash('Monthly notes updated!', 'success')

    elif action in ['add_calendar_item', 'save_calendar_day']:
        day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
        item_text = (json_data.get('item_text') or request.form.get('item_text', '')).strip()
        item_type = json_data.get('item_type') or request.form.get('item_type', 'deadline')
        sticker = (json_data.get('sticker') or request.form.get('sticker', '')).strip()
        image_url = (json_data.get('image_url') or request.form.get('image_url', '')).strip()
        remind_me = (json_data.get('remind_me') if 'remind_me' in json_data else request.form.get('remind_me')) in ['true', 'True', '1', 'on', True, 1]

        if day_str and item_text:
            if day_str not in calendar_days:
                calendar_days[day_str] = {'items': [], 'sticker': '', 'image_url': ''}
            
            day_entry = calendar_days[day_str]
            items = day_entry.get('items', [])
            items.append({
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'text': item_text,
                'type': item_type,
                'sticker': sticker,
                'image_url': image_url,
                'remind_me': remind_me
            })
            day_entry['items'] = items
            if sticker:
                day_entry['sticker'] = sticker
            if image_url:
                day_entry['image_url'] = image_url

            calendar_days[day_str] = day_entry
            plan.calendar_days = calendar_days
            flag_modified(plan, 'calendar_days')
            db.session.commit()
            flash(f'Plan item added to Day {day_str}!', 'success')
        elif day_str and (sticker or image_url):
            if day_str not in calendar_days:
                calendar_days[day_str] = {'items': [], 'sticker': '', 'image_url': ''}
            if sticker:
                calendar_days[day_str]['sticker'] = sticker
            if image_url:
                calendar_days[day_str]['image_url'] = image_url
            plan.calendar_days = calendar_days
            flag_modified(plan, 'calendar_days')
            db.session.commit()
            flash(f'Calendar updated for Day {day_str}!', 'success')

    elif action == 'edit_calendar_item':
        day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
        item_id = json_data.get('item_id') or request.form.get('item_id', '').strip()
        item_text = (json_data.get('item_text') or request.form.get('item_text', '')).strip()
        item_type = json_data.get('item_type') or request.form.get('item_type', 'deadline')
        sticker = (json_data.get('sticker') or request.form.get('sticker', '')).strip()
        image_url = (json_data.get('image_url') or request.form.get('image_url', '')).strip()
        remind_me = (json_data.get('remind_me') if 'remind_me' in json_data else request.form.get('remind_me')) in ['true', 'True', '1', 'on', True, 1]

        if day_str in calendar_days and item_id and item_text:
            day_entry = calendar_days[day_str]
            items = day_entry.get('items', [])
            for item in items:
                if item.get('id') == item_id:
                    item['text'] = item_text
                    item['type'] = item_type
                    item['sticker'] = sticker
                    item['image_url'] = image_url
                    item['remind_me'] = remind_me
                    break
            day_entry['items'] = items

            remaining_stickers = [i.get('sticker') for i in items if i.get('sticker')]
            remaining_images = [i.get('image_url') for i in items if i.get('image_url')]
            day_entry['sticker'] = remaining_stickers[-1] if remaining_stickers else ''
            day_entry['image_url'] = remaining_images[-1] if remaining_images else ''

            calendar_days[day_str] = day_entry
            plan.calendar_days = calendar_days
            flag_modified(plan, 'calendar_days')
            db.session.commit()
            flash(f'Plan item updated on Day {day_str}!', 'success')

    elif action == 'delete_calendar_item':
        day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
        item_id = json_data.get('item_id') or request.form.get('item_id')
        if day_str in calendar_days:
            day_entry = calendar_days[day_str]
            day_entry['items'] = [i for i in day_entry.get('items', []) if i.get('id') != item_id]
            
            remaining_stickers = [i.get('sticker') for i in day_entry['items'] if i.get('sticker')]
            remaining_images = [i.get('image_url') for i in day_entry['items'] if i.get('image_url')]
            day_entry['sticker'] = remaining_stickers[-1] if remaining_stickers else ''
            day_entry['image_url'] = remaining_images[-1] if remaining_images else ''

            calendar_days[day_str] = day_entry
            plan.calendar_days = calendar_days
            flag_modified(plan, 'calendar_days')
            db.session.commit()
            flash('Calendar item removed.', 'info')

    elif action == 'delete_day_sticker':
        day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
        if day_str in calendar_days:
            calendar_days[day_str]['sticker'] = ''
            calendar_days[day_str]['image_url'] = ''
            plan.calendar_days = calendar_days
            flag_modified(plan, 'calendar_days')
            db.session.commit()
            flash(f'Day sticker cleared for Day {day_str}.', 'info')

    elif action == 'set_day_sticker':
        day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
        sticker = (json_data.get('sticker') or request.form.get('sticker', '')).strip()
        image_url = (json_data.get('image_url') or request.form.get('image_url', '')).strip()
        if day_str:
            if day_str not in calendar_days:
                calendar_days[day_str] = {'items': [], 'sticker': '', 'image_url': ''}
            calendar_days[day_str]['sticker'] = sticker
            if image_url:
                calendar_days[day_str]['image_url'] = image_url
            plan.calendar_days = calendar_days
            flag_modified(plan, 'calendar_days')
            db.session.commit()
            flash(f'Sticker updated for Day {day_str}!', 'success')

    elif action == 'add_habit':
        habit_name = (json_data.get('habit_name') or request.form.get('habit_name', '')).strip()
        habit_type = (json_data.get('habit_type') or request.form.get('habit_type', 'boolean')).strip().lower()
        if habit_type not in ['boolean', 'counter', 'sub_habits']:
            habit_type = 'boolean'

        category = (json_data.get('category') or request.form.get('category', 'General')).strip()

        if habit_name:
            new_habit = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'name': habit_name,
                'type': habit_type,
                'category': category,
                'completed_days': []
            }

            if habit_type == 'counter':
                unit = (json_data.get('unit') or request.form.get('unit', 'times')).strip()
                try:
                    target_count = int(json_data.get('target_count') or request.form.get('target_count', 1))
                except (ValueError, TypeError):
                    target_count = 1
                new_habit['unit'] = unit or 'times'
                new_habit['target_count'] = max(1, target_count)
                new_habit['daily_counts'] = {}

            elif habit_type == 'sub_habits':
                sub_habits_raw = json_data.get('sub_habits') or request.form.get('sub_habits')
                sub_habits_list = []
                if isinstance(sub_habits_raw, list):
                    for idx, s in enumerate(sub_habits_raw):
                        s_name = s.get('name', '') if isinstance(s, dict) else str(s).strip()
                        if s_name:
                            s_id = s.get('id') if (isinstance(s, dict) and s.get('id')) else f"sh_{int(datetime.utcnow().timestamp() * 1000) + idx}"
                            sub_habits_list.append({'id': str(s_id), 'name': s_name})
                elif isinstance(sub_habits_raw, str):
                    for idx, s_name in enumerate(sub_habits_raw.split(',')):
                        s_name = s_name.strip()
                        if s_name:
                            sub_habits_list.append({'id': f"sh_{int(datetime.utcnow().timestamp() * 1000) + idx}", 'name': s_name})
                new_habit['sub_habits'] = sub_habits_list
                new_habit['daily_sub_completions'] = {}

            habits.append(new_habit)
            plan.habits = habits
            flag_modified(plan, 'habits')
            db.session.commit()
            flash('New habit added!', 'success')

    elif action in ['update_habit', 'manage_sub_habits']:
        habit_id = json_data.get('habit_id') or request.form.get('habit_id')
        for h in habits:
            if h.get('id') == habit_id:
                if 'habit_name' in json_data or 'habit_name' in request.form:
                    h['name'] = (json_data.get('habit_name') or request.form.get('habit_name', h.get('name'))).strip()
                if 'category' in json_data or 'category' in request.form:
                    h['category'] = (json_data.get('category') or request.form.get('category', h.get('category', 'General'))).strip()
                if 'unit' in json_data or 'unit' in request.form:
                    h['unit'] = (json_data.get('unit') or request.form.get('unit', h.get('unit', 'times'))).strip()
                if 'target_count' in json_data or 'target_count' in request.form:
                    try:
                        h['target_count'] = max(1, int(json_data.get('target_count') or request.form.get('target_count', h.get('target_count', 1))))
                    except (ValueError, TypeError):
                        pass
                if 'sub_habits' in json_data or 'sub_habits' in request.form:
                    sub_habits_raw = json_data.get('sub_habits') or request.form.get('sub_habits')
                    sub_habits_list = []
                    if isinstance(sub_habits_raw, list):
                        for idx, s in enumerate(sub_habits_raw):
                            s_name = s.get('name', '') if isinstance(s, dict) else str(s).strip()
                            if s_name:
                                s_id = s.get('id') if (isinstance(s, dict) and s.get('id')) else f"sh_{int(datetime.utcnow().timestamp() * 1000) + idx}"
                                sub_habits_list.append({'id': str(s_id), 'name': s_name})
                    elif isinstance(sub_habits_raw, str):
                        for idx, s_name in enumerate(sub_habits_raw.split(',')):
                            s_name = s_name.strip()
                            if s_name:
                                sub_habits_list.append({'id': f"sh_{int(datetime.utcnow().timestamp() * 1000) + idx}", 'name': s_name})
                    h['sub_habits'] = sub_habits_list
                break
        plan.habits = habits
        flag_modified(plan, 'habits')
        db.session.commit()
        flash('Habit updated!', 'success')

    elif action in ['reorder_habits', 'reorder_habit']:
        order = json_data.get('order') or request.form.getlist('order')
        move_id = json_data.get('habit_id') or json_data.get('move_id') or request.form.get('habit_id')
        direction = json_data.get('direction') or request.form.get('direction')  # 'up' or 'down'
        arrange_by = json_data.get('arrange_by') or request.form.get('arrange_by')  # 'type_standard', 'alphabetical', 'completion'

        if order and isinstance(order, list):
            habit_map = {str(h.get('id')): h for h in habits}
            reordered = []
            for hid in order:
                hid_str = str(hid)
                if hid_str in habit_map:
                    reordered.append(habit_map.pop(hid_str))
            reordered.extend(habit_map.values())
            plan.habits = reordered
            flag_modified(plan, 'habits')
            db.session.commit()
            habits = plan.habits
        elif move_id and direction in ['up', 'down']:
            move_id_str = str(move_id)
            idx = next((i for i, h in enumerate(habits) if str(h.get('id')) == move_id_str), -1)
            if idx != -1:
                target_idx = idx - 1 if direction == 'up' else idx + 1
                if 0 <= target_idx < len(habits):
                    habits[idx], habits[target_idx] = habits[target_idx], habits[idx]
                    plan.habits = habits
                    flag_modified(plan, 'habits')
                    db.session.commit()
        elif arrange_by == 'type_standard':
            # Checklists (boolean) top -> Sub-habits middle -> Counters bottom
            type_weights = {'boolean': 0, 'sub_habits': 1, 'counter': 2}
            plan.habits = sorted(habits, key=lambda h: type_weights.get(h.get('type', 'boolean'), 0))
            flag_modified(plan, 'habits')
            db.session.commit()
            habits = plan.habits
        elif arrange_by == 'alphabetical':
            plan.habits = sorted(habits, key=lambda h: str(h.get('name', '')).lower())
            flag_modified(plan, 'habits')
            db.session.commit()
            habits = plan.habits
        elif arrange_by == 'completion':
            plan.habits = sorted(habits, key=lambda h: len(h.get('completed_days', [])), reverse=True)
            flag_modified(plan, 'habits')
            db.session.commit()
            habits = plan.habits

    elif action == 'delete_habit':
        habit_id = json_data.get('habit_id') or request.form.get('habit_id')
        plan.habits = [h for h in habits if h.get('id') != habit_id]
        flag_modified(plan, 'habits')
        db.session.commit()
        flash('Habit deleted.', 'info')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == 'true':
        tot_goals = len(goals)
        comp_goals = sum(1 for g in goals if g.get('status') == 'Completed')
        goal_pct = int((comp_goals / tot_goals * 100)) if tot_goals > 0 else 0

        tot_milestones = len(milestones)
        comp_milestones = sum(1 for m in milestones if m.get('completed'))
        milestone_pct = int((comp_milestones / tot_milestones * 100)) if tot_milestones > 0 else 0

        days_in_m = calendar.monthrange(selected_year, selected_month)[1]
        tot_habit_slots = len(habits) * days_in_m
        comp_habit_slots = sum(len(h.get('completed_days', [])) for h in habits)
        habit_pct = int((comp_habit_slots / tot_habit_slots * 100)) if tot_habit_slots > 0 else 0

        m_comps = []
        if tot_goals > 0:
            m_comps.append(goal_pct)
        if tot_milestones > 0:
            m_comps.append(milestone_pct)
        if tot_habit_slots > 0:
            m_comps.append(habit_pct)
        monthly_score = int(sum(m_comps) / len(m_comps)) if m_comps else (100 if comp_goals > 0 or comp_milestones > 0 else 0)

        resp_data = {
            'success': True,
            'action': action,
            'completed_goals': comp_goals,
            'total_goals': tot_goals,
            'goal_pct': goal_pct,
            'comp_goals': comp_goals,
            'tot_goals': tot_goals,
            'milestone_pct': milestone_pct,
            'comp_milestones': comp_milestones,
            'tot_milestones': tot_milestones,
            'habit_pct': habit_pct,
            'monthly_score': monthly_score,
            'message': 'Operation completed successfully'
        }

        if action == 'add_goal' and goals:
            resp_data['goal'] = goals[-1]
            resp_data['message'] = 'Goal added!'
        elif action in ['toggle_goal', 'toggle_goal_status']:
            goal_id = json_data.get('goal_id') or request.form.get('goal_id')
            g_stat = next((g.get('status') for g in goals if g.get('id') == goal_id), 'In Progress')
            resp_data['goal_id'] = goal_id
            resp_data['status'] = g_stat
            resp_data['message'] = 'Goal updated!'
        elif action == 'delete_goal':
            resp_data['goal_id'] = json_data.get('goal_id') or request.form.get('goal_id')
            resp_data['message'] = 'Goal removed.'
        elif action == 'add_milestone' and milestones:
            resp_data['milestone'] = milestones[-1]
            resp_data['message'] = 'Milestone added!'
        elif action == 'toggle_milestone':
            m_id = json_data.get('milestone_id') or request.form.get('milestone_id')
            m_comp = next((m.get('completed') for m in milestones if m.get('id') == m_id), False)
            resp_data['milestone_id'] = m_id
            resp_data['completed'] = m_comp
            resp_data['message'] = 'Milestone updated!'
        elif action == 'delete_milestone':
            resp_data['milestone_id'] = json_data.get('milestone_id') or request.form.get('milestone_id')
            resp_data['message'] = 'Milestone removed.'
        elif action in ['add_calendar_item', 'edit_calendar_item', 'save_calendar_day']:
            day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
            resp_data['day'] = day_str
            resp_data['day_entry'] = calendar_days.get(day_str, {'items': [], 'sticker': '', 'image_url': ''})
            resp_data['message'] = f'Calendar updated for Day {day_str}!'
        elif action == 'delete_calendar_item':
            day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
            resp_data['day'] = day_str
            resp_data['item_id'] = json_data.get('item_id') or request.form.get('item_id')
            resp_data['day_entry'] = calendar_days.get(day_str, {'items': [], 'sticker': '', 'image_url': ''})
            resp_data['message'] = 'Calendar item removed.'
        elif action == 'delete_day_sticker':
            day_str = str(json_data.get('day') or request.form.get('day', '')).strip()
            resp_data['day'] = day_str
            resp_data['message'] = f'Day sticker cleared for Day {day_str}.'
        elif action == 'add_habit' and habits:
            days_in_m = calendar.monthrange(selected_year, selected_month)[1]
            resp_data['habit'] = habits[-1]
            resp_data['days_in_month'] = days_in_m
            resp_data['message'] = 'Habit added!'
        elif action in ['update_habit', 'manage_sub_habits']:
            habit_id = json_data.get('habit_id') or request.form.get('habit_id')
            target_h = next((h for h in habits if h.get('id') == habit_id), None)
            resp_data['habit'] = target_h
            resp_data['message'] = 'Habit updated successfully!'
        elif action in ['reorder_habits', 'reorder_habit']:
            resp_data['habits'] = plan.habits
            resp_data['message'] = 'Habits reordered successfully!'
        elif action == 'delete_habit':
            resp_data['habit_id'] = json_data.get('habit_id') or request.form.get('habit_id')
            resp_data['message'] = 'Habit deleted.'

        return jsonify(resp_data)
    return redirect(url_for('planner_ui.monthly', year=selected_year, month=selected_month))


@planner_api.route('/api/monthly/habit/reorder', methods=['POST'])
@token_required
def api_reorder_monthly_habits():
    """
    Reorder habits in a monthly plan. Supports moving by ID list, move up/down, or auto-arranging.
    ---
    tags:
      - Monthly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - year
            - month
          properties:
            year:
              type: integer
            month:
              type: integer
            order:
              type: array
              items:
                type: string
              description: Ordered list of habit IDs
            habit_id:
              type: string
              description: Specific habit ID to move
            direction:
              type: string
              enum: [up, down]
              description: Direction to move habit
            arrange_by:
              type: string
              enum: [type_standard, alphabetical, completion]
              description: Auto-arrange strategy (e.g. type_standard: Checklists -> Sub-habits -> Counters)
    responses:
      200:
        description: Habits reordered successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
      404:
        description: Plan not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    year = data.get('year')
    month = data.get('month')

    if not year or not month:
        return jsonify({'success': False, 'message': 'Missing year or month'}), 400

    plan = MonthlyPlan.query.filter_by(user_id=user.id, year=int(year), month=int(month)).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Monthly plan not found'}), 404

    habits = plan.habits or []
    order = data.get('order')
    move_id = data.get('habit_id') or data.get('move_id')
    direction = data.get('direction')
    arrange_by = data.get('arrange_by')

    if order and isinstance(order, list):
        habit_map = {str(h.get('id')): h for h in habits}
        reordered = []
        for hid in order:
            hid_str = str(hid)
            if hid_str in habit_map:
                reordered.append(habit_map.pop(hid_str))
        reordered.extend(habit_map.values())
        plan.habits = reordered
        flag_modified(plan, 'habits')
        db.session.commit()
    elif move_id and direction in ['up', 'down']:
        move_id_str = str(move_id)
        idx = next((i for i, h in enumerate(habits) if str(h.get('id')) == move_id_str), -1)
        if idx != -1:
            target_idx = idx - 1 if direction == 'up' else idx + 1
            if 0 <= target_idx < len(habits):
                habits[idx], habits[target_idx] = habits[target_idx], habits[idx]
                plan.habits = habits
                flag_modified(plan, 'habits')
                db.session.commit()
    elif arrange_by == 'type_standard':
        type_weights = {'boolean': 0, 'sub_habits': 1, 'counter': 2}
        plan.habits = sorted(habits, key=lambda h: type_weights.get(h.get('type', 'boolean'), 0))
        flag_modified(plan, 'habits')
        db.session.commit()
    elif arrange_by == 'alphabetical':
        plan.habits = sorted(habits, key=lambda h: str(h.get('name', '')).lower())
        flag_modified(plan, 'habits')
        db.session.commit()
    elif arrange_by == 'completion':
        plan.habits = sorted(habits, key=lambda h: len(h.get('completed_days', [])), reverse=True)
        flag_modified(plan, 'habits')
        db.session.commit()

    return jsonify({
        'success': True,
        'habits': plan.habits,
        'message': 'Habits reordered successfully'
    })


@planner_api.route('/api/monthly/habit/toggle', methods=['POST'])
@token_required
def api_toggle_habit_day():
    """
    Toggle a specific day completion status for a habit (Boolean, Counter, or Sub-Habits).
    ---
    tags:
      - Monthly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
      - name: body
        schema:
          type: object
          required:
            - year
            - month
            - habit_id
            - day
          properties:
            year:
              type: integer
            month:
              type: integer
            habit_id:
              type: string
            day:
              type: integer
            delta:
              type: integer
              description: For counter habits (+1 or -1)
            count:
              type: integer
              description: Explicit count value for counter habits
            sub_habit_id:
              type: string
              description: Target sub-habit item ID for sub_habits type
    responses:
      200:
        description: Habit day toggled/updated successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
      404:
        description: Habit or plan not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    year = data.get('year')
    month = data.get('month')
    habit_id = data.get('habit_id')
    day = data.get('day')

    if not all([year, month, habit_id, day]):
        return jsonify({'success': False, 'message': 'Missing arguments'}), 400

    try:
        day_int = int(day)
        day_str = str(day_int)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid day value'}), 400

    plan = MonthlyPlan.query.filter_by(user_id=user.id, year=int(year), month=int(month)).first()
    if not plan:
        return jsonify({'success': False, 'message': 'Plan not found'}), 404

    habits = plan.habits or []
    target_habit = None

    for h in habits:
        if h.get('id') == habit_id:
            target_habit = h
            break

    if not target_habit:
        return jsonify({'success': False, 'message': 'Habit not found'}), 404

    h_type = target_habit.get('type', 'boolean')
    completed_days = target_habit.get('completed_days', [])
    if not isinstance(completed_days, list):
        completed_days = []

    resp_payload = {'success': True, 'habit_id': habit_id, 'day': day_int, 'type': h_type}

    # Case 1: Numeric Counter Habit
    if h_type == 'counter':
        daily_counts = target_habit.get('daily_counts', {})
        if not isinstance(daily_counts, dict):
            daily_counts = {}

        target_count = target_habit.get('target_count', 1)
        current_count = int(daily_counts.get(day_str, 0))

        if 'count' in data:
            new_count = max(0, int(data['count']))
        elif 'delta' in data:
            new_count = max(0, current_count + int(data['delta']))
        else:
            # Default click toggle: if count > 0, reset to 0; if 0, set to target_count (or 1)
            new_count = 0 if current_count > 0 else max(1, target_count)

        if new_count > 0:
            daily_counts[day_str] = new_count
            if day_int not in completed_days:
                completed_days.append(day_int)
        else:
            daily_counts.pop(day_str, None)
            if day_int in completed_days:
                completed_days.remove(day_int)

        target_habit['daily_counts'] = daily_counts
        target_habit['completed_days'] = completed_days

        resp_payload['count'] = new_count
        resp_payload['unit'] = target_habit.get('unit', 'times')
        resp_payload['target_count'] = target_count
        resp_payload['checked'] = (new_count >= target_count if target_count > 1 else new_count > 0)
        resp_payload['daily_counts'] = daily_counts

    # Case 2: Sub-Habits Group Habit
    elif h_type == 'sub_habits':
        sub_habits = target_habit.get('sub_habits', [])
        daily_sub_completions = target_habit.get('daily_sub_completions', {})
        if not isinstance(daily_sub_completions, dict):
            daily_sub_completions = {}

        sub_list = list(daily_sub_completions.get(day_str, []))
        sub_habit_id = data.get('sub_habit_id')

        if sub_habit_id:
            if sub_habit_id in sub_list:
                sub_list.remove(sub_habit_id)
                sub_checked = False
            else:
                sub_list.append(sub_habit_id)
                sub_checked = True
        else:
            # Toggle all sub-habits at once
            all_ids = [s.get('id') for s in sub_habits if isinstance(s, dict) and s.get('id')]
            if len(sub_list) >= len(all_ids) and len(all_ids) > 0:
                sub_list = []
                sub_checked = False
            else:
                sub_list = all_ids
                sub_checked = True

        if sub_list:
            daily_sub_completions[day_str] = sub_list
        else:
            daily_sub_completions.pop(day_str, None)

        total_subs = len(sub_habits)
        comp_count = len(sub_list)
        all_done = (comp_count == total_subs) and total_subs > 0

        if all_done or (comp_count > 0 and total_subs == 0):
            if day_int not in completed_days:
                completed_days.append(day_int)
        else:
            if day_int in completed_days:
                completed_days.remove(day_int)

        target_habit['daily_sub_completions'] = daily_sub_completions
        target_habit['completed_days'] = completed_days

        resp_payload['sub_habit_id'] = sub_habit_id
        resp_payload['sub_checked'] = sub_checked if sub_habit_id else None
        resp_payload['completed_sub_ids'] = sub_list
        resp_payload['completed_sub_count'] = comp_count
        resp_payload['total_sub_count'] = total_subs
        resp_payload['all_done'] = all_done
        resp_payload['checked'] = all_done

    # Case 3: Standard Boolean Checkbox Habit (Default)
    else:
        if day_int in completed_days:
            completed_days.remove(day_int)
            is_checked = False
        else:
            completed_days.append(day_int)
            is_checked = True

        target_habit['completed_days'] = completed_days
        resp_payload['checked'] = is_checked

    plan.habits = habits
    flag_modified(plan, 'habits')
    db.session.commit()

    return jsonify(resp_payload)

    return jsonify({'success': False, 'message': 'Habit not found'}), 404


@planner_api.route('/api/monthly/habit/momentum-yearly', methods=['GET'])
@token_required
def api_habit_momentum_yearly():
    """
    Get yearly habit momentum aggregation across all 12 months for momentum charts.
    ---
    tags:
      - Monthly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: year
        type: integer
        required: false
        description: Calendar year (defaults to current year)
    responses:
      200:
        description: Yearly habit momentum stats returned
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    import calendar as cal_mod
    try:
        year = int(request.args.get('year', get_today_date().year))
    except (ValueError, TypeError):
        year = get_today_date().year

    all_monthly = MonthlyPlan.query.filter_by(user_id=user.id, year=year).all()
    monthly_map = {mp.month: mp for mp in all_monthly}

    result = []
    for m in range(1, 13):
        days_in_month = cal_mod.monthrange(year, m)[1]
        mp = monthly_map.get(m)
        habits = mp.habits if (mp and mp.habits) else []
        total_habits = len(habits)
        completed_slots = sum(len(h.get('completed_days', [])) for h in habits)
        result.append({
            'month': m,
            'label': cal_mod.month_abbr[m],
            'total_habits': total_habits,
            'days_in_month': days_in_month,
            'completed_slots': completed_slots,
            'habits': [
                {
                    'id': h.get('id'),
                    'name': h.get('name', 'Habit'),
                    'completed_count': len(h.get('completed_days', []))
                }
                for h in habits
            ]
        })

    return jsonify({'success': True, 'data': result})


# ============================================================================
# YEARLY PLANNER REST API ENDPOINTS
# ============================================================================

@planner_api.route('/yearly', methods=['POST'])
@token_required
def api_yearly_post():
    """
    Handle yearly plan mutations (resolutions, quarterly objectives, annual events/birthdays, reflections).
    ---
    tags:
      - Yearly Planner
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: year
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            action:
              type: string
              enum: [add_resolution, toggle_resolution, delete_resolution, add_objective, update_objective_status, delete_objective, add_yearly_event, toggle_yearly_event, delete_yearly_event, save_reflections]
    responses:
      200:
        description: Yearly operation completed successfully
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    today = get_today_date()
    try:
        selected_year = int(request.args.get('year', today.year))
    except (ValueError, TypeError):
        selected_year = today.year

    plan = YearlyPlan.query.filter_by(user_id=user.id, year=selected_year).first()
    if not plan:
        plan = YearlyPlan(user_id=user.id, year=selected_year, resolutions=[], objectives=[], events=[], reflections='')
        db.session.add(plan)

    json_data = request.get_json(silent=True) or {}
    action = json_data.get('action') or request.form.get('action')

    resolutions = plan.resolutions or []
    objectives = plan.objectives or []
    events = plan.events or []

    if action == 'add_resolution':
        text = (json_data.get('resolution_text') or request.form.get('resolution_text', '')).strip()
        category = (json_data.get('category') or request.form.get('category', 'Personal')).strip()
        if text:
            new_res = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'text': text,
                'category': category,
                'completed': False
            }
            resolutions.append(new_res)
            plan.resolutions = resolutions
            flag_modified(plan, 'resolutions')
            db.session.commit()
            flash('Resolution added!', 'success')

    elif action == 'toggle_resolution':
        res_id = json_data.get('resolution_id') or request.form.get('resolution_id')
        for r in resolutions:
            if r.get('id') == res_id:
                r['completed'] = not r.get('completed', False)
        plan.resolutions = resolutions
        flag_modified(plan, 'resolutions')
        db.session.commit()

    elif action == 'delete_resolution':
        res_id = json_data.get('resolution_id') or request.form.get('resolution_id')
        plan.resolutions = [r for r in resolutions if r.get('id') != res_id]
        flag_modified(plan, 'resolutions')
        db.session.commit()

    elif action == 'add_objective':
        title = (json_data.get('objective_title') or request.form.get('objective_title', '')).strip()
        quarter = (json_data.get('quarter') or request.form.get('quarter', 'Q1')).strip()
        if title:
            new_obj = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'title': title,
                'quarter': quarter,
                'status': 'In Progress'
            }
            objectives.append(new_obj)
            plan.objectives = objectives
            flag_modified(plan, 'objectives')
            db.session.commit()
            flash('Objective added!', 'success')

    elif action == 'update_objective_status':
        obj_id = json_data.get('objective_id') or request.form.get('objective_id')
        new_status = json_data.get('status') or request.form.get('status', 'In Progress')
        for o in objectives:
            if o.get('id') == obj_id:
                o['status'] = new_status
        plan.objectives = objectives
        flag_modified(plan, 'objectives')
        db.session.commit()

    elif action == 'delete_objective':
        obj_id = json_data.get('objective_id') or request.form.get('objective_id')
        plan.objectives = [o for o in objectives if o.get('id') != obj_id]
        flag_modified(plan, 'objectives')
        db.session.commit()

    elif action == 'add_yearly_event':
        title = (json_data.get('event_title') or request.form.get('event_title', '')).strip()
        event_type = json_data.get('event_type') or request.form.get('event_type', 'goal')
        event_date = (json_data.get('event_date') or request.form.get('event_date', '')).strip()
        notes = (json_data.get('notes') or request.form.get('notes', '')).strip()
        if title and event_date:
            new_event = {
                'id': str(int(datetime.utcnow().timestamp() * 1000)),
                'title': title,
                'event_type': event_type,
                'date': event_date,
                'notes': notes,
                'completed': False
            }
            events.append(new_event)
            plan.events = events
            flag_modified(plan, 'events')
            db.session.commit()
            flash('Yearly event/goal added!', 'success')

    elif action == 'toggle_yearly_event':
        event_id = json_data.get('event_id') or request.form.get('event_id')
        for ev in events:
            if ev.get('id') == event_id:
                ev['completed'] = not ev.get('completed', False)
        plan.events = events
        flag_modified(plan, 'events')
        db.session.commit()

    elif action == 'delete_yearly_event':
        event_id = json_data.get('event_id') or request.form.get('event_id')
        plan.events = [ev for ev in events if ev.get('id') != event_id]
        flag_modified(plan, 'events')
        db.session.commit()
        flash('Yearly event removed.', 'info')

    elif action == 'save_reflections':
        reflections = (json_data.get('reflections') or request.form.get('reflections', '')).strip()
        plan.reflections = reflections
        db.session.commit()
        flash('Yearly reflections saved!', 'success')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.form.get('is_ajax') == 'true':
        tot_events = len(events)
        tot_res = len(resolutions)
        acc_res = sum(1 for r in resolutions if r.get('completed'))

        resp_data = {
            'success': True,
            'action': action,
            'total_events': tot_events,
            'total_resolutions': tot_res,
            'accomplished_resolutions': acc_res,
            'message': 'Operation completed successfully'
        }

        if action == 'add_yearly_event' and events:
            resp_data['event'] = events[-1]
            resp_data['message'] = 'Yearly event/goal added!'
        elif action == 'toggle_yearly_event':
            event_id = json_data.get('event_id') or request.form.get('event_id')
            ev_comp = next((ev.get('completed') for ev in events if ev.get('id') == event_id), False)
            resp_data['event_id'] = event_id
            resp_data['completed'] = ev_comp
            resp_data['message'] = 'Yearly event updated!'
        elif action == 'delete_yearly_event':
            resp_data['event_id'] = json_data.get('event_id') or request.form.get('event_id')
            resp_data['message'] = 'Yearly event removed.'
        elif action == 'add_resolution' and resolutions:
            resp_data['resolution'] = resolutions[-1]
            resp_data['message'] = 'Resolution added!'
        elif action == 'toggle_resolution':
            res_id = json_data.get('resolution_id') or request.form.get('resolution_id')
            r_comp = next((r.get('completed') for r in resolutions if r.get('id') == res_id), False)
            resp_data['resolution_id'] = res_id
            resp_data['completed'] = r_comp
            resp_data['message'] = 'Resolution updated!'
        elif action == 'delete_resolution':
            resp_data['resolution_id'] = json_data.get('resolution_id') or request.form.get('resolution_id')
            resp_data['message'] = 'Resolution removed.'
        elif action == 'add_objective' and objectives:
            resp_data['objective'] = objectives[-1]
            resp_data['message'] = 'Objective added!'
        elif action == 'update_objective_status':
            obj_id = json_data.get('objective_id') or request.form.get('objective_id')
            o_stat = next((o.get('status') for o in objectives if o.get('id') == obj_id), 'In Progress')
            resp_data['objective_id'] = obj_id
            resp_data['status'] = o_stat
            resp_data['message'] = 'Objective status updated!'
        elif action == 'delete_objective':
            resp_data['objective_id'] = json_data.get('objective_id') or request.form.get('objective_id')
            resp_data['message'] = 'Objective removed.'

        return jsonify(resp_data)
    return redirect(url_for('planner_ui.yearly', year=selected_year))


# ============================================================================
# PLANNING TASKS (BACKLOG) REST API ENDPOINTS
# ============================================================================

@planner_api.route('/api/planning/tasks', methods=['GET'])
@planner_api.route('/api/planning', methods=['GET'])
@token_required
def api_planning_get_tasks():
    """
    Get all planning backlog tasks, with optional filtering by status (all, pending, completed).
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: status
        type: string
        enum: [all, pending, completed]
        default: all
        description: Filter tasks by status (all, pending, completed)
    responses:
      200:
        description: List of planning tasks and summary counts
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    status_filter = request.args.get('status', 'all').lower()

    if status_filter == 'pending':
        tasks = (
            PlanningTask.query
            .filter_by(user_id=user.id, completed=False)
            .order_by(PlanningTask.sort_order.asc(), PlanningTask.created_at.asc())
            .all()
        )
    elif status_filter == 'completed':
        tasks = (
            PlanningTask.query
            .filter_by(user_id=user.id, completed=True)
            .order_by(PlanningTask.updated_at.desc(), PlanningTask.id.desc())
            .all()
        )
    else:
        pending = (
            PlanningTask.query
            .filter_by(user_id=user.id, completed=False)
            .order_by(PlanningTask.sort_order.asc(), PlanningTask.created_at.asc())
            .all()
        )
        completed = (
            PlanningTask.query
            .filter_by(user_id=user.id, completed=True)
            .order_by(PlanningTask.updated_at.desc(), PlanningTask.id.desc())
            .all()
        )
        total_pending = len(pending)
        total_completed = len(completed)
        return jsonify({
            'success': True,
            'tasks': [t.to_dict() for t in (pending + completed)],
            'pending_tasks': [t.to_dict() for t in pending],
            'completed_tasks': [t.to_dict() for t in completed],
            'total_pending': total_pending,
            'total_completed': total_completed,
            'total_tasks': total_pending + total_completed
        })

    total_pending = PlanningTask.query.filter_by(user_id=user.id, completed=False).count()
    total_completed = PlanningTask.query.filter_by(user_id=user.id, completed=True).count()

    return jsonify({
        'success': True,
        'tasks': [t.to_dict() for t in tasks],
        'total_pending': total_pending,
        'total_completed': total_completed,
        'total_tasks': total_pending + total_completed
    })


@planner_api.route('/api/planning/completed', methods=['GET'])
@token_required
def api_planning_completed_page():
    """
    Return a paginated batch of completed planning tasks.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: offset
        type: integer
        default: 10
        description: Offset index for pagination
    responses:
      200:
        description: Paginated completed tasks returned
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    COMPLETED_PAGE_SIZE = 10
    try:
        offset = int(request.args.get('offset', COMPLETED_PAGE_SIZE))
    except (ValueError, TypeError):
        offset = COMPLETED_PAGE_SIZE

    tasks = (
        PlanningTask.query
        .filter_by(user_id=user.id, completed=True)
        .order_by(PlanningTask.updated_at.desc(), PlanningTask.id.desc())
        .offset(offset)
        .limit(COMPLETED_PAGE_SIZE)
        .all()
    )
    total_completed = (
        PlanningTask.query
        .filter_by(user_id=user.id, completed=True)
        .count()
    )
    return jsonify({
        'success': True,
        'tasks': [t.to_dict() for t in tasks],
        'total_completed': total_completed,
        'offset': offset,
        'page_size': COMPLETED_PAGE_SIZE
    })


@planner_api.route('/api/planning/task/add', methods=['POST'])
@token_required
def api_planning_add_task():
    """
    Create a new persistent planning task in the backlog.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - text
          properties:
            text:
              type: string
            priority:
              type: string
              default: Medium
            tags:
              type: array
              items:
                type: string
    responses:
      200:
        description: Planning task created successfully
      400:
        description: Missing required text
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    text = data.get('text', '').strip()
    priority = data.get('priority', 'Medium')
    tags = data.get('tags', [])
    if isinstance(tags, str):
        tags = [x.strip() for x in tags.split(',') if x.strip()]

    if not text:
        return jsonify({'success': False, 'message': 'Task text is required'}), 400

    max_order = db.session.query(db.func.max(PlanningTask.sort_order)).filter_by(user_id=user.id).scalar() or 0

    task = PlanningTask(
        user_id=user.id,
        text=text,
        priority=priority,
        tags=tags,
        completed=False,
        sort_order=max_order + 1
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'success': True, 'task': task.to_dict()})


@planner_api.route('/api/planning/task/toggle', methods=['POST'])
@token_required
def api_planning_toggle_task():
    """
    Toggle completion status of a backlog planning task.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - task_id
          properties:
            task_id:
              type: integer
    responses:
      200:
        description: Task toggled successfully
      400:
        description: Missing task_id
      401:
        description: Unauthorized
      404:
        description: Task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'message': 'Missing task_id'}), 400

    task = PlanningTask.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify({'success': False, 'message': 'Task not found'}), 404

    task.completed = not task.completed
    db.session.commit()
    return jsonify({'success': True, 'completed': task.completed})


@planner_api.route('/api/planning/task/edit', methods=['POST'])
@token_required
def api_planning_edit_task():
    """
    Edit attributes of a backlog planning task.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - task_id
          properties:
            task_id:
              type: integer
            text:
              type: string
            priority:
              type: string
            tags:
              type: array
              items:
                type: string
    responses:
      200:
        description: Task updated successfully
      400:
        description: Missing parameters
      401:
        description: Unauthorized
      404:
        description: Task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'message': 'Missing task_id'}), 400

    task = PlanningTask.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify({'success': False, 'message': 'Task not found'}), 404

    if 'text' in data and data['text'].strip():
        task.text = data['text'].strip()
    if 'priority' in data:
        task.priority = data['priority']
    if 'tags' in data:
        tags = data['tags']
        if isinstance(tags, str):
            tags = [x.strip() for x in tags.split(',') if x.strip()]
        task.tags = tags

    db.session.commit()
    return jsonify({'success': True, 'task': task.to_dict()})


@planner_api.route('/api/planning/task/delete', methods=['POST'])
@token_required
def api_planning_delete_task():
    """
    Delete a backlog planning task.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - task_id
          properties:
            task_id:
              type: integer
    responses:
      200:
        description: Task deleted successfully
      400:
        description: Missing task_id
      401:
        description: Unauthorized
      404:
        description: Task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'message': 'Missing task_id'}), 400

    task = PlanningTask.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify({'success': False, 'message': 'Task not found'}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})


@planner_api.route('/api/planning/task/move_to_daily', methods=['POST'])
@token_required
def api_planning_move_to_daily():
    """
    Copy a planning task into today's DailyPlan tasks checklist and delete from Planning backlog.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - task_id
          properties:
            task_id:
              type: integer
    responses:
      200:
        description: Task moved to today's daily checklist successfully
      400:
        description: Missing task_id
      401:
        description: Unauthorized
      404:
        description: Task not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'message': 'Missing task_id'}), 400

    task = PlanningTask.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify({'success': False, 'message': 'Task not found'}), 404

    today = get_today_date()
    plan = DailyPlan.query.filter_by(user_id=user.id, date=today).first()
    if not plan:
        plan = DailyPlan(user_id=user.id, date=today, schedule={}, tasks=[], notes='')
        db.session.add(plan)

    daily_tasks = list(plan.tasks or [])
    new_daily_task = {
        'id': str(int(datetime.utcnow().timestamp() * 1000)),
        'text': task.text,
        'priority': task.priority,
        'tags': task.tags or [],
        'status': 'To Do',
        'note': '',
        'completed': False,
        'is_default': False,
        'is_spillover': False,
        'spillover_count': 0,
        'original_date': today.strftime('%Y-%m-%d')
    }
    daily_tasks.append(new_daily_task)
    plan.tasks = daily_tasks
    flag_modified(plan, 'tasks')

    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True, 'message': f"Task moved to today's Daily checklist ({today.strftime('%b %d')})"})


@planner_api.route('/api/planning/task/reorder', methods=['POST'])
@token_required
def api_planning_reorder_tasks():
    """
    Reorder planning backlog tasks.
    ---
    tags:
      - Planning Tasks Backlog
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - task_ids
          properties:
            task_ids:
              type: array
              items:
                type: integer
    responses:
      200:
        description: Tasks reordered successfully
      400:
        description: Invalid task_ids array
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    task_ids = data.get('task_ids', [])
    if not isinstance(task_ids, list):
        return jsonify({'success': False, 'message': 'task_ids must be a list'}), 400

    tasks = PlanningTask.query.filter_by(user_id=user.id).all()
    task_map = {t.id: t for t in tasks}

    for idx, tid in enumerate(task_ids):
        try:
            tid_int = int(tid)
        except (ValueError, TypeError):
            continue
        if tid_int in task_map:
            task_map[tid_int].sort_order = idx

    db.session.commit()
    return jsonify({'success': True})


# ============================================================================
# PLANNING EVENT TIME-TRACKER REST API ENDPOINTS
# ============================================================================

def _parse_event_datetime(dt_str):
    """Safely parse user-supplied datetime string in ISO, HTML5 datetime-local or standard formats."""
    if not dt_str:
        return None
    if isinstance(dt_str, datetime):
        return dt_str
    dt_str = str(dt_str).strip()
    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    try:
        # Handle ISO format with potential timezone offset or Z
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.replace(tzinfo=None)
    except Exception:
        return None


@planner_api.route('/api/planning/events', methods=['GET'])
@token_required
def api_planning_get_events():
    """
    Get all dynamic planning event time-trackers for the user.
    ---
    tags:
      - Planning Event Time-Trackers
    security:
      - Bearer: []
      - ApiKeyAuth: []
    responses:
      200:
        description: List of tracked planning events
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    events = (
        PlanningEvent.query
        .filter_by(user_id=user.id)
        .order_by(PlanningEvent.sort_order.asc(), PlanningEvent.target_datetime.asc())
        .all()
    )
    return jsonify({
        'success': True,
        'events': [e.to_dict() for e in events]
    })


@planner_api.route('/api/planning/event/add', methods=['POST'])
@token_required
def api_planning_add_event():
    """
    Create a new dynamic event time-tracker (auto-expire countdown, recurring window, or count-up).
    ---
    tags:
      - Planning Event Time-Trackers
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - title
          properties:
            title:
              type: string
            target_datetime:
              type: string
              example: "2026-12-31T23:59:59"
            category:
              type: string
              default: "General"
            notes:
              type: string
            color:
              type: string
              default: "#8b5cf6"
            icon:
              type: string
              default: "fa-calendar-check"
            timer_type:
              type: string
              enum: ["auto_expire", "recurring", "count_up"]
              default: "auto_expire"
            completion_message:
              type: string
              default: "Your countdown is over!"
            is_recurring:
              type: boolean
              default: false
            recurrence_frequency:
              type: string
              enum: ["daily", "monthly", "yearly"]
              default: "daily"
            window_start_time:
              type: string
              example: "10:00"
            window_end_time:
              type: string
              example: "19:00"
            inactive_message:
              type: string
              default: "Counter paused for this period"
    responses:
      200:
        description: Event time-tracker created successfully
      400:
        description: Missing required fields or invalid format
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    target_dt_raw = data.get('target_datetime')
    category = data.get('category', 'General')
    notes = data.get('notes', '').strip()
    color = data.get('color', '#8b5cf6')
    icon = data.get('icon', 'fa-calendar-check')

    timer_type = data.get('timer_type')
    is_recurring = bool(data.get('is_recurring', False))
    if not timer_type:
        timer_type = 'recurring' if is_recurring else 'auto_expire'
    if timer_type == 'recurring':
        is_recurring = True

    completion_message = data.get('completion_message', 'Your countdown is over!').strip() or 'Your countdown is over!'
    recurrence_frequency = data.get('recurrence_frequency', 'daily')
    if recurrence_frequency not in ['daily', 'monthly', 'yearly']:
        recurrence_frequency = 'daily'

    window_start_time = data.get('window_start_time')
    window_end_time = data.get('window_end_time')
    inactive_message = data.get('inactive_message', 'Counter paused for this period').strip() or 'Counter paused for this period'

    if not title:
        return jsonify({'success': False, 'message': 'Event title is required'}), 400

    target_dt = None
    if target_dt_raw:
        target_dt = _parse_event_datetime(target_dt_raw)
        if not target_dt and timer_type != 'recurring':
            return jsonify({'success': False, 'message': 'Invalid target datetime format'}), 400
    elif timer_type == 'recurring':
        target_dt = datetime.utcnow()
    else:
        return jsonify({'success': False, 'message': 'Target datetime is required for one-time events'}), 400

    if is_recurring or timer_type == 'recurring':
        if not window_start_time or not window_end_time:
            return jsonify({'success': False, 'message': 'Window start and end times are required for recurring events'}), 400

    max_order = db.session.query(db.func.max(PlanningEvent.sort_order)).filter_by(user_id=user.id).scalar() or 0

    event = PlanningEvent(
        user_id=user.id,
        title=title,
        target_datetime=target_dt or datetime.utcnow(),
        category=category,
        notes=notes,
        color=color,
        icon=icon,
        sort_order=max_order + 1,
        timer_type=timer_type,
        completion_message=completion_message,
        is_recurring=is_recurring,
        recurrence_frequency=recurrence_frequency,
        window_start_time=window_start_time,
        window_end_time=window_end_time,
        inactive_message=inactive_message
    )
    db.session.add(event)
    db.session.commit()

    return jsonify({'success': True, 'event': event.to_dict(), 'message': 'Event created successfully'})


@planner_api.route('/api/planning/event/edit', methods=['POST'])
@token_required
def api_planning_edit_event():
    """
    Edit an existing dynamic event time-tracker.
    ---
    tags:
      - Planning Event Time-Trackers
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - event_id
          properties:
            event_id:
              type: integer
            title:
              type: string
            target_datetime:
              type: string
            category:
              type: string
            notes:
              type: string
            color:
              type: string
            icon:
              type: string
            timer_type:
              type: string
            completion_message:
              type: string
            is_recurring:
              type: boolean
            recurrence_frequency:
              type: string
            window_start_time:
              type: string
            window_end_time:
              type: string
            inactive_message:
              type: string
    responses:
      200:
        description: Event time-tracker updated successfully
      400:
        description: Invalid inputs
      401:
        description: Unauthorized
      404:
        description: Event not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'success': False, 'message': 'Missing event_id'}), 400

    event = PlanningEvent.query.filter_by(id=event_id, user_id=user.id).first()
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'}), 404

    if 'title' in data:
        t = data['title'].strip()
        if not t:
            return jsonify({'success': False, 'message': 'Event title cannot be empty'}), 400
        event.title = t

    if 'target_datetime' in data:
        if data['target_datetime']:
            dt = _parse_event_datetime(data['target_datetime'])
            if not dt and data.get('timer_type', event.timer_type) != 'recurring':
                return jsonify({'success': False, 'message': 'Invalid target datetime format'}), 400
            if dt:
                event.target_datetime = dt

    if 'category' in data:
        event.category = data['category']
    if 'notes' in data:
        event.notes = data['notes'].strip()
    if 'color' in data:
        event.color = data['color']
    if 'icon' in data:
        event.icon = data['icon']

    if 'timer_type' in data:
        event.timer_type = data['timer_type']
        if event.timer_type == 'recurring':
            event.is_recurring = True
        elif event.timer_type in ['auto_expire', 'count_up']:
            event.is_recurring = False

    if 'is_recurring' in data:
        event.is_recurring = bool(data['is_recurring'])
        if event.is_recurring and event.timer_type != 'recurring':
            event.timer_type = 'recurring'

    if 'completion_message' in data:
        event.completion_message = data['completion_message'].strip() or 'Your countdown is over!'
    if 'recurrence_frequency' in data:
        event.recurrence_frequency = data['recurrence_frequency'] if data['recurrence_frequency'] in ['daily', 'monthly', 'yearly'] else 'daily'
    if 'window_start_time' in data:
        event.window_start_time = data['window_start_time']
    if 'window_end_time' in data:
        event.window_end_time = data['window_end_time']
    if 'inactive_message' in data:
        event.inactive_message = data['inactive_message'].strip() or 'Counter paused for this period'

    db.session.commit()
    return jsonify({'success': True, 'event': event.to_dict(), 'message': 'Event updated successfully'})



@planner_api.route('/api/planning/event/delete', methods=['POST'])
@token_required
def api_planning_delete_event():
    """
    Delete a planning event time-tracker.
    ---
    tags:
      - Planning Event Time-Trackers
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - event_id
          properties:
            event_id:
              type: integer
    responses:
      200:
        description: Event deleted successfully
      400:
        description: Missing event_id
      401:
        description: Unauthorized
      404:
        description: Event not found
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    event_id = data.get('event_id')
    if not event_id:
        return jsonify({'success': False, 'message': 'Missing event_id'}), 400

    event = PlanningEvent.query.filter_by(id=event_id, user_id=user.id).first()
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'}), 404

    db.session.delete(event)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Event deleted successfully'})


@planner_api.route('/api/planning/event/reorder', methods=['POST'])
@token_required
def api_planning_reorder_events():
    """
    Reorder planning event time-trackers.
    ---
    tags:
      - Planning Event Time-Trackers
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required:
            - event_ids
          properties:
            event_ids:
              type: array
              items:
                type: integer
    responses:
      200:
        description: Events reordered successfully
      400:
        description: Invalid event_ids array
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    data = request.get_json() or {}
    event_ids = data.get('event_ids', [])
    if not isinstance(event_ids, list):
        return jsonify({'success': False, 'message': 'event_ids must be a list'}), 400

    events = PlanningEvent.query.filter_by(user_id=user.id).all()
    event_map = {e.id: e for e in events}

    for idx, eid in enumerate(event_ids):
        try:
            eid_int = int(eid)
        except (ValueError, TypeError):
            continue
        if eid_int in event_map:
            event_map[eid_int].sort_order = idx

    db.session.commit()
    return jsonify({'success': True})


# ============================================================================
# TAGS MANAGEMENT REST API ENDPOINTS
# ============================================================================

@planner_api.route('/api/tags', methods=['GET', 'POST'])
@token_required
def api_user_tags():
    """
    Get or modify dynamic user task tags.
    ---
    tags:
      - Tags Management
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            action:
              type: string
              enum: [add, delete, edit]
            name:
              type: string
            color:
              type: string
            tag_id:
              type: string
    responses:
      200:
        description: Tags retrieved or modified successfully
      400:
        description: Invalid action or missing parameters
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    if request.method == 'GET':
        return jsonify({'success': True, 'tags': get_user_tags(user)})

    data = request.get_json() or {}
    action = data.get('action', 'add')
    user_tags = list(get_user_tags(user))

    if action == 'add':
        name = data.get('name', '').strip()
        color = data.get('color', '#3b82f6').strip()
        if name:
            new_tag = {
                'id': f'tag_{int(datetime.utcnow().timestamp() * 1000)}',
                'name': name,
                'color': color
            }
            user_tags.append(new_tag)
            user.custom_tags = user_tags
            flag_modified(user, 'custom_tags')
            db.session.commit()
            return jsonify({'success': True, 'tag': new_tag, 'tags': user_tags})
        return jsonify({'success': False, 'message': 'Tag name is required'}), 400

    elif action == 'delete':
        tag_id = data.get('tag_id')
        user_tags = [t for t in user_tags if t.get('id') != tag_id]
        user.custom_tags = user_tags
        flag_modified(user, 'custom_tags')
        db.session.commit()
        return jsonify({'success': True, 'tags': user_tags})

    elif action == 'edit':
        tag_id = data.get('tag_id')
        name = data.get('name', '').strip()
        color = data.get('color', '#3b82f6').strip()
        for t in user_tags:
            if t.get('id') == tag_id:
                if name:
                    t['name'] = name
                if color:
                    t['color'] = color
                break
        user.custom_tags = user_tags
        flag_modified(user, 'custom_tags')
        db.session.commit()
        return jsonify({'success': True, 'tags': user_tags})

    return jsonify({'success': False, 'message': 'Invalid tag action'}), 400


# ============================================================================
# GOOGLE DRIVE & BACKUP INTEGRATION REST API ENDPOINTS
# ============================================================================

@planner_api.route('/api/google/drive/sync', methods=['POST'])
@token_required
def api_google_drive_sync():
    """
    Trigger backup synchronization to Google Drive.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            force:
              type: boolean
              description: Force sync even if already synced today
    responses:
      200:
        description: Sync status and result returned
      401:
        description: Unauthorized
      500:
        description: Sync failure
    """
    user = get_current_user_safe()
    from app.services.google_service import sync_to_google_drive, is_admin
    from datetime import datetime
    try:
        body = request.get_json(silent=True) or {}
        force = bool(body.get('force', False))

        today_utc = datetime.utcnow().date()
        if not force and user.last_drive_sync:
            last_sync_date = user.last_drive_sync.date()
            if last_sync_date >= today_utc:
                last_sync_str = user.last_drive_sync.strftime('%d %b %Y, %I:%M %p UTC')
                return jsonify({
                    'success': True,
                    'already_synced_today': True,
                    'message': f'Already synced today at {last_sync_str}. Next sync available tomorrow.',
                    'last_sync': last_sync_str,
                    'last_sync_iso': user.last_drive_sync.isoformat()
                })

        res = sync_to_google_drive(user)
        last_sync_str = user.last_drive_sync.strftime('%d %b %Y, %I:%M %p UTC') if user.last_drive_sync else 'Just now'
        return jsonify({
            'success': res.get('success', False),
            'already_synced_today': False,
            'is_admin_backup': is_admin(user),
            'message': res.get('message', 'Drive sync completed'),
            'last_sync': last_sync_str,
            'last_sync_iso': user.last_drive_sync.isoformat() if user.last_drive_sync else None,
            'google_connected': res.get('google_connected', True)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Drive sync error: {str(e)}'}), 500


@planner_api.route('/api/google/drive/sync_status', methods=['GET'])
@token_required
def api_google_drive_sync_status():
    """
    Check Google Drive backup sync status and last sync timestamp.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    responses:
      200:
        description: Sync status details
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    from datetime import datetime
    today_utc = datetime.utcnow().date()
    synced_today = False
    last_sync_str = None
    last_sync_iso = None
    if user.last_drive_sync:
        last_sync_str = user.last_drive_sync.strftime('%d %b %Y, %I:%M %p UTC')
        last_sync_iso = user.last_drive_sync.isoformat()
        synced_today = user.last_drive_sync.date() >= today_utc
    return jsonify({
        'synced_today': synced_today,
        'last_sync': last_sync_str,
        'last_sync_iso': last_sync_iso
    })


@planner_api.route('/api/google/drive/restore', methods=['POST'])
@token_required
def api_google_drive_restore():
    """
    Restore planner data from Google Drive backup.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    responses:
      200:
        description: Data restored from Google Drive successfully
      400:
        description: Restore failed
      401:
        description: Unauthorized
      500:
        description: Server error
    """
    user = get_current_user_safe()
    from app.services.google_service import restore_from_google_drive
    try:
        res = restore_from_google_drive(user)
        if res.get('success'):
            flash('Successfully restored planner data from Google Drive!', 'success')
            return jsonify({'success': True, 'message': res.get('message')})
        return jsonify({'success': False, 'message': res.get('message', 'Drive restore failed')}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Drive restore error: {str(e)}'}), 500


@planner_api.route('/api/backup/export_json', methods=['GET'])
@token_required
def api_backup_export_json():
    """
    Export all planner records for the authenticated user as a downloadable JSON backup.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    responses:
      200:
        description: Downloadable JSON backup file attachment
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    from app.services.google_service import export_user_data_payload
    payload = export_user_data_payload(user)
    json_bytes = io.BytesIO(json.dumps(payload, indent=2).encode('utf-8'))
    filename = f"Chronos_Planner_Backup_{user.username}.json"
    return send_file(json_bytes, download_name=filename, as_attachment=True, mimetype="application/json")


@planner_api.route('/api/backup/restore_json', methods=['POST'])
@token_required
def api_backup_restore_json():
    """
    Restore planner records from an uploaded JSON file or raw JSON payload.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: formData
        name: backup_file
        type: file
        description: JSON backup file
      - in: body
        name: body
        schema:
          type: object
          description: Direct JSON backup payload
    responses:
      200:
        description: Data restored successfully
      400:
        description: Invalid JSON or restore payload
      401:
        description: Unauthorized
      500:
        description: Restore error
    """
    user = get_current_user_safe()
    from app.services.google_service import import_user_data_payload
    try:
        if 'backup_file' in request.files:
            file = request.files['backup_file']
            if not file.filename or file.filename == '':
                return jsonify({'success': False, 'message': 'No backup file selected'}), 400
            content = file.read().decode('utf-8-sig')
            payload = json.loads(content)
        elif request.is_json:
            payload = request.get_json()
        else:
            return jsonify({'success': False, 'message': 'No backup file or JSON payload provided'}), 400

        res = import_user_data_payload(user, payload)
        if isinstance(res, dict):
            msg = f"Local backup restored successfully! (Restored: {res.get('daily', 0)} Daily, {res.get('weekly', 0)} Weekly, {res.get('monthly', 0)} Monthly, {res.get('yearly', 0)} Yearly, {res.get('tasks', 0)} Tasks)"
            flash(msg, 'success')
            return jsonify({'success': True, 'message': msg, 'stats': res})
        elif res:
            flash('Successfully restored planner data from local JSON backup across all tables!', 'success')
            return jsonify({'success': True, 'message': 'Local backup restored successfully across all tables!'})
        return jsonify({'success': False, 'message': 'Failed to restore local backup'}), 400
    except json.JSONDecodeError:
        return jsonify({'success': False, 'message': 'Invalid JSON file format'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Restore error: {str(e)}'}), 500


@planner_api.route('/api/google/drive/folders', methods=['GET'])
@token_required
def api_google_drive_folders():
    """
    List folders in Google Drive for folder selection.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: parent_id
        type: string
        default: root
    responses:
      200:
        description: Folder list returned
      401:
        description: Unauthorized
      500:
        description: Error fetching folders
    """
    user = get_current_user_safe()
    from app.services.google_service import list_google_drive_folders
    try:
        parent_id = request.args.get('parent_id', 'root')
        folders = list_google_drive_folders(user, parent_id=parent_id)
        selected_folder_id = user.google_drive_folder_id or 'root'
        selected_folder_name = user.google_drive_folder_name or 'My Drive (Root Folder)'
        selected_folder_path = user.google_drive_folder_path or selected_folder_name
        return jsonify({
            'success': True,
            'folders': folders,
            'parent_id': parent_id,
            'current_folder_id': selected_folder_id,
            'current_folder_name': selected_folder_name,
            'current_folder_path': selected_folder_path
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Folder fetch error: {str(e)}'}), 500


@planner_api.route('/api/google/drive/folder_settings', methods=['POST'])
@token_required
def api_google_drive_folder_settings():
    """
    Set or create target Google Drive backup folder.
    ---
    tags:
      - Cloud Backup & Sync
    security:
      - Bearer: []
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            action:
              type: string
              enum: [select, create]
            folder_id:
              type: string
            folder_name:
              type: string
            folder_path:
              type: string
            parent_id:
              type: string
    responses:
      200:
        description: Target backup folder saved
      401:
        description: Unauthorized
    """
    user = get_current_user_safe()
    from app.services.google_service import create_google_drive_folder
    data = request.get_json() or {}
    folder_action = data.get('action', 'select')
    parent_id = data.get('parent_id', 'root')
    folder_path = data.get('folder_path', '')

    if folder_action == 'create':
        folder_name = data.get('folder_name', 'chronos planner folder')
        folder_info = create_google_drive_folder(user, folder_name, parent_id=parent_id)
        folder_id = folder_info['id']
        folder_name = folder_info['name']
    else:
        folder_id = data.get('folder_id', 'root')
        folder_name = data.get('folder_name', 'My Drive (Root Folder)')

    if not folder_path:
        folder_path = folder_name

    user.google_drive_folder_id = folder_id
    user.google_drive_folder_name = folder_name
    user.google_drive_folder_path = folder_path
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Backup target folder set to "{folder_name}"',
        'folder_id': folder_id,
        'folder_name': folder_name,
        'folder_path': folder_path
    })
