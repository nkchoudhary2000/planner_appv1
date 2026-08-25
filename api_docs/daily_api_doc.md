# Daily Planner REST API Documentation

Complete REST API specification and developer integration guide for the **Daily Planner** tab. This document is tailored for building frontend applications (React, Next.js, Vue, Angular, mobile, or CLI) in a separate repository.

---

## 1. Authentication & Base URL

### Base URL
- **Local Development**: `http://localhost:5000`
- **Production**: `https://<YOUR_DEPLOYED_DOMAIN>`

### Required Headers
All requests must include one of the following authentication headers:

```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer <YOUR_API_TOKEN>
```
*Alternative: `X-API-Token: <YOUR_API_TOKEN>` or query parameter `?api_token=<YOUR_API_TOKEN>`.*

---

## 2. Overview of Daily Planner Features & State

A single daily plan for a given date (`YYYY-MM-DD`) contains:
1. **Daily Tasks**: Checklist with priority (`High`, `Medium`, `Low`), custom tags, completion status, reordering index, and automatic cross-day spillover counters (`is_spillover`, `spillover_count`).
2. **24-Hour Hourly Schedule**: 24 time slots (e.g. `09:00 - 10:00 AM`) mapping to activity descriptions, emoji mood icons (e.g. `😄`, `⚡`, `😴`), and default template persistence.
3. **Daily Reflection / Notes**: Free-form markdown/plain text end-of-day reflection notes.
4. **Sleep Tracker Metrics**: Bedtime, wake time, total sleep hours, quality score (1–10), disruptions, and notes.
5. **Depression Episode & Symptom Logs**: Structured mental health episode tracker (start time, duration, intensity 1–10, triggers, coping mechanism, effectiveness rating, notes).
6. **Memory Slip Logs**: Track forgotten items/appointments (time, item, category, context, impact, recovery, notes).
7. **Cascaded Multi-Level Tasks**: Real-time read-only cascaded items pulled from Monthly Milestones, Weekly Goals/Daily Todos, and Yearly Events.
8. **Excel Export**: Generate formatted `.xlsx` spreadsheet for the day.

---

## 3. Endpoints Reference

### 3.1 Get Daily Plan Data
Retrieve full daily plan state, schedule, tasks, summary statistics, cascaded cross-tab items, and sleep/symptom trackers for a target date.

- **Method**: `GET`
- **Path**: `/api/daily` or `/api/daily/today`
- **Query Parameters**:
  | Param | Type | Required | Default | Description |
  | :--- | :--- | :--- | :--- | :--- |
  | `date` | `string` | No | Current Date (`today`) | Date formatted as `YYYY-MM-DD` |

#### Request Example
```bash
curl -X GET "http://localhost:5000/api/daily?date=2026-08-25" \
  -H "Authorization: Bearer cp_9a8b7c6d5e4f3a2b1c0d"
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "date": "2026-08-25",
  "is_today": true,
  "summary": {
    "total_tasks": 5,
    "completed_tasks": 3,
    "pending_tasks": 2,
    "completion_pct": 60
  },
  "tasks": [
    {
      "id": "1724581200000",
      "text": "Review Pull Requests and Sprint Backlog",
      "priority": "High",
      "tags": ["Work", "Code"],
      "completed": true,
      "is_default": false,
      "is_spillover": false,
      "spillover_count": 0,
      "original_date": "2026-08-25"
    },
    {
      "id": "1724581300000",
      "text": "30-minute Cardio Session",
      "priority": "Medium",
      "tags": ["Health"],
      "completed": false,
      "is_default": true,
      "is_spillover": true,
      "spillover_count": 1,
      "original_date": "2026-08-24"
    }
  ],
  "schedule": {
    "08:00 - 09:00 AM": {
      "activity": "Morning Coffee & Planning",
      "mood": "☕",
      "is_default": true
    },
    "09:00 - 10:00 AM": {
      "activity": "Team Daily Standup",
      "mood": "⚡",
      "is_default": false
    },
    "12:00 - 01:00 PM": {
      "activity": "Lunch & Reading",
      "mood": "🥗",
      "is_default": false
    }
  },
  "notes": "Productive morning. Solved the database bottleneck.",
  "sleep_log": {
    "hours": 7.5,
    "bedtime": "11:00 PM",
    "bedtime_24h": "23:00",
    "wake_time": "06:30 AM",
    "wake_time_24h": "06:30",
    "quality": 8,
    "disruptions": "Woke up once around 3 AM",
    "notes": "Felt refreshed upon waking",
    "updated_at": "06:35 AM"
  },
  "depression_episodes": [
    {
      "id": "1724589000000",
      "entry_time": "02:30 PM",
      "start_time": "02:00 PM",
      "duration": "45m",
      "intensity": 4,
      "triggers": "Work deadline stress",
      "coping_mechanism": "Breathwork and walk",
      "coping_effectiveness": "Helpful",
      "notes": "Calmed down after 20 minutes"
    }
  ],
  "memory_logs": [
    {
      "id": "1724591000000",
      "entry_time": "03:15 PM",
      "time": "03:00 PM",
      "item": "Forgot meeting zoom link",
      "category": "Work",
      "context": "Joining client sync",
      "impact": "Mild",
      "recovery": "Checked calendar invite",
      "notes": "Need to pin meeting links beforehand"
    }
  ],
  "cascaded_items": {
    "monthly_milestones": [
      {
        "id": "m1",
        "title": "Submit Quarterly Architecture RFC",
        "date": "25",
        "completed": false
      }
    ],
    "weekly_todos": [
      {
        "id": "wt1",
        "text": "Refactor API authentication middleware",
        "completed": true
      }
    ],
    "yearly_events": [
      {
        "id": "ye1",
        "title": "Team Quarterly Offsite",
        "event_type": "work",
        "date": "2026-08-25"
      }
    ]
  }
}
```

---

### 3.2 Add Task to Daily Checklist
Direct granular endpoint to append a new task to a specific day.

- **Method**: `POST`
- **Path**: `/api/daily/task/add`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "text": "Implement OAuth Refresh Token flow",
    "priority": "High",
    "tags": ["Work", "Backend", "Security"],
    "is_default": false
  }
  ```
  | Field | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `date` | `string` | No | Date in `YYYY-MM-DD` (defaults to today) |
  | `text` | `string` | Yes | Task title/description |
  | `priority` | `string` | No | `High`, `Medium`, or `Low` (default: `Medium`) |
  | `tags` | `string[]` | No | Array of tag strings |
  | `is_default` | `boolean`| No | If `true`, task is auto-seeded as default |

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Task added successfully",
  "task": {
    "id": "1724589999000",
    "text": "Implement OAuth Refresh Token flow",
    "priority": "High",
    "tags": ["Work", "Backend", "Security"],
    "completed": false,
    "is_default": false,
    "is_spillover": false,
    "spillover_count": 0,
    "original_date": "2026-08-25"
  },
  "total_tasks": 6,
  "completed_tasks": 3,
  "pending_tasks": 3,
  "completion_pct": 50
}
```

---

### 3.3 Edit Task in Daily Checklist
Update text, priority, tags, or default status of an existing task.

- **Method**: `POST`
- **Path**: `/api/daily/task/edit`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "task_id": "1724589999000",
    "text": "Implement OAuth Refresh Token & PKCE flow",
    "priority": "High",
    "tags": ["Work", "Security"],
    "is_default": false
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Task updated successfully",
  "task": {
    "id": "1724589999000",
    "text": "Implement OAuth Refresh Token & PKCE flow",
    "priority": "High",
    "tags": ["Work", "Security"],
    "completed": false
  }
}
```

---

### 3.4 Toggle Task Status
Toggle task completion (`completed: true / false`). Recalculates completion progress metrics.

- **Method**: `POST`
- **Path**: `/api/daily/task/toggle`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "task_id": "1724589999000"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "task_id": "1724589999000",
  "completed": true,
  "total_tasks": 6,
  "completed_tasks": 4,
  "pending_tasks": 2,
  "completion_pct": 67
}
```

---

### 3.5 Delete Task
Permanently delete a task from the daily checklist and mark it as dismissed to prevent unwanted spillovers.

- **Method**: `POST`
- **Path**: `/api/daily/task/delete`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "task_id": "1724589999000"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Task deleted successfully",
  "total_tasks": 5,
  "completed_tasks": 3,
  "pending_tasks": 2,
  "completion_pct": 60
}
```

---

### 3.6 Duplicate Task
Clone an existing task on the current date.

- **Method**: `POST`
- **Path**: `/api/daily/task/duplicate`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "task_id": "1724589999000"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Task duplicated successfully",
  "task": {
    "id": "1724590050000",
    "text": "Implement OAuth Refresh Token & PKCE flow",
    "priority": "High",
    "tags": ["Work", "Security"],
    "completed": false
  }
}
```

---

### 3.7 Reorder Tasks (Drag & Drop)
Save a new ordering array of task IDs.

- **Method**: `POST`
- **Path**: `/api/daily/task/reorder`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "task_ids": [
      "1724590050000",
      "1724581200000",
      "1724581300000"
    ]
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Tasks reordered successfully"
}
```

---

### 3.8 Update Hourly Schedule Slot
Quickly update a single time slot in the 24-hour daily timeline.

- **Method**: `POST`
- **Path**: `/api/daily/schedule/update`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "time_slot": "09:00 - 10:00 AM",
    "activity": "Sprint Planning & Backlog Grooming",
    "mood": "🎯",
    "is_default": false
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Schedule slot updated successfully",
  "time_slot": "09:00 - 10:00 AM",
  "activity": "Sprint Planning & Backlog Grooming",
  "mood": "🎯"
}
```

---

### 3.9 Update Daily Reflection Notes
Save markdown or text notes for the day.

- **Method**: `POST`
- **Path**: `/api/daily/notes/update`
- **Request Body (`application/json`)**:
  ```json
  {
    "date": "2026-08-25",
    "notes": "Accomplished major milestone on the frontend integration today."
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Daily notes updated successfully"
}
```

---

### 3.10 Unified Daily Mutations (`POST /daily`)
The unified `/daily` endpoint accepts action-based payloads for full form submits or modular widgets.

- **Method**: `POST`
- **Path**: `/daily?date=YYYY-MM-DD`
- **Supported `action` values**:
  1. `add_task`: Requires `task_text`, optional `priority`, `tags`, `is_default`.
  2. `delete_task`: Requires `task_id`.
  3. `save_schedule`: Payload containing slot keys (e.g. `"08:00 - 09:00 AM": {"activity": "...", "mood": "..."}`).
  4. `save_notes`: Requires `notes`.
  5. `save_sleep_log`: Requires `sleep_hours`, `bedtime`, `wake_time`, `sleep_quality`, `disruptions`, `notes`.
  6. `add_depression_episode`: Requires `start_time`, `duration`, `intensity`, `triggers`, `coping_mechanism`, `coping_effectiveness`, `notes`.
  7. `delete_depression_episode`: Requires `episode_id`.
  8. `add_memory_log`: Requires `time`, `item`, `category`, `context`, `impact`, `recovery`, `notes`.
  9. `delete_memory_log`: Requires `log_id`.

#### Example: Save Sleep Metrics
```json
{
  "action": "save_sleep_log",
  "date": "2026-08-25",
  "sleep_hours": 8.0,
  "bedtime": "22:30",
  "wake_time": "06:30",
  "sleep_quality": 9,
  "disruptions": "None",
  "notes": "Deep restful sleep"
}
```

---

### 3.11 Fetch Formatted Daily Activity Dataset
Generates an AI/LLM-ready or clipboard-friendly plain-text dataset summary of everything logged on a specific date.

- **Method**: `GET`
- **Path**: `/daily/fetch_activity?date=YYYY-MM-DD`

#### Response (`200 OK`)
```json
{
  "success": true,
  "date": "2026-08-25",
  "formatted_text": "=== DATASET: DAILY ACTIVITY LOG (2026-08-25, Tuesday) ===\n\nHourly Time Slots & Activities:\n  - 08:00 - 09:00 AM: Morning Coffee & Planning [Mood: ☕]\n  - 09:00 - 10:00 AM: Sprint Planning [Mood: 🎯]\n\nDaily Tasks:\n  - [Completed] Review Pull Requests (Priority: High)\n  - [Pending] 30-minute Cardio Session (Priority: Medium) [Spillover: 1d]\n\nSleep Log: 8.0 hrs (Bed: 10:30 PM, Wake: 06:30 AM, Quality: 9/10)\n\nEnd of Day Reflection & Notes: Accomplished major milestone on the frontend integration today."
}
```

---

### 3.12 Export Daily Plan to Excel
Download a formatted Excel (`.xlsx`) sheet of the daily planner data.

- **Method**: `GET`
- **Path**: `/daily/export_excel?date=YYYY-MM-DD`
- **Response**: Binary Excel file (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

---

## 4. Frontend TypeScript Data Interfaces

Copy these TypeScript interfaces into your frontend project:

```typescript
export interface DailyTask {
  id: string;
  text: string;
  priority: 'High' | 'Medium' | 'Low';
  tags: string[];
  completed: boolean;
  is_default?: boolean;
  is_spillover?: boolean;
  spillover_count?: number;
  original_date?: string;
}

export interface ScheduleSlot {
  activity: string;
  mood: string;
  is_default?: boolean;
  context?: string;
  tag?: string;
}

export interface SleepLog {
  hours: number;
  bedtime: string;
  bedtime_24h: string;
  wake_time: string;
  wake_time_24h: string;
  quality: number;
  disruptions: string;
  notes: string;
  updated_at?: string;
}

export interface DepressionEpisode {
  id: string;
  entry_time: string;
  start_time: string;
  duration: string;
  intensity: number; // 1 - 10
  triggers: string;
  coping_mechanism: string;
  coping_effectiveness: 'Helpful' | 'Moderate' | 'Ineffective';
  notes: string;
}

export interface MemoryLog {
  id: string;
  entry_time: string;
  time: string;
  item: string;
  category: string;
  context: string;
  impact: 'Mild' | 'Moderate' | 'Significant';
  recovery: string;
  notes: string;
}

export interface DailySummary {
  total_tasks: number;
  completed_tasks: number;
  pending_tasks: number;
  completion_pct: number;
}

export interface DailyPlanResponse {
  success: boolean;
  date: string;
  is_today: boolean;
  summary: DailySummary;
  tasks: DailyTask[];
  schedule: Record<string, ScheduleSlot>;
  notes: string;
  sleep_log?: SleepLog;
  depression_episodes?: DepressionEpisode[];
  memory_logs?: MemoryLog[];
  cascaded_items?: {
    monthly_milestones: Array<{ id: string; title: string; date: string; completed: boolean }>;
    weekly_todos: Array<{ id: string; text: string; completed: boolean }>;
    yearly_events: Array<{ id: string; title: string; event_type: string; date: string }>;
  };
}
```

---

## 5. Frontend API Service Example (JavaScript / TypeScript)

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

class DailyApiService {
  private static token: string = '';

  public static setToken(token: string) {
    this.token = token;
  }

  private static async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Authorization': `Bearer ${this.token}`,
      ...options.headers,
    };

    const res = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
    const data = await res.json();
    if (!res.ok || data.success === false) {
      throw new Error(data.message || 'Daily API request failed');
    }
    return data;
  }

  // Fetch plan for a given date
  public static getDailyPlan(date?: string): Promise<DailyPlanResponse> {
    const query = date ? `?date=${date}` : '';
    return this.request<DailyPlanResponse>(`/api/daily${query}`);
  }

  // Add task
  public static addTask(payload: { date: string; text: string; priority?: string; tags?: string[]; is_default?: boolean }) {
    return this.request('/api/daily/task/add', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // Toggle task completion
  public static toggleTask(date: string, taskId: string) {
    return this.request('/api/daily/task/toggle', {
      method: 'POST',
      body: JSON.stringify({ date, task_id: taskId }),
    });
  }

  // Update schedule slot
  public static updateScheduleSlot(payload: { date: string; time_slot: string; activity: string; mood: string; is_default?: boolean }) {
    return this.request('/api/daily/schedule/update', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // Save notes
  public static updateNotes(date: string, notes: string) {
    return this.request('/api/daily/notes/update', {
      method: 'POST',
      body: JSON.stringify({ date, notes }),
    });
  }
}

export default DailyApiService;
```
