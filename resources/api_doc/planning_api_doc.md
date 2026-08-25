# Planning API & Tags Integration Documentation

Comprehensive REST API reference and frontend client integration guide for building Web & Progressive Web Apps (PWAs) to manage **Planning Backlog Tasks**, **Dynamic Event Time-Trackers**, and **Custom Tags** using **Token-Based Authentication**.

---

## Table of Contents

1. [Authentication & Authorization](#1-authentication--authorization)
   - [Authentication Protocol & Headers](#authentication-protocol--headers)
   - [User Isolation & Security Guarantees](#user-isolation--security-guarantees)
   - [Token Management Endpoints](#token-management-endpoints)
2. [Data Models & TypeScript Definitions](#2-data-models--typescript-definitions)
   - [PlanningTask Model](#planningtask-model)
   - [PlanningEvent Model](#planningevent-model)
   - [UserTag Model](#usertag-model)
   - [Complete TypeScript Interfaces](#complete-typescript-interfaces)
3. [Planning Backlog Tasks API Reference](#3-planning-backlog-tasks-api-reference)
   - [3.1 Get All Planning Tasks (`GET /api/planning/tasks` / `GET /api/planning`)](#31-get-all-planning-tasks)
   - [3.2 Get Completed Tasks with Pagination (`GET /api/planning/completed`)](#32-get-completed-tasks-with-pagination)
   - [3.3 Create Planning Task (`POST /api/planning/task/add`)](#33-create-planning-task)
   - [3.4 Toggle Task Completion (`POST /api/planning/task/toggle`)](#34-toggle-task-completion)
   - [3.5 Edit Planning Task (`POST /api/planning/task/edit`)](#35-edit-planning-task)
   - [3.6 Delete Planning Task (`POST /api/planning/task/delete`)](#36-delete-planning-task)
   - [3.7 Move Task to Today's Daily Plan (`POST /api/planning/task/move_to_daily`)](#37-move-task-to-todays-daily-plan)
   - [3.8 Reorder Backlog Tasks (`POST /api/planning/task/reorder`)](#38-reorder-backlog-tasks)
4. [Planning Event Time-Trackers API Reference](#4-planning-event-time-trackers-api-reference)
   - [4.1 Get All Tracked Events (`GET /api/planning/events`)](#41-get-all-tracked-events)
   - [4.2 Create Event Time-Tracker (`POST /api/planning/event/add`)](#42-create-event-time-tracker)
   - [4.3 Edit Event Time-Tracker (`POST /api/planning/event/edit`)](#43-edit-event-time-tracker)
   - [4.4 Delete Event Time-Tracker (`POST /api/planning/event/delete`)](#44-delete-event-time-tracker)
   - [4.5 Reorder Events (`POST /api/planning/event/reorder`)](#45-reorder-events)
5. [Tags Management & Task Tagging Integration](#5-tags-management--task-tagging-integration)
   - [5.1 Fetch User Tags (`GET /api/tags`)](#51-fetch-user-tags)
   - [5.2 Add / Edit / Delete Tags (`POST /api/tags`)](#52-add--edit--delete-tags)
   - [5.3 Assigning and Filtering Tags on Planning Tasks](#53-assigning-and-filtering-tags-on-planning-tasks)
6. [Standard Error Responses & HTTP Status Codes](#6-standard-error-responses--http-status-codes)
7. [Frontend / PWA Integration Client](#7-frontend--pwa-integration-client)
   - [Complete TypeScript API Client (`PlanningApiClient.ts`)](#complete-typescript-api-client)
   - [React Hook Integration Example (`usePlanning.ts`)](#react-hook-integration-example)
8. [cURL Quick Reference](#8-curl-quick-reference)

---

## 1. Authentication & Authorization

All Planning and Tag API endpoints require authentication via an **API Token**. Only authorized users with a valid token can read or modify data.

### Authentication Protocol & Headers

Tokens are generated per user account and formatted with a `cp_` prefix (e.g. `cp_9a8b7c6d5e4f...`).

When making HTTP requests from your frontend application, supply the token via one of the following methods (evaluated in priority order):

| Priority | Method | Header / Parameter | Example |
| :--- | :--- | :--- | :--- |
| **1 (Recommended)** | HTTP `Authorization` Header | `Authorization: Bearer <API_TOKEN>` | `Authorization: Bearer cp_7a8b9c0d...` |
| **2** | Custom Header | `X-API-Token: <API_TOKEN>` | `X-API-Token: cp_7a8b9c0d...` |
| **3** | URL Query Parameter | `?api_token=<API_TOKEN>` | `https://api.yourdomain.com/api/planning/tasks?api_token=cp_...` |
| **4** | JSON Request Body | `"api_token": "<API_TOKEN>"` | `{"api_token": "cp_...", "text": "New task"}` |

> [!IMPORTANT]
> Always use the **`Authorization: Bearer <API_TOKEN>`** header for security, caching compatibility, and clean separation of query parameters.

### User Isolation & Security Guarantees

- **Database-Level Isolation**: Every query automatically filters on `user_id == authenticated_user.id`.
- **Zero Cross-Account Leakage**: A user cannot access, modify, reorder, or delete tasks/events belonging to another user.
- **Immediate Invalidation**: When a token is revoked or rotated, all incoming requests using the old token are rejected with `HTTP 401 Unauthorized`.

---

### Token Management Endpoints

#### 1. Generate / Rotate API Token
Creates a new permanent token or rotates an existing one.

- **Method**: `POST`
- **Endpoint**: `/auth/generate-api-token`
- **Auth**: Active session cookie or existing token
- **Response (`200 OK`)**:
```json
{
  "success": true,
  "message": "New API token generated successfully!",
  "api_token": "cp_3f8a9e2d1c4b5a67890ef1234567890abcdef1234567890abcdef1234567890a",
  "masked_token": "cp_3f8a...890a",
  "created_at": "2026-08-25 08:30:00 UTC"
}
```

#### 2. Verify API Token Status
Checks if the current authenticated user has an active token.

- **Method**: `GET`
- **Endpoint**: `/auth/api-token-info`
- **Headers**: `Authorization: Bearer <YOUR_API_TOKEN>`
- **Response (`200 OK`)**:
```json
{
  "success": true,
  "has_token": true,
  "masked_token": "cp_3f8a...890a",
  "created_at": "2026-08-25 08:30:00 UTC"
}
```

#### 3. Revoke API Token
Immediately invalidates the token.

- **Method**: `POST`
- **Endpoint**: `/auth/revoke-api-token`
- **Headers**: `Authorization: Bearer <YOUR_API_TOKEN>`
- **Response (`200 OK`)**:
```json
{
  "success": true,
  "message": "API token revoked successfully!"
}
```

---

## 2. Data Models & TypeScript Definitions

### PlanningTask Model
Persistent, date-independent backlog tasks. Unlike Daily Plan tasks (which are tied to specific calendar dates and subject to daily rollovers), `PlanningTask` rows live in the backlog until completed, deleted, or moved into Today's Daily plan.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `number` | Unique task ID (database integer primary key) | `104` |
| `text` | `string` | Task description / title | `"Finalize Q4 Product Roadmap"` |
| `priority` | `'High' \| 'Medium' \| 'Low'` | Priority level (Default: `'Medium'`) | `"High"` |
| `tags` | `string[]` | Array of associated tag IDs | `["tag_work", "tag_urgent"]` |
| `completed` | `boolean` | Completion state | `false` |
| `sort_order` | `number` | Integer position for manual drag-and-drop ordering | `1` |
| `created_at` | `string` | Creation timestamp (`YYYY-MM-DD HH:MM`) | `"2026-08-25 10:15"` |
| `updated_at` | `string` | Last update timestamp (`YYYY-MM-DD HH:MM`) | `"2026-08-25 11:30"` |

---

### PlanningEvent Model
Dynamic time-trackers supporting **Auto-Expire countdowns**, **Recurring time windows**, and **Count-Up timers**.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `number` | Event ID primary key | `42` |
| `title` | `string` | Event title | `"Product Launch v2"` |
| `target_datetime` | `string` | ISO timestamp target (`YYYY-MM-DDTHH:MM:SS`) | `"2026-10-01T15:00:00"` |
| `target_datetime_display` | `string` | Pre-formatted display date | `"Oct 01, 2026 • 03:00 PM"` |
| `category` | `string` | Grouping category (`Milestone`, `Deadline`, etc.) | `"Milestone"` |
| `notes` | `string` | Additional notes/context | `"All systems go for launch"` |
| `color` | `string` | Hex accent color code | `"#8b5cf6"` |
| `icon` | `string` | FontAwesome icon class | `"fa-rocket"` |
| `sort_order` | `number` | Reordering index | `0` |
| `timer_type` | `'auto_expire' \| 'recurring' \| 'count_up'` | Timer behavior mode | `"recurring"` |
| `completion_message` | `string` | Notification message when countdown finishes | `"Countdown completed!"` |
| `is_recurring` | `boolean` | Whether recurring mode is enabled | `true` |
| `recurrence_frequency` | `'daily' \| 'monthly' \| 'yearly'` | Repeat frequency | `"daily"` |
| `window_start_time` | `string` | Active time window start (`HH:MM`) | `"09:00"` |
| `window_end_time` | `string` | Active time window end (`HH:MM`) | `"18:00"` |
| `inactive_message` | `string` | Display message when outside active window | `"Counter paused for the day"` |

---

### UserTag Model
Customizable, color-coded tags for categorization.

| Property | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Unique tag identifier | `"tag_work"` or `"tag_1724221500123"` |
| `name` | `string` | Tag display name | `"Engineering"` |
| `color` | `string` | Hex color code for badges | `"#3b82f6"` |

---

### Complete TypeScript Interfaces

```typescript
export type TaskPriority = 'High' | 'Medium' | 'Low';
export type TimerType = 'auto_expire' | 'recurring' | 'count_up';
export type RecurrenceFrequency = 'daily' | 'monthly' | 'yearly';

export interface UserTag {
  id: string;
  name: string;
  color: string;
}

export interface PlanningTask {
  id: number;
  text: string;
  priority: TaskPriority;
  tags: string[];
  completed: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PlanningEvent {
  id: number;
  title: string;
  target_datetime: string;
  target_datetime_display: string;
  category: string;
  notes: string;
  color: string;
  icon: string;
  sort_order: number;
  timer_type: TimerType;
  completion_message: string;
  is_recurring: boolean;
  recurrence_frequency: RecurrenceFrequency;
  window_start_time?: string;
  window_end_time?: string;
  inactive_message?: string;
  created_at: string;
  updated_at: string;
}

export interface PlanningTasksResponse {
  success: boolean;
  tasks: PlanningTask[];
  pending_tasks?: PlanningTask[];
  completed_tasks?: PlanningTask[];
  total_tasks: number;
  total_pending: number;
  total_completed: number;
}

export interface CompletedTasksPaginatedResponse {
  success: boolean;
  tasks: PlanningTask[];
  total_completed: number;
  offset: number;
  page_size: number;
}

export interface PlanningEventsResponse {
  success: boolean;
  events: PlanningEvent[];
}

export interface UserTagsResponse {
  success: boolean;
  tags: UserTag[];
}
```

---

## 3. Planning Backlog Tasks API Reference

### Base URL
- **Local Dev**: `http://localhost:5000`
- **Production**: `https://<YOUR_DEPLOYED_DOMAIN>`

---

### 3.1 Get All Planning Tasks
Fetches all planning tasks, with optional status filtering (`all`, `pending`, `completed`).

- **Method**: `GET`
- **Endpoint**: `/api/planning/tasks` *(or `/api/planning`)*
- **Headers**: `Authorization: Bearer <API_TOKEN>`
- **Query Parameters**:
  - `status` *(optional, string)*: `'all'` (default), `'pending'`, or `'completed'`

#### Example Response (`200 OK` - `?status=all`):
```json
{
  "success": true,
  "tasks": [
    {
      "id": 101,
      "text": "Design system dark mode audit",
      "priority": "High",
      "tags": ["tag_work", "tag_urgent"],
      "completed": false,
      "sort_order": 0,
      "created_at": "2026-08-25 09:00",
      "updated_at": "2026-08-25 09:00"
    },
    {
      "id": 98,
      "text": "Refactor authentication middleware",
      "priority": "Medium",
      "tags": ["tag_work"],
      "completed": true,
      "sort_order": 2,
      "created_at": "2026-08-24 14:20",
      "updated_at": "2026-08-25 08:15"
    }
  ],
  "pending_tasks": [
    {
      "id": 101,
      "text": "Design system dark mode audit",
      "priority": "High",
      "tags": ["tag_work", "tag_urgent"],
      "completed": false,
      "sort_order": 0,
      "created_at": "2026-08-25 09:00",
      "updated_at": "2026-08-25 09:00"
    }
  ],
  "completed_tasks": [
    {
      "id": 98,
      "text": "Refactor authentication middleware",
      "priority": "Medium",
      "tags": ["tag_work"],
      "completed": true,
      "sort_order": 2,
      "created_at": "2026-08-24 14:20",
      "updated_at": "2026-08-25 08:15"
    }
  ],
  "total_pending": 1,
  "total_completed": 1,
  "total_tasks": 2
}
```

---

### 3.2 Get Completed Tasks with Pagination
Retrieves older completed tasks in paginated batches (10 per batch) sorted newest completed first.

- **Method**: `GET`
- **Endpoint**: `/api/planning/completed`
- **Headers**: `Authorization: Bearer <API_TOKEN>`
- **Query Parameters**:
  - `offset` *(optional, integer, default: `10`)*: Offset index for pagination.

#### Example Response (`200 OK`):
```json
{
  "success": true,
  "tasks": [
    {
      "id": 92,
      "text": "Setup CI/CD deployment pipeline",
      "priority": "High",
      "tags": ["tag_work"],
      "completed": true,
      "sort_order": 5,
      "created_at": "2026-08-20 11:00",
      "updated_at": "2026-08-23 16:30"
    }
  ],
  "total_completed": 24,
  "offset": 10,
  "page_size": 10
}
```

---

### 3.3 Create Planning Task
Adds a new persistent backlog task.

- **Method**: `POST`
- **Endpoint**: `/api/planning/task/add`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "text": "Implement PWA Offline Sync support",
  "priority": "High",
  "tags": ["tag_work", "tag_urgent"]
}
```

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `string` | **Yes** | - | Task description |
| `priority` | `string` | No | `"Medium"` | `'High'`, `'Medium'`, or `'Low'` |
| `tags` | `string[] \| string` | No | `[]` | Array or comma-separated list of tag IDs |

#### Response (`200 OK`):
```json
{
  "success": true,
  "task": {
    "id": 105,
    "text": "Implement PWA Offline Sync support",
    "priority": "High",
    "tags": ["tag_work", "tag_urgent"],
    "completed": false,
    "sort_order": 3,
    "created_at": "2026-08-25 10:30",
    "updated_at": "2026-08-25 10:30"
  }
}
```

---

### 3.4 Toggle Task Completion
Toggles the completion status of a backlog task.

- **Method**: `POST`
- **Endpoint**: `/api/planning/task/toggle`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "task_id": 105
}
```

#### Response (`200 OK`):
```json
{
  "success": true,
  "completed": true
}
```

---

### 3.5 Edit Planning Task
Updates text, priority, or tags of an existing planning task.

- **Method**: `POST`
- **Endpoint**: `/api/planning/task/edit`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "task_id": 105,
  "text": "Implement PWA Offline Sync & Background Sync",
  "priority": "Medium",
  "tags": ["tag_work", "tag_finance"]
}
```

#### Response (`200 OK`):
```json
{
  "success": true,
  "task": {
    "id": 105,
    "text": "Implement PWA Offline Sync & Background Sync",
    "priority": "Medium",
    "tags": ["tag_work", "tag_finance"],
    "completed": false,
    "sort_order": 3,
    "created_at": "2026-08-25 10:30",
    "updated_at": "2026-08-25 10:45"
  }
}
```

---

### 3.6 Delete Planning Task
Permanently deletes a planning backlog task.

- **Method**: `POST`
- **Endpoint**: `/api/planning/task/delete`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "task_id": 105
}
```

#### Response (`200 OK`):
```json
{
  "success": true
}
```

---

### 3.7 Move Task to Today's Daily Plan
Copies the planning backlog task into today's `DailyPlan` checklist and removes it from the planning backlog.

- **Method**: `POST`
- **Endpoint**: `/api/planning/task/move_to_daily`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "task_id": 105
}
```

#### Response (`200 OK`):
```json
{
  "success": true,
  "message": "Task moved to today's Daily checklist (Aug 25)"
}
```

---

### 3.8 Reorder Backlog Tasks
Saves custom drag-and-drop sort orders for planning tasks.

- **Method**: `POST`
- **Endpoint**: `/api/planning/task/reorder`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "task_ids": [103, 101, 105, 99]
}
```

#### Response (`200 OK`):
```json
{
  "success": true
}
```

---

## 4. Planning Event Time-Trackers API Reference

Dynamic time-trackers manage milestones, deadlines, work hour windows, and count-ups.

---

### 4.1 Get All Tracked Events
Returns all active planning events for the authenticated user.

- **Method**: `GET`
- **Endpoint**: `/api/planning/events`
- **Headers**: `Authorization: Bearer <API_TOKEN>`

#### Response (`200 OK`):
```json
{
  "success": true,
  "events": [
    {
      "id": 12,
      "title": "Quarterly OKR Review",
      "target_datetime": "2026-09-30T17:00:00",
      "target_datetime_display": "Sep 30, 2026 • 05:00 PM",
      "category": "Milestone",
      "notes": "Prepare presentation slides",
      "color": "#8b5cf6",
      "icon": "fa-calendar-check",
      "sort_order": 0,
      "timer_type": "auto_expire",
      "completion_message": "Quarterly review time!",
      "is_recurring": false,
      "recurrence_frequency": "daily",
      "window_start_time": "",
      "window_end_time": "",
      "inactive_message": "Counter paused for this period",
      "created_at": "2026-08-25 09:15:00",
      "updated_at": "2026-08-25 09:15:00"
    },
    {
      "id": 14,
      "title": "Daily Deep Work Block",
      "target_datetime": "2026-08-25T08:30:00",
      "target_datetime_display": "Aug 25, 2026 • 08:30 AM",
      "category": "Work",
      "notes": "No Slack / notifications",
      "color": "#10b981",
      "icon": "fa-brain",
      "sort_order": 1,
      "timer_type": "recurring",
      "completion_message": "Deep work session concluded",
      "is_recurring": true,
      "recurrence_frequency": "daily",
      "window_start_time": "10:00",
      "window_end_time": "18:00",
      "inactive_message": "Deep work window is inactive",
      "created_at": "2026-08-24 10:00:00",
      "updated_at": "2026-08-24 10:00:00"
    }
  ]
}
```

---

### 4.2 Create Event Time-Tracker
Creates a new countdown, recurring window, or count-up timer.

- **Method**: `POST`
- **Endpoint**: `/api/planning/event/add`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "title": "Annual Company Summit",
  "target_datetime": "2026-11-15T09:00:00",
  "category": "Celebration",
  "notes": "Book flights and hotel accommodation",
  "color": "#f59e0b",
  "icon": "fa-plane-departure",
  "timer_type": "auto_expire",
  "completion_message": "Summit starts now!"
}
```

#### Field Specifications:

| Field | Type | Required | Default | Allowed Values / Format |
| :--- | :--- | :--- | :--- | :--- |
| `title` | `string` | **Yes** | - | Event title |
| `target_datetime` | `string` | Conditionally | - | ISO string e.g. `"2026-12-31T23:59:59"` (Required for `auto_expire` / `count_up`) |
| `category` | `string` | No | `"General"` | Custom category string |
| `notes` | `string` | No | `""` | Additional notes |
| `color` | `string` | No | `"#8b5cf6"` | Hex color code |
| `icon` | `string` | No | `"fa-calendar-check"` | FontAwesome class |
| `timer_type` | `string` | No | `"auto_expire"` | `'auto_expire'`, `'recurring'`, `'count_up'` |
| `completion_message` | `string` | No | `"Your countdown is over!"` | Message when timer expires |
| `is_recurring` | `boolean` | No | `false` | Set `true` for recurring active window timers |
| `recurrence_frequency`| `string` | No | `"daily"` | `'daily'`, `'monthly'`, `'yearly'` |
| `window_start_time` | `string` | If recurring | `""` | Format `"HH:MM"` (e.g. `"09:00"`) |
| `window_end_time` | `string` | If recurring | `""` | Format `"HH:MM"` (e.g. `"17:00"`) |
| `inactive_message` | `string` | No | `"Counter paused for this period"` | Message when outside window |

#### Response (`200 OK`):
```json
{
  "success": true,
  "message": "Event created successfully",
  "event": {
    "id": 15,
    "title": "Annual Company Summit",
    "target_datetime": "2026-11-15T09:00:00",
    "target_datetime_display": "Nov 15, 2026 • 09:00 AM",
    "category": "Celebration",
    "notes": "Book flights and hotel accommodation",
    "color": "#f59e0b",
    "icon": "fa-plane-departure",
    "sort_order": 2,
    "timer_type": "auto_expire",
    "completion_message": "Summit starts now!",
    "is_recurring": false,
    "recurrence_frequency": "daily",
    "window_start_time": "",
    "window_end_time": "",
    "inactive_message": "Counter paused for this period",
    "created_at": "2026-08-25 10:45:00",
    "updated_at": "2026-08-25 10:45:00"
  }
}
```

---

### 4.3 Edit Event Time-Tracker
Modifies any properties of an existing event.

- **Method**: `POST`
- **Endpoint**: `/api/planning/event/edit`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "event_id": 15,
  "title": "Annual Company Summit (Updated)",
  "color": "#ec4899",
  "notes": "Hotel booked. Prepare slide deck."
}
```

#### Response (`200 OK`):
```json
{
  "success": true,
  "message": "Event updated successfully",
  "event": {
    "id": 15,
    "title": "Annual Company Summit (Updated)",
    "target_datetime": "2026-11-15T09:00:00",
    "color": "#ec4899",
    "notes": "Hotel booked. Prepare slide deck.",
    "updated_at": "2026-08-25 11:00:00"
  }
}
```

---

### 4.4 Delete Event Time-Tracker
Deletes a tracked event.

- **Method**: `POST`
- **Endpoint**: `/api/planning/event/delete`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "event_id": 15
}
```

#### Response (`200 OK`):
```json
{
  "success": true,
  "message": "Event deleted successfully"
}
```

---

### 4.5 Reorder Events
Saves a new custom sort order for event time-trackers.

- **Method**: `POST`
- **Endpoint**: `/api/planning/event/reorder`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Request Body:
```json
{
  "event_ids": [14, 12, 15]
}
```

#### Response (`200 OK`):
```json
{
  "success": true
}
```

---

## 5. Tags Management & Task Tagging Integration

Users have dynamic, color-coded tags that categorize both **Planning Backlog Tasks** and **Daily Tasks**.

### 5.1 Fetch User Tags
Retrieves the user's customized tags. If not customized yet, default system tags are returned.

- **Method**: `GET`
- **Endpoint**: `/api/tags`
- **Headers**: `Authorization: Bearer <API_TOKEN>`

#### Response (`200 OK`):
```json
{
  "success": true,
  "tags": [
    { "id": "tag_work", "name": "Work", "color": "#3b82f6" },
    { "id": "tag_personal", "name": "Personal", "color": "#10b981" },
    { "id": "tag_health", "name": "Health", "color": "#ec4899" },
    { "id": "tag_finance", "name": "Finance", "color": "#f59e0b" },
    { "id": "tag_urgent", "name": "Urgent", "color": "#ef4444" }
  ]
}
```

---

### 5.2 Add / Edit / Delete Tags

- **Method**: `POST`
- **Endpoint**: `/api/tags`
- **Headers**:
  - `Authorization: Bearer <API_TOKEN>`
  - `Content-Type: application/json`

#### Action: `add` (Create Tag)
```json
{
  "action": "add",
  "name": "Design",
  "color": "#8b5cf6"
}
```
**Response (`200 OK`)**:
```json
{
  "success": true,
  "tags": [
    { "id": "tag_work", "name": "Work", "color": "#3b82f6" },
    { "id": "tag_1724221500123", "name": "Design", "color": "#8b5cf6" }
  ],
  "tag": {
    "id": "tag_1724221500123",
    "name": "Design",
    "color": "#8b5cf6"
  }
}
```

#### Action: `edit` (Update Tag)
```json
{
  "action": "edit",
  "tag_id": "tag_1724221500123",
  "name": "UI/UX Design",
  "color": "#a855f7"
}
```

#### Action: `delete` (Delete Tag)
```json
{
  "action": "delete",
  "tag_id": "tag_1724221500123"
}
```

---

### 5.3 Assigning and Filtering Tags on Planning Tasks

1. **Tag Storage**: Planning tasks store an array of tag IDs in their `tags` property:
   ```json
   {
     "id": 101,
     "text": "Refactor login modal",
     "tags": ["tag_work", "tag_1724221500123"]
   }
   ```
2. **Frontend Tag Lookup Map**: Cache tags in memory as a map:
   ```typescript
   const tagMap = new Map<string, UserTag>(tags.map(t => [t.id, t]));
   
   function getTagBadge(tagId: string) {
     const tag = tagMap.get(tagId) || { name: tagId, color: '#6b7280' };
     return `<span style="background-color: ${tag.color}20; color: ${tag.color}; border: 1px solid ${tag.color}50;">${tag.name}</span>`;
   }
   ```

---

## 6. Standard Error Responses & HTTP Status Codes

All API endpoints return standard HTTP status codes and JSON payloads:

| HTTP Status | Meaning | Typical Scenario |
| :--- | :--- | :--- |
| `200 OK` | Success | Request succeeded and response payload contains `success: true`. |
| `400 Bad Request` | Missing / Invalid Fields | `text` or `task_id` is missing; invalid timestamp format. |
| `401 Unauthorized` | Authentication Failed | Missing or invalid API token. Redirect user to login. |
| `404 Not Found` | Entity Not Found | `task_id` or `event_id` not found for this user account. |
| `500 Server Error` | Server Exception | Internal server error. |

### Error Payload Format:
```json
{
  "success": false,
  "error": "Unauthorized",
  "message": "Authentication required. Missing or invalid API token."
}
```

---

## 7. Frontend / PWA Integration Client

### Complete TypeScript API Client

Save this as `PlanningApiClient.ts` in your frontend application:

```typescript
/**
 * PlanningApiClient.ts
 * Type-safe, authorized API client for Planning Backlog Tasks, Events & Tags.
 */

export interface UserTag {
  id: string;
  name: string;
  color: string;
}

export interface PlanningTask {
  id: number;
  text: string;
  priority: 'High' | 'Medium' | 'Low';
  tags: string[];
  completed: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface PlanningEvent {
  id: number;
  title: string;
  target_datetime: string;
  target_datetime_display: string;
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

export class PlanningApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = '', token?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.token = token || (typeof window !== 'undefined' ? localStorage.getItem('planner_api_token') : null);
  }

  public setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('planner_api_token', token);
    }
  }

  public clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('planner_api_token');
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {})
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      if (response.status === 401) {
        // Token expired or unauthorized
        throw new Error(data.message || 'Unauthorized: Please check your API token.');
      }
      throw new Error(data.message || `Request failed with status ${response.status}`);
    }

    return data as T;
  }

  // ==========================================
  // PLANNING TASKS
  // ==========================================

  public async getTasks(status: 'all' | 'pending' | 'completed' = 'all') {
    return this.request<{
      success: boolean;
      tasks: PlanningTask[];
      pending_tasks?: PlanningTask[];
      completed_tasks?: PlanningTask[];
      total_pending: number;
      total_completed: number;
      total_tasks: number;
    }>(`/api/planning/tasks?status=${status}`);
  }

  public async getCompletedTasks(offset: number = 10) {
    return this.request<{
      success: boolean;
      tasks: PlanningTask[];
      total_completed: number;
      offset: number;
      page_size: number;
    }>(`/api/planning/completed?offset=${offset}`);
  }

  public async addTask(text: string, priority: 'High' | 'Medium' | 'Low' = 'Medium', tags: string[] = []) {
    return this.request<{ success: boolean; task: PlanningTask }>(
      '/api/planning/task/add',
      {
        method: 'POST',
        body: JSON.stringify({ text, priority, tags })
      }
    );
  }

  public async toggleTask(taskId: number) {
    return this.request<{ success: boolean; completed: boolean }>(
      '/api/planning/task/toggle',
      {
        method: 'POST',
        body: JSON.stringify({ task_id: taskId })
      }
    );
  }

  public async editTask(taskId: number, updates: { text?: string; priority?: 'High' | 'Medium' | 'Low'; tags?: string[] }) {
    return this.request<{ success: boolean; task: PlanningTask }>(
      '/api/planning/task/edit',
      {
        method: 'POST',
        body: JSON.stringify({ task_id: taskId, ...updates })
      }
    );
  }

  public async deleteTask(taskId: number) {
    return this.request<{ success: boolean }>(
      '/api/planning/task/delete',
      {
        method: 'POST',
        body: JSON.stringify({ task_id: taskId })
      }
    );
  }

  public async moveTaskToDaily(taskId: number) {
    return this.request<{ success: boolean; message: string }>(
      '/api/planning/task/move_to_daily',
      {
        method: 'POST',
        body: JSON.stringify({ task_id: taskId })
      }
    );
  }

  public async reorderTasks(taskIds: number[]) {
    return this.request<{ success: boolean }>(
      '/api/planning/task/reorder',
      {
        method: 'POST',
        body: JSON.stringify({ task_ids: taskIds })
      }
    );
  }

  // ==========================================
  // PLANNING EVENTS
  // ==========================================

  public async getEvents() {
    return this.request<{ success: boolean; events: PlanningEvent[] }>(
      '/api/planning/events'
    );
  }

  public async addEvent(eventData: Partial<PlanningEvent> & { title: string }) {
    return this.request<{ success: boolean; event: PlanningEvent; message: string }>(
      '/api/planning/event/add',
      {
        method: 'POST',
        body: JSON.stringify(eventData)
      }
    );
  }

  public async editEvent(eventId: number, eventData: Partial<PlanningEvent>) {
    return this.request<{ success: boolean; event: PlanningEvent; message: string }>(
      '/api/planning/event/edit',
      {
        method: 'POST',
        body: JSON.stringify({ event_id: eventId, ...eventData })
      }
    );
  }

  public async deleteEvent(eventId: number) {
    return this.request<{ success: boolean; message: string }>(
      '/api/planning/event/delete',
      {
        method: 'POST',
        body: JSON.stringify({ event_id: eventId })
      }
    );
  }

  public async reorderEvents(eventIds: number[]) {
    return this.request<{ success: boolean }>(
      '/api/planning/event/reorder',
      {
        method: 'POST',
        body: JSON.stringify({ event_ids: eventIds })
      }
    );
  }

  // ==========================================
  // TAGS MANAGEMENT
  // ==========================================

  public async getTags() {
    return this.request<{ success: boolean; tags: UserTag[] }>('/api/tags');
  }

  public async addTag(name: string, color: string) {
    return this.request<{ success: boolean; tags: UserTag[]; tag: UserTag }>(
      '/api/tags',
      {
        method: 'POST',
        body: JSON.stringify({ action: 'add', name, color })
      }
    );
  }

  public async editTag(tagId: string, name: string, color: string) {
    return this.request<{ success: boolean; tags: UserTag[] }>(
      '/api/tags',
      {
        method: 'POST',
        body: JSON.stringify({ action: 'edit', tag_id: tagId, name, color })
      }
    );
  }

  public async deleteTag(tagId: string) {
    return this.request<{ success: boolean; tags: UserTag[] }>(
      '/api/tags',
      {
        method: 'POST',
        body: JSON.stringify({ action: 'delete', tag_id: tagId })
      }
    );
  }
}
```

---

### React Hook Integration Example

```typescript
// usePlanning.ts
import { useState, useEffect, useCallback } from 'react';
import { PlanningApiClient, PlanningTask, PlanningEvent, UserTag } from './PlanningApiClient';

const api = new PlanningApiClient();

export function usePlanning() {
  const [tasks, setTasks] = useState<PlanningTask[]>([]);
  const [events, setEvents] = useState<PlanningEvent[]>([]);
  const [tags, setTags] = useState<UserTag[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [tasksRes, eventsRes, tagsRes] = await Promise.all([
        api.getTasks('all'),
        api.getEvents(),
        api.getTags()
      ]);
      setTasks(tasksRes.tasks || []);
      setEvents(eventsRes.events || []);
      setTags(tagsRes.tags || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load planning data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const addTask = async (text: string, priority: 'High' | 'Medium' | 'Low' = 'Medium', tagIds: string[] = []) => {
    const res = await api.addTask(text, priority, tagIds);
    if (res.success) {
      setTasks(prev => [res.task, ...prev]);
    }
  };

  const toggleTask = async (taskId: number) => {
    const res = await api.toggleTask(taskId);
    if (res.success) {
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, completed: res.completed } : t));
    }
  };

  const deleteTask = async (taskId: number) => {
    const res = await api.deleteTask(taskId);
    if (res.success) {
      setTasks(prev => prev.filter(t => t.id !== taskId));
    }
  };

  const moveToDaily = async (taskId: number) => {
    const res = await api.moveTaskToDaily(taskId);
    if (res.success) {
      setTasks(prev => prev.filter(t => t.id !== taskId));
    }
  };

  return {
    tasks,
    events,
    tags,
    loading,
    error,
    refresh: loadData,
    addTask,
    toggleTask,
    deleteTask,
    moveToDaily
  };
}
```

---

## 8. cURL Quick Reference

Replace `YOUR_API_TOKEN` with your actual token:

### 1. Fetch All Planning Backlog Tasks
```bash
curl -X GET "http://localhost:5000/api/planning/tasks" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Accept: application/json"
```

### 2. Create a Backlog Task with Tags
```bash
curl -X POST "http://localhost:5000/api/planning/task/add" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Setup WebSocket live countdown listener",
    "priority": "High",
    "tags": ["tag_work", "tag_urgent"]
  }'
```

### 3. Toggle Task Status
```bash
curl -X POST "http://localhost:5000/api/planning/task/toggle" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_id": 101}'
```

### 4. Move Task to Today's Daily Checklist
```bash
curl -X POST "http://localhost:5000/api/planning/task/move_to_daily" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_id": 101}'
```

### 5. Fetch Planning Event Time-Trackers
```bash
curl -X GET "http://localhost:5000/api/planning/events" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### 6. Create Recurring Event Time-Tracker
```bash
curl -X POST "http://localhost:5000/api/planning/event/add" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Focused Work Hours",
    "timer_type": "recurring",
    "is_recurring": true,
    "recurrence_frequency": "daily",
    "window_start_time": "09:30",
    "window_end_time": "17:30",
    "color": "#3b82f6",
    "icon": "fa-briefcase"
  }'
```

### 7. Manage Tags (Add New Tag)
```bash
curl -X POST "http://localhost:5000/api/tags" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "add",
    "name": "Design System",
    "color": "#8b5cf6"
  }'
```
