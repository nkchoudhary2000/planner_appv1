# Planning System & Core Manager REST API Documentation

Complete REST API specification and developer integration guide for the **Planning Tasks Backlog**, **Dynamic Event Time-Trackers & Countdowns**, **User Custom Tags**, **Data Backup/Restore**, and **Google Drive Cloud Sync**.

---

## 1. Authentication & Base URL

### Base URL
- **Local Development**: `http://localhost:5000`
- **Production**: `https://<YOUR_DEPLOYED_DOMAIN>`

### Required Headers
```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer <YOUR_API_TOKEN>
```
*(You can also pass `X-API-Token: <token>` or `?api_token=<token>`)*

---

## 2. Planning Tasks Backlog API

Planning tasks are date-independent, persistent backlog tasks stored as individual database entities (`PlanningTask`). They never expire or automatically spill over until completed or explicitly transferred to a daily checklist.

### 2.1 Get Planning Tasks
Retrieve all backlog tasks with summary metrics and optional status filtering.

- **Method**: `GET`
- **Path**: `/api/planning/tasks` or `/api/planning`
- **Query Parameters**:
  | Param | Type | Values | Default | Description |
  | :--- | :--- | :--- | :--- | :--- |
  | `status` | `string` | `all`, `pending`, `completed` | `all` | Filter tasks by completion |

#### Response (`200 OK`)
```json
{
  "success": true,
  "tasks": [
    {
      "id": 101,
      "text": "Refactor state management in frontend repo",
      "priority": "High",
      "tags": ["tag_work", "tag_code"],
      "completed": false,
      "sort_order": 0,
      "created_at": "2026-08-25 10:00",
      "updated_at": "2026-08-25 10:00"
    }
  ],
  "pending_tasks": [ /* pending objects */ ],
  "completed_tasks": [ /* completed objects */ ],
  "total_pending": 4,
  "total_completed": 12,
  "total_tasks": 16
}
```

---

### 2.2 Add Planning Backlog Task
Create a new task in the planning backlog.

- **Method**: `POST`
- **Path**: `/api/planning/task/add`
- **Request Body (`application/json`)**:
  ```json
  {
    "text": "Set up CI/CD pipeline with GitHub Actions",
    "priority": "High",
    "tags": ["Work", "DevOps"]
  }
  ```
  | Field | Type | Required | Default | Description |
  | :--- | :--- | :--- | :--- | :--- |
  | `text` | `string` | Yes | - | Task title / description |
  | `priority` | `string` | No | `Medium` | `High`, `Medium`, or `Low` |
  | `tags` | `string[]` | No | `[]` | List of tag IDs or strings |

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Planning task created",
  "task": {
    "id": 102,
    "text": "Set up CI/CD pipeline with GitHub Actions",
    "priority": "High",
    "tags": ["Work", "DevOps"],
    "completed": false,
    "sort_order": 0,
    "created_at": "2026-08-25 12:45",
    "updated_at": "2026-08-25 12:45"
  }
}
```

---

### 2.3 Edit Planning Backlog Task
Update text, priority, or tags of an existing planning task.

- **Method**: `POST`
- **Path**: `/api/planning/task/edit`
- **Request Body (`application/json`)**:
  ```json
  {
    "task_id": 102,
    "text": "Set up automated CI/CD pipeline with GitHub Actions & Docker",
    "priority": "High",
    "tags": ["Work", "DevOps", "Docker"]
  }
  ```

---

### 2.4 Toggle Planning Task Status
Toggle task completion status (`completed: true / false`).

- **Method**: `POST`
- **Path**: `/api/planning/task/toggle`
- **Request Body (`application/json`)**:
  ```json
  {
    "task_id": 102
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "task_id": 102,
  "completed": true
}
```

---

### 2.5 Delete Planning Task
Permanently delete a task from the planning backlog.

- **Method**: `POST`
- **Path**: `/api/planning/task/delete`
- **Request Body (`application/json`)**:
  ```json
  {
    "task_id": 102
  }
  ```

---

### 2.6 Move Task to Daily Checklist
Transfer a task out of the long-term planning backlog and schedule it into a specific date's daily checklist.

- **Method**: `POST`
- **Path**: `/api/planning/task/move_to_daily`
- **Request Body (`application/json`)**:
  ```json
  {
    "task_id": 102,
    "target_date": "2026-08-25"
  }
  ```
  *If `target_date` is omitted, defaults to today.*

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Task moved to Daily Checklist for 2026-08-25",
  "target_date": "2026-08-25",
  "daily_task_id": "1724589999000"
}
```

---

### 2.7 Reorder Planning Tasks
Save new manual drag-and-drop ordering of task IDs.

- **Method**: `POST`
- **Path**: `/api/planning/task/reorder`
- **Request Body (`application/json`)**:
  ```json
  {
    "task_ids": [105, 101, 103, 104]
  }
  ```

---

### 2.8 Get Paginated Completed Tasks Archive
Retrieve completed backlog tasks with pagination support.

- **Method**: `GET`
- **Path**: `/api/planning/completed?page=1&per_page=20`
- **Query Parameters**:
  | Param | Type | Default | Description |
  | :--- | :--- | :--- | :--- |
  | `page` | `integer` | `1` | Current page number |
  | `per_page` | `integer` | `20` | Items per page (max 100) |

---

## 3. Dynamic Event Time-Tracker & Timers API

Tracks live countdowns, count-ups, recurring daily/monthly/yearly active time windows, and target date milestones.

### 3.1 Get All Planning Events
Retrieve all event timers and countdown configurations.

- **Method**: `GET`
- **Path**: `/api/planning/events`

#### Response (`200 OK`)
```json
{
  "success": true,
  "events": [
    {
      "id": 1,
      "title": "Product Launch Day",
      "target_datetime": "2026-09-01T09:00:00",
      "target_datetime_display": "Sep 01, 2026 • 09:00 AM",
      "category": "Milestone",
      "notes": "Global announcement and press release",
      "color": "#6366f1",
      "icon": "fa-rocket",
      "sort_order": 0,
      "timer_type": "auto_expire",
      "completion_message": "🚀 Product is officially LIVE!",
      "is_recurring": false,
      "recurrence_frequency": "daily",
      "window_start_time": "",
      "window_end_time": "",
      "inactive_message": "",
      "created_at": "2026-08-20 14:00:00",
      "updated_at": "2026-08-20 14:00:00"
    }
  ]
}
```

---

### 3.2 Add Planning Event / Timer
Create a new countdown timer, count-up tracker, or recurring window timer.

- **Method**: `POST`
- **Path**: `/api/planning/event/add`
- **Request Body (`application/json`)**:
  ```json
  {
    "title": "Daily Deep Work Focus Block",
    "category": "Focus",
    "notes": "No Slack, no emails",
    "color": "#10b981",
    "icon": "fa-brain",
    "timer_type": "recurring",
    "is_recurring": true,
    "recurrence_frequency": "daily",
    "window_start_time": "09:00",
    "window_end_time": "12:00",
    "completion_message": "Deep work session concluded!",
    "inactive_message": "Focus session starts at 09:00 AM"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Event created successfully",
  "event": {
    "id": 2,
    "title": "Daily Deep Work Focus Block",
    "color": "#10b981",
    "timer_type": "recurring"
  }
}
```

---

### 3.3 Edit Planning Event / Timer
Update parameters of an existing event timer.

- **Method**: `POST`
- **Path**: `/api/planning/event/edit`
- **Request Body (`application/json`)**:
  ```json
  {
    "event_id": 2,
    "title": "Daily Deep Work & Code Review",
    "target_datetime": "2026-08-26T09:00:00",
    "category": "Focus",
    "color": "#059669",
    "icon": "fa-code"
  }
  ```

---

### 3.4 Delete Planning Event
Remove an event timer.

- **Method**: `POST`
- **Path**: `/api/planning/event/delete`
- **Request Body (`application/json`)**:
  ```json
  {
    "event_id": 2
  }
  ```

---

### 3.5 Reorder Planning Events
Save new display ordering of event IDs.

- **Method**: `POST`
- **Path**: `/api/planning/event/reorder`
- **Request Body (`application/json`)**:
  ```json
  {
    "event_ids": [2, 1, 3]
  }
  ```

---

## 4. Custom User Tags API

Manage global tags and color badges used across tasks and time slots.

### 4.1 Get Tags List
Retrieve default and user-customized tags.

- **Method**: `GET`
- **Path**: `/api/tags`

#### Response (`200 OK`)
```json
{
  "success": true,
  "tags": [
    { "id": "work", "label": "Work", "color": "#3b82f6", "is_default": true },
    { "id": "personal", "label": "Personal", "color": "#10b981", "is_default": true },
    { "id": "health", "label": "Health", "color": "#ec4899", "is_default": true },
    { "id": "finance", "label": "Finance", "color": "#f59e0b", "is_default": true },
    { "id": "tag_crypto", "label": "Crypto", "color": "#8b5cf6", "is_default": false }
  ]
}
```

---

### 4.2 Add or Update Custom Tags
Add a new custom tag or update the user's custom tag list.

- **Method**: `POST`
- **Path**: `/api/tags`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add",
    "label": "Research",
    "color": "#06b6d4"
  }
  ```
  *To delete a custom tag, send `{"action": "delete", "tag_id": "tag_crypto"}`.*

---

## 5. Backup & Data Migration API

Export and import complete user account data in clean JSON format.

### 5.1 Export Entire Account Data (JSON)
Download full JSON backup of all Daily, Weekly, Monthly, Yearly plans, Planning Tasks, Events, and Tags.

- **Method**: `GET`
- **Path**: `/api/backup/export_json`
- **Response**: Full JSON document download with headers `Content-Disposition: attachment; filename=planner_backup_YYYYMMDD.json`.

---

### 5.2 Restore Entire Account Data (JSON)
Restore full planner state from a JSON backup payload.

- **Method**: `POST`
- **Path**: `/api/backup/restore_json`
- **Request Body (`application/json`)**:
  ```json
  {
    "version": "1.0",
    "exported_at": "2026-08-25T12:00:00Z",
    "daily_plans": [ /* ... */ ],
    "weekly_plans": [ /* ... */ ],
    "monthly_plans": [ /* ... */ ],
    "yearly_plans": [ /* ... */ ],
    "planning_tasks": [ /* ... */ ],
    "planning_events": [ /* ... */ ],
    "custom_tags": [ /* ... */ ]
  }
  ```

---

## 6. Google Drive Cloud Sync API

Perform manual or scheduled backups and restores to/from the user's connected Google Drive.

### 6.1 Trigger Immediate Google Drive Sync
- **Method**: `POST`
- **Path**: `/api/google/drive/sync`

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Backup successfully uploaded to Google Drive!",
  "file_id": "1A2B3C4D5E6F7G8H9I0J",
  "folder_name": "Chronos Planner Backups",
  "timestamp": "2026-08-25 12:50 UTC"
}
```

---

### 6.2 Get Google Drive Sync Status
- **Method**: `GET`
- **Path**: `/api/google/drive/sync_status`

#### Response (`200 OK`)
```json
{
  "success": true,
  "google_connected": true,
  "sync_enabled": true,
  "last_sync": "2026-08-25 12:50 UTC",
  "folder_id": "1A2B3C4D5E6F7G8H9I0J",
  "folder_name": "Chronos Planner Backups"
}
```

---

### 6.3 Restore Latest Backup from Google Drive
- **Method**: `POST`
- **Path**: `/api/google/drive/restore`

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Planner data successfully restored from Google Drive!"
}
```

---

### 6.4 Browse Google Drive Folders & Set Target Folder
- **Browse Folders (`GET /api/google/drive/folders`)**: List available folders in Google Drive.
- **Update Target Backup Folder (`POST /api/google/drive/folder_settings`)**:
  ```json
  {
    "folder_id": "1A2B3C4D5E6F7G8H9I0J",
    "folder_name": "My Custom Planner Backups"
  }
  ```

---

## 7. Frontend TypeScript Data Interfaces

```typescript
export interface PlanningTaskItem {
  id: number;
  text: string;
  priority: 'High' | 'Medium' | 'Low';
  tags: string[];
  completed: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PlanningEventItem {
  id: number;
  title: string;
  target_datetime?: string;
  target_datetime_display?: string;
  category: string;
  notes: string;
  color: string;
  icon: string;
  sort_order: number;
  timer_type: 'auto_expire' | 'recurring' | 'count_up';
  completion_message: string;
  is_recurring: boolean;
  recurrence_frequency: 'daily' | 'monthly' | 'yearly';
  window_start_time?: string;
  window_end_time?: string;
  inactive_message?: string;
  created_at: string;
  updated_at: string;
}

export interface TagItem {
  id: string;
  label: string;
  color: string;
  is_default: boolean;
}
```
