# Daily Task & Planner REST API Documentation

This document provides complete API reference, authentication instructions, request/response schemas, and ready-to-use code examples (cURL, Python, Node.js/JavaScript) for integrating with the Daily Task & Planner API from external web services, background bots, mobile apps, or automation workflows.

---

## Table of Contents
1. [Authentication](#1-authentication)
2. [Base URL & Headers](#2-base-url--headers)
3. [API Endpoints Reference](#3-api-endpoints-reference)
   - [3.1 View Daily Plan & Tasks (GET)](#31-view-daily-plan--tasks)
   - [3.2 Add New Task (POST)](#32-add-new-task)
   - [3.3 Edit Task (POST)](#33-edit-task)
   - [3.4 Toggle Task Status (POST)](#34-toggle-task-status)
   - [3.5 Delete Task (POST)](#35-delete-task)
   - [3.6 Duplicate Task (POST)](#36-duplicate-task)
   - [3.7 Reorder Tasks (POST)](#37-reorder-tasks)
   - [3.8 Update Hourly Schedule Slot (POST)](#38-update-hourly-schedule-slot)
   - [3.9 Update Daily Notes (POST)](#39-update-daily-notes)
4. [Task Data Structure](#4-task-data-structure)
5. [Code Examples](#5-code-examples)
   - [Python (`requests`)](#python-requests-example)
   - [JavaScript / TypeScript (`fetch`)](#javascript-fetch-example)
   - [cURL](#curl-examples)
6. [Generating / Managing API Tokens](#6-generating--managing-api-tokens)

---

## 1. Authentication

All API endpoints are protected using **API Token Authentication**. You can pass the token using any of the following 3 methods:

| Method | Syntax | Example |
| :--- | :--- | :--- |
| **HTTP Authorization Header** (Recommended) | `Authorization: Bearer <YOUR_API_TOKEN>` | `Authorization: Bearer cp_9a8b7c6d5e4f...` |
| **Custom Header** | `X-API-Token: <YOUR_API_TOKEN>` | `X-API-Token: cp_9a8b7c6d5e4f...` |
| **URL Query Parameter** | `?api_token=<YOUR_API_TOKEN>` | `https://your-domain.com/api/daily?api_token=cp_9a8b...` |

> [!TIP]
> Generate your personal API Token in the web app under **Account Settings / API Access** or via the `/auth/generate-api-token` endpoint.

---

## 2. Base URL & Headers

- **Local Development**: `http://localhost:5000`
- **Production**: `https://<YOUR_DEPLOYED_DOMAIN>`

### Standard Headers
```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer YOUR_API_TOKEN
```

---

## 3. API Endpoints Reference

### 3.1 View Daily Plan & Tasks
Retrieve the complete daily plan, task list, hourly activity schedule, mood logs, and completion statistics.

- **Method**: `GET`
- **Endpoint**: `/api/daily` or `/api/daily/today`
- **Query Parameters**:
  - `date` *(optional, string, format: `YYYY-MM-DD`)*: Target date. Defaults to today.

#### Request Example
```http
GET /api/daily?date=2026-08-21 HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Accept: application/json
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "date": "2026-08-21",
  "is_today": true,
  "summary": {
    "total_tasks": 3,
    "completed_tasks": 1,
    "pending_tasks": 2,
    "completion_pct": 33
  },
  "tasks": [
    {
      "id": "1724221500123",
      "text": "Review architecture PRs",
      "priority": "High",
      "tags": ["Engineering", "Review"],
      "status": "To Do",
      "completed": false,
      "note": "Focus on database indexes",
      "is_default": false,
      "is_spillover": false,
      "spillover_count": 0,
      "original_date": "2026-08-21"
    },
    {
      "id": "1724221500456",
      "text": "Morning team standup",
      "priority": "Medium",
      "tags": ["Meeting"],
      "status": "Completed",
      "completed": true,
      "note": "",
      "is_default": true,
      "is_spillover": false,
      "spillover_count": 0,
      "original_date": "2026-08-21"
    }
  ],
  "schedule": {
    "08:00 - 09:00 AM": {
      "activity": "Morning Routine & Planning",
      "mood": "😄",
      "is_default": true
    },
    "09:00 - 10:00 AM": {
      "activity": "Sprint Planning Meeting",
      "mood": "🤩",
      "is_default": false
    }
  },
  "notes": "Productive sprint morning.",
  "sleep_log": {
    "hours": 7.5,
    "quality": 9,
    "bedtime": "11:00 PM",
    "wake_time": "06:30 AM"
  },
  "cascaded_items": {
    "monthly_habits": [],
    "monthly_goals": [],
    "weekly_todos": []
  }
}
```

---

### 3.2 Add New Task
Create a new task in the daily planner for a specific date.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/add`
- **Request Body** (`application/json`):

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `date` | `string` | **Yes** | — | Target date (`YYYY-MM-DD`) |
| `text` | `string` | **Yes** | — | Task title / description |
| `priority` | `string` | No | `"Medium"` | `"High"`, `"Medium"`, or `"Low"` |
| `tags` | `array[string]` | No | `[]` | List of tag names e.g. `["Work", "Urgent"]` |
| `status` | `string` | No | `"To Do"` | `"To Do"`, `"In Progress"`, `"Completed"`, or `"Undone"` |
| `note` | `string` | No | `""` | Additional notes or sub-details |
| `is_default` | `boolean` | No | `false` | If `true`, auto-populates on every future day |

#### Request Example
```http
POST /api/daily/task/add HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Content-Type: application/json

{
  "date": "2026-08-21",
  "text": "Implement OAuth webhook handler",
  "priority": "High",
  "tags": ["Backend", "Auth"],
  "status": "To Do",
  "note": "Verify token expiry handling",
  "is_default": false
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "task": {
    "id": "1724222849102",
    "text": "Implement OAuth webhook handler",
    "priority": "High",
    "tags": ["Backend", "Auth"],
    "status": "To Do",
    "completed": false,
    "note": "Verify token expiry handling",
    "is_default": false,
    "is_spillover": false,
    "spillover_count": 0,
    "original_date": "2026-08-21"
  }
}
```

---

### 3.3 Edit Task
Update any attribute of an existing daily task (text, priority, status, tags, note, default).

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/edit`
- **Request Body** (`application/json`):

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `date` | `string` | **Yes** | Target date (`YYYY-MM-DD`) |
| `task_id` | `string` | **Yes** | ID of the task to edit |
| `text` | `string` | No | Updated task title |
| `priority` | `string` | No | `"High"`, `"Medium"`, `"Low"` |
| `status` | `string` | No | `"To Do"`, `"In Progress"`, `"Completed"`, `"Undone"` |
| `tags` | `array[string]` | No | Updated tag array |
| `note` | `string` | No | Updated notes |
| `is_default` | `boolean` | No | Enable/disable auto-daily recurrence |

#### Request Example
```http
POST /api/daily/task/edit HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Content-Type: application/json

{
  "date": "2026-08-21",
  "task_id": "1724222849102",
  "text": "Implement OAuth webhook handler (Completed test suite)",
  "priority": "High",
  "status": "Completed",
  "tags": ["Backend", "Auth", "Tested"]
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true
}
```

---

### 3.4 Toggle Task Status
Quickly toggle a task between completed (`true`) and incomplete (`false`).

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/toggle`
- **Request Body** (`application/json`):

```json
{
  "date": "2026-08-21",
  "task_id": "1724222849102"
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "completed": true
}
```

---

### 3.5 Delete Task
Permanently remove a task from a specific daily plan.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/delete`
- **Request Body** (`application/json`):

```json
{
  "date": "2026-08-21",
  "task_id": "1724222849102"
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true
}
```

---

### 3.6 Duplicate Task
Create an exact clone of an existing task on the same date.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/duplicate`
- **Request Body** (`application/json`):

```json
{
  "date": "2026-08-21",
  "task_id": "1724222849102"
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "task": {
    "id": "1724223100555",
    "text": "Implement OAuth webhook handler",
    "priority": "High",
    "status": "To Do",
    "completed": false,
    "tags": ["Backend", "Auth"]
  }
}
```

---

### 3.7 Reorder Tasks
Save custom drag-and-drop ordering for daily tasks.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/reorder`
- **Request Body** (`application/json`):

```json
{
  "date": "2026-08-21",
  "task_ids": [
    "1724222849102",
    "1724221500123",
    "1724221500456"
  ]
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true
}
```

---

### 3.8 Update Hourly Schedule Slot
Update the activity description, mood emoji, or recurrence for an hourly time slot.

- **Method**: `POST`
- **Endpoint**: `/api/daily/schedule/update`
- **Request Body** (`application/json`):

| Field | Type | Required | Example |
| :--- | :--- | :--- | :--- |
| `date` | `string` | **Yes** | `"2026-08-21"` |
| `slot` | `string` | **Yes** | `"09:00 - 10:00 AM"` (See slot format list below) |
| `activity` | `string` | No | `"Deep Work: API Integration"` |
| `mood` | `string` | No | `"😄"`, `"🤩"`, `"😊"`, `"😐"`, `"😓"`, `"😤"`, `"😴"`, `"🌧️"` |
| `is_default` | `boolean` | No | `false` |

> **Default Slot Format Strings (24 Hours)**:
> `"12:00 - 01:00 AM"`, `"01:00 - 02:00 AM"`, `"02:00 - 03:00 AM"`, `"03:00 - 04:00 AM"`,
> `"04:00 - 05:00 AM"`, `"05:00 - 06:00 AM"`, `"06:00 - 07:00 AM"`, `"07:00 - 08:00 AM"`,
> `"08:00 - 09:00 AM"`, `"09:00 - 10:00 AM"`, `"10:00 - 11:00 AM"`, `"11:00 - 12:00 PM"`,
> `"12:00 - 01:00 PM"`, `"01:00 - 02:00 PM"`, `"02:00 - 03:00 PM"`, `"03:00 - 04:00 PM"`,
> `"04:00 - 05:00 PM"`, `"05:00 - 06:00 PM"`, `"06:00 - 07:00 PM"`, `"07:00 - 08:00 PM"`,
> `"08:00 - 09:00 PM"`, `"09:00 - 10:00 PM"`, `"10:00 - 11:00 PM"`, `"11:00 - 12:00 AM"`

#### Request Example
```http
POST /api/daily/schedule/update HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Content-Type: application/json

{
  "date": "2026-08-21",
  "slot": "09:00 - 10:00 AM",
  "activity": "Deep Work Sprint",
  "mood": "🤩",
  "is_default": false
}
```

---

### 3.9 Update Daily Notes
Update the free-form notes / end-of-day reflection for a specific date.

- **Method**: `POST`
- **Endpoint**: `/api/daily/notes/update`
- **Request Body** (`application/json`):

```json
{
  "date": "2026-08-21",
  "notes": "Completed all high priority tasks before 4 PM."
}
```

---

## 4. Task Data Structure

Every task object in the database is represented as:

```typescript
interface DailyTask {
  id: string;              // Millisecond timestamp string (e.g. "1724222849102")
  text: string;            // Task title
  priority: "High" | "Medium" | "Low";
  tags: string[];          // e.g. ["Work", "Design"]
  status: "To Do" | "In Progress" | "Completed" | "Undone";
  completed: boolean;      // True if finished
  note?: string;           // Additional notes
  is_default: boolean;     // If true, recurs daily
  is_spillover: boolean;   // If true, carried over from prior day
  spillover_count: number; // Consecutive rollover days
  original_date: string;   // Date task was initially created ("YYYY-MM-DD")
}
```

---

## 5. Code Examples

### Python (`requests`) Example

```python
import requests

BASE_URL = "http://localhost:5000"
API_TOKEN = "cp_your_api_token_here"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Fetch Today's Daily Plan & Tasks
def get_daily_plan(date_str="2026-08-21"):
    res = requests.get(f"{BASE_URL}/api/daily", params={"date": date_str}, headers=headers)
    return res.json()

# 2. Add a New Task
def add_task(date_str, text, priority="High", tags=None):
    payload = {
        "date": date_str,
        "text": text,
        "priority": priority,
        "tags": tags or ["Integration", "Automated"],
        "status": "To Do"
    }
    res = requests.post(f"{BASE_URL}/api/daily/task/add", json=payload, headers=headers)
    return res.json()

# 3. Toggle Task Completion Status
def toggle_task(date_str, task_id):
    payload = {"date": date_str, "task_id": task_id}
    res = requests.post(f"{BASE_URL}/api/daily/task/toggle", json=payload, headers=headers)
    return res.json()

# 4. Edit an Existing Task
def edit_task(date_str, task_id, **updates):
    payload = {"date": date_str, "task_id": task_id, **updates}
    res = requests.post(f"{BASE_URL}/api/daily/task/edit", json=payload, headers=headers)
    return res.json()

# 5. Delete a Task
def delete_task(date_str, task_id):
    payload = {"date": date_str, "task_id": task_id}
    res = requests.post(f"{BASE_URL}/api/daily/task/delete", json=payload, headers=headers)
    return res.json()

if __name__ == "__main__":
    today = "2026-08-21"
    
    # Create task
    result = add_task(today, "Send quarterly report to client", priority="High")
    print("Add Task Result:", result)
    
    if result.get("success"):
        task_id = result["task"]["id"]
        
        # Toggle completed
        toggle_res = toggle_task(today, task_id)
        print("Toggle Status Result:", toggle_res)
        
        # Edit text
        edit_res = edit_task(today, task_id, text="Send quarterly report to client (Sent via Email)")
        print("Edit Task Result:", edit_res)
```

---

### JavaScript (`fetch`) Example

```javascript
const BASE_URL = 'http://localhost:5000';
const API_TOKEN = 'cp_your_api_token_here';

const authHeaders = {
    'Authorization': `Bearer ${API_TOKEN}`,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
};

// 1. Fetch Today's Tasks
async function fetchDailyPlan(date = '2026-08-21') {
    const res = await fetch(`${BASE_URL}/api/daily?date=${date}`, {
        method: 'GET',
        headers: authHeaders
    });
    return await res.json();
}

// 2. Add New Task
async function addTask(date, text, priority = 'Medium', tags = []) {
    const res = await fetch(`${BASE_URL}/api/daily/task/add`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ date, text, priority, tags, status: 'To Do' })
    });
    return await res.json();
}

// 3. Edit Task
async function editTask(date, taskId, updates = {}) {
    const res = await fetch(`${BASE_URL}/api/daily/task/edit`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ date, task_id: taskId, ...updates })
    });
    return await res.json();
}

// 4. Toggle Task Status
async function toggleTask(date, taskId) {
    const res = await fetch(`${BASE_URL}/api/daily/task/toggle`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ date, task_id: taskId })
    });
    return await res.json();
}

// 5. Delete Task
async function deleteTask(date, taskId) {
    const res = await fetch(`${BASE_URL}/api/daily/task/delete`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ date, task_id: taskId })
    });
    return await res.json();
}
```

---

### cURL Examples

#### 1. View Plan
```bash
curl -X GET "http://localhost:5000/api/daily?date=2026-08-21" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Accept: application/json"
```

#### 2. Add Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/add" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "date": "2026-08-21",
       "text": "Review microservices metrics",
       "priority": "High",
       "tags": ["DevOps", "Monitoring"]
     }'
```

#### 3. Edit Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/edit" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "date": "2026-08-21",
       "task_id": "1724222849102",
       "status": "Completed",
       "note": "Checked Grafana dashboards"
     }'
```

#### 4. Toggle Status
```bash
curl -X POST "http://localhost:5000/api/daily/task/toggle" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "date": "2026-08-21",
       "task_id": "1724222849102"
     }'
```

#### 5. Delete Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/delete" \
     -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "date": "2026-08-21",
       "task_id": "1724222849102"
     }'
```

---

## 6. Generating / Managing API Tokens

If you need to programmatically generate or revoke your API token:

### Generate New API Token
- **Method**: `POST`
- **Endpoint**: `/auth/generate-api-token`
- **Requires**: Active session or current token
- **Response**:
```json
{
  "success": true,
  "api_token": "cp_3f8a12e9b04c85d7e12f6a9c3d4e5f6a",
  "masked_token": "cp_3f8a...5f6a",
  "created_at": "2026-08-21 08:30 AM"
}
```

### Revoke API Token
- **Method**: `POST`
- **Endpoint**: `/auth/revoke-api-token`
- **Response**:
```json
{
  "success": true,
  "message": "API token revoked successfully."
}
```

### Check Token Info
- **Method**: `GET`
- **Endpoint**: `/auth/api-token-info`
- **Headers**: `Authorization: Bearer <TOKEN>`
