# Daily Task API Documentation (PWA Reference)

Comprehensive API reference and frontend integration guide for building Progressive Web Apps (PWAs) and client applications using **API Token Authentication** to manage **Daily Tasks**.

> **Scope**: This document covers **Auth Tokens** and **Daily Tasks** (Fetch, Add, Edit, Toggle Status, Delete, Duplicate, Reorder) exclusively.

---

## Table of Contents

1. [Authentication & Token Management](#1-authentication--token-management)
   - [Authentication Headers](#authentication-headers)
   - [Token Generation & Management Endpoints](#token-generation--management-endpoints)
2. [Task Data Model & Types](#2-task-data-model--types)
3. [Daily Task Endpoints](#3-daily-task-endpoints)
   - [3.1 Fetch Daily Plan & Tasks (`GET /api/daily`)](#31-fetch-daily-plan--tasks)
   - [3.2 Add Task (`POST /api/daily/task/add`)](#32-add-task)
   - [3.3 Edit Task (`POST /api/daily/task/edit`)](#33-edit-task)
   - [3.4 Toggle Task Status (`POST /api/daily/task/toggle`)](#34-toggle-task-status)
   - [3.5 Delete Task (`POST /api/daily/task/delete`)](#35-delete-task)
   - [3.6 Duplicate Task (`POST /api/daily/task/duplicate`)](#36-duplicate-task)
   - [3.7 Reorder Tasks (`POST /api/daily/task/reorder`)](#37-reorder-tasks)
4. [Standard Error Responses & Status Codes](#4-standard-error-responses--status-codes)
5. [Frontend / PWA Integration Reference](#5-frontend--pwa-integration-reference)
   - [PWA Token Storage & API Client Module](#pwa-token-storage--api-client-module)
   - [Complete JavaScript / TypeScript Service](#complete-javascript--typescript-service)
6. [cURL Quick Testing Reference](#6-curl-quick-testing-reference)

---

## 1. Authentication & Token Management

All task API endpoints require token authentication. Once generated, tokens are prefixed with `cp_` (e.g., `cp_9a8b7c6d5e4f...`).

### Authentication Headers

You can supply the token in any of the following supported ways (listed by priority):

| Method | Header / Parameter | Format |
| :--- | :--- | :--- |
| **HTTP Authorization Header** *(Recommended)* | `Authorization` | `Bearer <YOUR_API_TOKEN>` or `Token <YOUR_API_TOKEN>` |
| **Custom Header** | `X-API-Token` | `<YOUR_API_TOKEN>` |
| **URL Query Parameter** | `api_token` / `token` | `?api_token=<YOUR_API_TOKEN>` |
| **JSON Request Body** | `api_token` | `{"api_token": "<YOUR_API_TOKEN>", ...}` |

---

### Token Generation & Management Endpoints

#### 1. Generate New API Token
Generates or rotates a permanent API token for the user.

- **Method**: `POST`
- **Endpoint**: `/auth/generate-api-token`
- **Authentication**: Active web session or existing token
- **Response (`200 OK`)**:
```json
{
  "success": true,
  "message": "New API token generated successfully!",
  "api_token": "cp_a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
  "masked_token": "cp_a1b2...8f90",
  "created_at": "2026-08-24 08:30:00 UTC"
}
```

#### 2. Get API Token Info
Checks if the current user has an active token and retrieves metadata.

- **Method**: `GET`
- **Endpoint**: `/auth/api-token-info`
- **Headers**: `Authorization: Bearer <YOUR_API_TOKEN>`
- **Response (`200 OK`)**:
```json
{
  "success": true,
  "has_token": true,
  "masked_token": "cp_a1b2...8f90",
  "created_at": "2026-08-24 08:30:00 UTC"
}
```

#### 3. Revoke API Token
Invalidates the current API token immediately.

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

## 2. Task Data Model & Types

### TypeScript Interface

```typescript
export type TaskPriority = 'High' | 'Medium' | 'Low';
export type TaskStatus = 'To Do' | 'In Progress' | 'Completed' | 'Undone';

export interface DailyTask {
  id: string;              // Unique millisecond timestamp string e.g. "1724222849102"
  text: string;            // Task title / description
  priority: TaskPriority;  // "High" | "Medium" | "Low" (Default: "Medium")
  tags: string[];          // List of category/context tags e.g. ["Work", "Urgent"]
  status: TaskStatus;      // "To Do" | "In Progress" | "Completed" | "Undone"
  completed: boolean;      // True if finished, False otherwise
  note: string;            // Optional extra notes / instructions
  is_default: boolean;     // If true, automatically carries over to all subsequent days
  is_spillover: boolean;   // True if task was rolled over automatically from a previous day
  spillover_count: number; // Number of times this task has rolled over
  original_date: string;   // Date the task was initially created ("YYYY-MM-DD")
}

export interface DailyTaskSummary {
  total_tasks: number;
  completed_tasks: number;
  pending_tasks: number;
  completion_pct: number;  // 0 to 100
}
```

---

## 3. Daily Task Endpoints

### Base URL
- **Development**: `http://localhost:5000`
- **Production**: `https://<YOUR_DEPLOYED_DOMAIN>`

---

### 3.1 Fetch Daily Plan & Tasks

Retrieves all tasks and summary statistics for a given date.

- **Method**: `GET`
- **Endpoint**: `/api/daily` or `/api/daily/today`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Accept: application/json`
- **Query Parameters**:
  - `date` *(optional, string, format: `YYYY-MM-DD`)*: Target date. Defaults to current date if omitted or set to `'today'`.

#### Request
```http
GET /api/daily?date=2026-08-24 HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Accept: application/json
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "date": "2026-08-24",
  "is_today": true,
  "summary": {
    "total_tasks": 2,
    "completed_tasks": 1,
    "pending_tasks": 1,
    "completion_pct": 50
  },
  "tasks": [
    {
      "id": "1724482800101",
      "text": "Review pull requests and deploy PWA update",
      "priority": "High",
      "tags": ["Dev", "Release"],
      "status": "To Do",
      "completed": false,
      "note": "Verify offline service worker cache",
      "is_default": false,
      "is_spillover": false,
      "spillover_count": 0,
      "original_date": "2026-08-24"
    },
    {
      "id": "1724482800102",
      "text": "Daily morning standup meeting",
      "priority": "Medium",
      "tags": ["Meeting"],
      "status": "Completed",
      "completed": true,
      "note": "",
      "is_default": true,
      "is_spillover": false,
      "spillover_count": 0,
      "original_date": "2026-08-24"
    }
  ]
}
```

---

### 3.2 Add Task

Creates a new task in the daily planner for a specific date.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/add`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- **Request Body Fields**:

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `date` | `string` | **Yes** | — | Target date (`YYYY-MM-DD`) |
| `text` | `string` | **Yes** | — | Task title or description |
| `priority` | `string` | No | `"Medium"` | `"High"`, `"Medium"`, or `"Low"` |
| `tags` | `string[]` | No | `[]` | Array of tag strings e.g. `["PWA", "Feature"]` |
| `status` | `string` | No | `"To Do"` | `"To Do"`, `"In Progress"`, `"Completed"`, or `"Undone"` |
| `note` | `string` | No | `""` | Additional notes or sub-details |
| `is_default`| `boolean` | No | `false` | If `true`, recurs every day automatically |

#### Request Example
```http
POST /api/daily/task/add HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Content-Type: application/json

{
  "date": "2026-08-24",
  "text": "Implement offline IndexedDB sync",
  "priority": "High",
  "tags": ["PWA", "Sync"],
  "status": "To Do",
  "note": "Use Background Sync API if supported",
  "is_default": false
}
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "task": {
    "id": "1724483940123",
    "text": "Implement offline IndexedDB sync",
    "priority": "High",
    "tags": ["PWA", "Sync"],
    "status": "To Do",
    "completed": false,
    "note": "Use Background Sync API if supported",
    "is_default": false,
    "is_spillover": false,
    "spillover_count": 0,
    "original_date": "2026-08-24"
  }
}
```

---

### 3.3 Edit Task

Updates any attribute of an existing daily task.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/edit`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- **Request Body Fields**:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `date` | `string` | **Yes** | Date of the plan (`YYYY-MM-DD`) |
| `task_id` | `string` | **Yes** | ID of the task to modify |
| `text` | `string` | No | Updated task title |
| `priority` | `string` | No | `"High"`, `"Medium"`, or `"Low"` |
| `status` | `string` | No | `"To Do"`, `"In Progress"`, `"Completed"`, or `"Undone"` *(Automatically sets `completed: true` if status is "Completed")* |
| `tags` | `string[]` | No | Updated tag array |
| `note` | `string` | No | Updated notes text |
| `is_default`| `boolean` | No | Enable/disable auto-daily recurrence |

#### Request Example
```http
POST /api/daily/task/edit HTTP/1.1
Host: localhost:5000
Authorization: Bearer cp_your_token_here
Content-Type: application/json

{
  "date": "2026-08-24",
  "task_id": "1724483940123",
  "text": "Implement offline IndexedDB sync (Tested & verified)",
  "priority": "High",
  "status": "Completed",
  "tags": ["PWA", "Sync", "Completed"],
  "note": "Works across Chrome, Edge, and iOS Safari"
}
```

#### Response (`200 OK`)
```json
{
  "success": true
}
```

---

### 3.4 Toggle Task Status

Quickly toggles task completion state between completed (`true`) and incomplete (`false`).

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/toggle`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- **Request Body**:
```json
{
  "date": "2026-08-24",
  "task_id": "1724483940123"
}
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "completed": true
}
```

---

### 3.5 Delete Task

Permanently deletes a task from a specific day's plan.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/delete`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- **Request Body**:
```json
{
  "date": "2026-08-24",
  "task_id": "1724483940123"
}
```

#### Response (`200 OK`)
```json
{
  "success": true
}
```

---

### 3.6 Duplicate Task

Clones an existing task with a new ID on the same date with `completed: false` and `status: "To Do"`.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/duplicate`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- **Request Body**:
```json
{
  "date": "2026-08-24",
  "task_id": "1724483940123"
}
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "task": {
    "id": "1724484120999",
    "text": "Implement offline IndexedDB sync",
    "priority": "High",
    "tags": ["PWA", "Sync"],
    "status": "To Do",
    "completed": false,
    "note": "Use Background Sync API if supported",
    "is_default": false,
    "is_spillover": false,
    "spillover_count": 0,
    "original_date": "2026-08-24"
  }
}
```

---

### 3.7 Reorder Tasks

Saves a custom drag-and-drop ordering for tasks on a given date.

- **Method**: `POST`
- **Endpoint**: `/api/daily/task/reorder`
- **Headers**:
  - `Authorization: Bearer <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- **Request Body**:
```json
{
  "date": "2026-08-24",
  "task_ids": [
    "1724483940123",
    "1724482800101",
    "1724482800102"
  ]
}
```

#### Response (`200 OK`)
```json
{
  "success": true
}
```

---

## 4. Standard Error Responses & Status Codes

| HTTP Status | Meaning | Typical JSON Body |
| :--- | :--- | :--- |
| `200 OK` | Success | `{"success": true, ...}` |
| `400 Bad Request` | Missing required parameters or invalid date format | `{"success": false, "message": "Task text is required"}` |
| `401 Unauthorized` | Missing or invalid API token | `{"error": "Unauthorized", "message": "Invalid API token provided."}` |
| `404 Not Found` | Plan or task ID not found for given date | `{"success": false, "message": "Task not found"}` |

---

## 5. Frontend / PWA Integration Reference

### PWA Token Storage & API Client Module

Below is a complete, production-ready JavaScript/TypeScript client service for your PWA.

```javascript
// taskApiService.js

export class TaskApiService {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  /**
   * Retrieve the stored API token from localStorage
   */
  getToken() {
    return localStorage.getItem('planner_api_token') || '';
  }

  /**
   * Save API token to localStorage
   */
  setToken(token) {
    if (token) {
      localStorage.setItem('planner_api_token', token.trim());
    } else {
      localStorage.removeItem('planner_api_token');
    }
  }

  /**
   * Helper to execute authenticated JSON HTTP requests
   */
  async request(endpoint, options = {}) {
    const token = this.getToken();
    if (!token) {
      throw new Error('AUTH_REQUIRED: No API token configured');
    }

    const headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options.headers || {})
    };

    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers
    });

    if (response.status === 401) {
      throw new Error('UNAUTHORIZED: Invalid or expired API token');
    }

    const data = await response.json();
    if (!response.ok || data.success === false) {
      throw new Error(data.message || data.error || `HTTP ${response.status}`);
    }

    return data;
  }

  // ==========================================
  // TOKEN ENDPOINTS
  // ==========================================

  /**
   * Check token info
   */
  async getApiTokenInfo() {
    return this.request('/auth/api-token-info', { method: 'GET' });
  }

  /**
   * Revoke active token
   */
  async revokeApiToken() {
    return this.request('/auth/revoke-api-token', { method: 'POST' });
  }

  // ==========================================
  // DAILY TASK ENDPOINTS
  // ==========================================

  /**
   * Fetch daily tasks for a given date (YYYY-MM-DD)
   */
  async getDailyTasks(dateStr) {
    const query = dateStr ? `?date=${encodeURIComponent(dateStr)}` : '';
    return this.request(`/api/daily${query}`, { method: 'GET' });
  }

  /**
   * Add a new daily task
   */
  async addTask({ date, text, priority = 'Medium', tags = [], status = 'To Do', note = '', is_default = false }) {
    return this.request('/api/daily/task/add', {
      method: 'POST',
      body: JSON.stringify({
        date,
        text,
        priority,
        tags,
        status,
        note,
        is_default
      })
    });
  }

  /**
   * Edit an existing task
   */
  async editTask(date, taskId, updates = {}) {
    return this.request('/api/daily/task/edit', {
      method: 'POST',
      body: JSON.stringify({
        date,
        task_id: taskId,
        ...updates
      })
    });
  }

  /**
   * Toggle task completion
   */
  async toggleTask(date, taskId) {
    return this.request('/api/daily/task/toggle', {
      method: 'POST',
      body: JSON.stringify({
        date,
        task_id: taskId
      })
    });
  }

  /**
   * Delete a task
   */
  async deleteTask(date, taskId) {
    return this.request('/api/daily/task/delete', {
      method: 'POST',
      body: JSON.stringify({
        date,
        task_id: taskId
      })
    });
  }

  /**
   * Duplicate a task
   */
  async duplicateTask(date, taskId) {
    return this.request('/api/daily/task/duplicate', {
      method: 'POST',
      body: JSON.stringify({
        date,
        task_id: taskId
      })
    });
  }

  /**
   * Reorder tasks
   */
  async reorderTasks(date, taskIdsArray) {
    return this.request('/api/daily/task/reorder', {
      method: 'POST',
      body: JSON.stringify({
        date,
        task_ids: taskIdsArray
      })
    });
  }
}

// Export singleton instance
export const taskApi = new TaskApiService();
```

---

### PWA UI Usage Example

```javascript
import { taskApi } from './taskApiService.js';

// Set token initially (e.g. from user input in Settings modal)
taskApi.setToken('cp_your_token_value_here');

const today = new Date().toISOString().split('T')[0];

async function loadAndDisplayTasks() {
  try {
    const res = await taskApi.getDailyTasks(today);
    console.log('Total tasks:', res.summary.total_tasks);
    console.log('Tasks list:', res.tasks);

    // 1. Add Task
    const addRes = await taskApi.addTask({
      date: today,
      text: 'Build PWA service worker',
      priority: 'High',
      tags: ['Frontend', 'PWA']
    });
    console.log('Created task ID:', addRes.task.id);

    // 2. Toggle Task
    await taskApi.toggleTask(today, addRes.task.id);

    // 3. Edit Task
    await taskApi.editTask(today, addRes.task.id, {
      priority: 'Medium',
      note: 'Implemented with Stale-While-Revalidate'
    });

  } catch (err) {
    if (err.message.includes('UNAUTHORIZED') || err.message.includes('AUTH_REQUIRED')) {
      alert('Please configure your API token in Settings.');
    } else {
      console.error('API Error:', err);
    }
  }
}
```

---

## 6. cURL Quick Testing Reference

Replace `YOUR_API_TOKEN` and `http://localhost:5000` with your credentials and server URL.

#### 1. Fetch Today's Tasks
```bash
curl -X GET "http://localhost:5000/api/daily?date=2026-08-24" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Accept: application/json"
```

#### 2. Add New Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/add" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "text": "Setup PWA Manifest and Icons",
    "priority": "High",
    "tags": ["PWA", "UI"],
    "status": "To Do"
  }'
```

#### 3. Toggle Task Completion
```bash
curl -X POST "http://localhost:5000/api/daily/task/toggle" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "task_id": "1724483940123"
  }'
```

#### 4. Edit Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/edit" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "task_id": "1724483940123",
    "text": "Setup PWA Manifest and 512px Icons",
    "priority": "High",
    "status": "In Progress"
  }'
```

#### 5. Reorder Tasks
```bash
curl -X POST "http://localhost:5000/api/daily/task/reorder" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "task_ids": ["1724483940123", "1724482800101"]
  }'
```

#### 6. Duplicate Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/duplicate" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "task_id": "1724483940123"
  }'
```

#### 7. Delete Task
```bash
curl -X POST "http://localhost:5000/api/daily/task/delete" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "task_id": "1724483940123"
  }'
```
