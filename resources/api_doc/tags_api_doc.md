# Tags Management REST API Documentation

This document provides a comprehensive API reference, authentication specifications, request/response schemas, error handling guidelines, and ready-to-use code examples (cURL, Python, JavaScript/TypeScript) for managing custom tags and associating tags with tasks in the Planner App.

---

## Table of Contents
1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Base URL & Common Headers](#3-base-url--common-headers)
4. [Tag Data Model & Default System Tags](#4-tag-data-model--default-system-tags)
5. [API Endpoints Reference](#5-api-endpoints-reference)
   - [5.1 List All Tags (`GET /api/tags`)](#51-list-all-tags-get-apitags)
   - [5.2 Create New Tag (`POST /api/tags` - action: `add`)](#52-create-new-tag-post-apitags---action-add)
   - [5.3 Edit Existing Tag (`POST /api/tags` - action: `edit`)](#53-edit-existing-tag-post-apitags---action-edit)
   - [5.4 Delete Tag (`POST /api/tags` - action: `delete`)](#54-delete-tag-post-apitags---action-delete)
6. [Task Tagging Integration](#6-task-tagging-integration)
   - [6.1 Assigning Tags on Daily Task Creation](#61-assigning-tags-on-daily-task-creation)
   - [6.2 Updating Tags on an Existing Task](#62-updating-tags-on-an-existing-task)
   - [6.3 Tagging Planning Tasks](#63-tagging-planning-tasks)
7. [Cloud Backup & Sync](#7-cloud-backup--sync)
8. [Error Handling & Status Codes](#8-error-handling--status-codes)
9. [Comprehensive Code Examples](#9-comprehensive-code-examples)
   - [Python (`requests`)](#python-requests)
   - [JavaScript / TypeScript (`fetch`)](#javascript--typescript-fetch)
   - [Node.js (`axios`)](#nodejs-axios)
   - [cURL](#curl)

---

## 1. Overview

The **Tags Management API** allows users to create, view, update, and delete personalized, color-coded tags. These tags categorize and filter tasks across the Daily Planner, Weekly/Monthly Planner, and Strategic Planning boards.

### Key Capabilities
- **Color-Coded Customization**: Customize tag hex color codes (e.g. `#3b82f6`, `#10b981`, `#ec4899`).
- **Dynamic Identification**: Auto-generated unique IDs (`tag_<timestamp>`) or standard slug IDs (`tag_work`, `tag_personal`).
- **Persistent User State**: Stored securely in the user's profile and synchronized across devices and Google Drive backups.
- **Full Task Association**: Tasks store tag ID arrays in their `tags` property.

---

## 2. Authentication

All Tag API endpoints require authentication via an **API Token** or an active session cookie.

You can supply the API token through any of the following methods:

| Method | Syntax | Example |
| :--- | :--- | :--- |
| **Authorization Header** (Recommended) | `Authorization: Bearer <API_TOKEN>` | `Authorization: Bearer cp_3f8a9e2d...` |
| **Custom Header** | `X-API-Token: <API_TOKEN>` | `X-API-Token: cp_3f8a9e2d...` |
| **Query Parameter** | `?api_token=<API_TOKEN>` | `https://api.yourdomain.com/api/tags?api_token=cp_3f8a9e2d...` |

> [!TIP]
> Generate or regenerate your API token from the web app under **Account Settings > API Access** or programmatically via the `/auth/generate-api-token` endpoint.

---

## 3. Base URL & Common Headers

- **Local Development**: `http://localhost:5000`
- **Production Server**: `https://<YOUR_DEPLOYED_DOMAIN>`

### Standard Request Headers
```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer YOUR_API_TOKEN
```

---

## 4. Tag Data Model & Default System Tags

### Tag Object Schema

| Field | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `id` | `string` | Unique identifier of the tag | `"tag_1724221500123"` or `"tag_work"` |
| `name` | `string` | Display name for the tag | `"Engineering"` |
| `color` | `string` | Hex color code used for badges and UI borders | `"#3b82f6"` |

### Default System Tags
When a new user has not yet customized their tags, the system provides 5 default tags:

```json
[
  { "id": "tag_work", "name": "Work", "color": "#3b82f6" },
  { "id": "tag_personal", "name": "Personal", "color": "#10b981" },
  { "id": "tag_health", "name": "Health", "color": "#ec4899" },
  { "id": "tag_finance", "name": "Finance", "color": "#f59e0b" },
  { "id": "tag_urgent", "name": "Urgent", "color": "#ef4444" }
]
```

---

## 5. API Endpoints Reference

### 5.1 List All Tags (GET `/api/tags`)

Fetch all active tags for the authenticated user. If the user has not configured custom tags, the default system tags are returned.

- **Method**: `GET`
- **Endpoint**: `/api/tags`
- **Authentication**: Required (`Bearer Token`)

#### Request Example
```http
GET /api/tags HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Accept: application/json
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "tags": [
    {
      "id": "tag_work",
      "name": "Work",
      "color": "#3b82f6"
    },
    {
      "id": "tag_personal",
      "name": "Personal",
      "color": "#10b981"
    },
    {
      "id": "tag_health",
      "name": "Health",
      "color": "#ec4899"
    },
    {
      "id": "tag_finance",
      "name": "Finance",
      "color": "#f59e0b"
    },
    {
      "id": "tag_urgent",
      "name": "Urgent",
      "color": "#ef4444"
    },
    {
      "id": "tag_1724221500123",
      "name": "Engineering",
      "color": "#8b5cf6"
    }
  ]
}
```

---

### 5.2 Create New Tag (`POST /api/tags` - action: `add`)

Creates a new custom tag for the user. A unique timestamp ID (`tag_<timestamp_ms>`) is generated automatically.

- **Method**: `POST`
- **Endpoint**: `/api/tags`
- **Content-Type**: `application/json`

#### Request Body Parameters

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `action` | `string` | No | `"add"` | Must be set to `"add"` (or omitted, defaults to `"add"`) |
| `name` | `string` | **Yes** | — | Display label of the tag (e.g. `"Design"`, `"Bugfix"`) |
| `color` | `string` | No | `"#3b82f6"` | Valid Hex color code (e.g. `"#8b5cf6"`, `"#f97316"`) |

#### Request Example
```http
POST /api/tags HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "action": "add",
  "name": "DevOps & Cloud",
  "color": "#06b6d4"
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "tag": {
    "id": "tag_1724478475000",
    "name": "DevOps & Cloud",
    "color": "#06b6d4"
  },
  "tags": [
    { "id": "tag_work", "name": "Work", "color": "#3b82f6" },
    { "id": "tag_personal", "name": "Personal", "color": "#10b981" },
    { "id": "tag_health", "name": "Health", "color": "#ec4899" },
    { "id": "tag_finance", "name": "Finance", "color": "#f59e0b" },
    { "id": "tag_urgent", "name": "Urgent", "color": "#ef4444" },
    { "id": "tag_1724478475000", "name": "DevOps & Cloud", "color": "#06b6d4" }
  ]
}
```

#### Error Response Example (`400 Bad Request` - Missing Name)
```json
{
  "success": false,
  "message": "Tag name is required"
}
```

---

### 5.3 Edit Existing Tag (`POST /api/tags` - action: `edit`)

Updates the display name or color of an existing tag identified by its `tag_id`.

- **Method**: `POST`
- **Endpoint**: `/api/tags`
- **Content-Type**: `application/json`

#### Request Body Parameters

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `action` | `string` | **Yes** | Must be `"edit"` |
| `tag_id` | `string` | **Yes** | Target tag identifier (e.g. `"tag_1724478475000"` or `"tag_work"`) |
| `name` | `string` | No | New label for the tag |
| `color` | `string` | No | New hex color code |

#### Request Example
```http
POST /api/tags HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "action": "edit",
  "tag_id": "tag_1724478475000",
  "name": "Infrastructure & Cloud",
  "color": "#0891b2"
}
```

#### Response Example (`200 OK`)
```json
{
  "success": true,
  "tags": [
    { "id": "tag_work", "name": "Work", "color": "#3b82f6" },
    { "id": "tag_personal", "name": "Personal", "color": "#10b981" },
    { "id": "tag_health", "name": "Health", "color": "#ec4899" },
    { "id": "tag_finance", "name": "Finance", "color": "#f59e0b" },
    { "id": "tag_urgent", "name": "Urgent", "color": "#ef4444" },
    { "id": "tag_1724478475000", "name": "Infrastructure & Cloud", "color": "#0891b2" }
  ]
}
```

---

### 5.4 Delete Tag (`POST /api/tags` - action: `delete`)

Removes a tag from the user's custom tags list.

- **Method**: `POST`
- **Endpoint**: `/api/tags`
- **Content-Type**: `application/json`

#### Request Body Parameters

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `action` | `string` | **Yes** | Must be `"delete"` |
| `tag_id` | `string` | **Yes** | The identifier of the tag to delete |

#### Request Example
```http
POST /api/tags HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "action": "delete",
  "tag_id": "tag_1724478475000"
}
```

#### Response Example (`200 OK`)
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

## 6. Task Tagging Integration

Tags are assigned to tasks across the system using array of tag IDs in the task's `tags` field.

### 6.1 Assigning Tags on Daily Task Creation

When creating a daily task via `POST /api/daily/task/add`, include the tag IDs:

```http
POST /api/daily/task/add HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "date": "2026-08-24",
  "text": "Setup CI/CD deployment pipeline",
  "priority": "High",
  "tags": ["tag_work", "tag_1724478475000"],
  "status": "To Do"
}
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "task": {
    "id": "1724478800123",
    "text": "Setup CI/CD deployment pipeline",
    "priority": "High",
    "tags": ["tag_work", "tag_1724478475000"],
    "status": "To Do",
    "completed": false,
    "note": "",
    "is_default": false,
    "is_spillover": false,
    "spillover_count": 0,
    "original_date": "2026-08-24"
  }
}
```

### 6.2 Updating Tags on an Existing Task

Update tags on an existing task via `POST /api/daily/task/edit`:

```http
POST /api/daily/task/edit HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "date": "2026-08-24",
  "task_id": "1724478800123",
  "tags": ["tag_urgent", "tag_1724478475000"]
}
```

### 6.3 Tagging Planning Tasks

For longer-term planning tasks (Quarterly/Yearly/Sprint planning), use `POST /api/planning/tasks`:

```http
POST /api/planning/tasks HTTP/1.1
Host: localhost:5000
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json

{
  "text": "Migrate database to PostgreSQL 16",
  "priority": "High",
  "category": "Infrastructure",
  "tags": ["tag_work"]
}
```

---

## 7. Cloud Backup & Sync

User custom tags are automatically backed up to Google Drive when cloud backup is enabled.

- **Sync Endpoint**: `POST /api/google/drive/sync`
- **Data Payload**: The backup archive includes `user.custom_tags`, restoring all tag names, colors, and identifiers across instances.

---

## 8. Error Handling & Status Codes

| HTTP Status | Meaning | Typical Scenario |
| :--- | :--- | :--- |
| `200 OK` | Success | Tag successfully retrieved, created, edited, or deleted. |
| `400 Bad Request` | Invalid Request | Missing tag name on `add`, invalid `action` parameter, or malformed JSON. |
| `401 Unauthorized` | Missing / Invalid Token | API token is missing, expired, or invalid. |
| `500 Internal Server Error` | Server Failure | Unexpected database error while saving tag changes. |

### Error Response Format
```json
{
  "success": false,
  "message": "Descriptive error message"
}
```

---

## 9. Comprehensive Code Examples

### Python (`requests`)

```python
import requests

BASE_URL = "http://localhost:5000"
API_TOKEN = "cp_your_api_token_here"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Fetch all tags
def list_tags():
    resp = requests.get(f"{BASE_URL}/api/tags", headers=headers)
    resp.raise_for_status()
    tags = resp.json().get("tags", [])
    print("User Tags:", tags)
    return tags

# 2. Create a new tag
def add_tag(name, color="#3b82f6"):
    payload = {
        "action": "add",
        "name": name,
        "color": color
    }
    resp = requests.post(f"{BASE_URL}/api/tags", json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    print("Created Tag:", data.get("tag"))
    return data.get("tag")

# 3. Edit an existing tag
def edit_tag(tag_id, name=None, color=None):
    payload = {"action": "edit", "tag_id": tag_id}
    if name:
        payload["name"] = name
    if color:
        payload["color"] = color
        
    resp = requests.post(f"{BASE_URL}/api/tags", json=payload, headers=headers)
    resp.raise_for_status()
    print("Updated Tags List:", resp.json().get("tags"))

# 4. Delete a tag
def delete_tag(tag_id):
    payload = {"action": "delete", "tag_id": tag_id}
    resp = requests.post(f"{BASE_URL}/api/tags", json=payload, headers=headers)
    resp.raise_for_status()
    print("Remaining Tags:", resp.json().get("tags"))

# 5. Create a daily task with tags
def create_task_with_tags(date_str, text, tag_ids):
    payload = {
        "date": date_str,
        "text": text,
        "priority": "High",
        "tags": tag_ids,
        "status": "To Do"
    }
    resp = requests.post(f"{BASE_URL}/api/daily/task/add", json=payload, headers=headers)
    resp.raise_for_status()
    print("Created Task with Tags:", resp.json().get("task"))

if __name__ == "__main__":
    # Example flow
    new_tag = add_tag("Product Design", "#a855f7")
    if new_tag:
        edit_tag(new_tag["id"], name="UI/UX Product Design", color="#9333ea")
        create_task_with_tags("2026-08-24", "Design Figma prototypes", [new_tag["id"], "tag_work"])
        # delete_tag(new_tag["id"])
```

---

### JavaScript / TypeScript (`fetch`)

```typescript
const BASE_URL = 'http://localhost:5000';
const API_TOKEN = 'cp_your_api_token_here';

interface Tag {
  id: string;
  name: string;
  color: string;
}

const authHeaders = {
  'Authorization': `Bearer ${API_TOKEN}`,
  'Content-Type': 'application/json'
};

// 1. Get all tags
async function fetchTags(): Promise<Tag[]> {
  const res = await fetch(`${BASE_URL}/api/tags`, {
    method: 'GET',
    headers: authHeaders
  });
  const data = await res.json();
  if (!data.success) throw new Error(data.message || 'Failed to fetch tags');
  return data.tags;
}

// 2. Add a new tag
async function createTag(name: string, color: string = '#3b82f6'): Promise<Tag> {
  const res = await fetch(`${BASE_URL}/api/tags`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({
      action: 'add',
      name,
      color
    })
  });
  const data = await res.json();
  if (!data.success) throw new Error(data.message || 'Failed to create tag');
  return data.tag;
}

// 3. Edit tag
async function updateTag(tagId: string, name?: string, color?: string): Promise<Tag[]> {
  const res = await fetch(`${BASE_URL}/api/tags`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({
      action: 'edit',
      tag_id: tagId,
      name,
      color
    })
  });
  const data = await res.json();
  if (!data.success) throw new Error(data.message || 'Failed to edit tag');
  return data.tags;
}

// 4. Delete tag
async function deleteTag(tagId: string): Promise<Tag[]> {
  const res = await fetch(`${BASE_URL}/api/tags`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({
      action: 'delete',
      tag_id: tagId
    })
  });
  const data = await res.json();
  if (!data.success) throw new Error(data.message || 'Failed to delete tag');
  return data.tags;
}
```

---

### Node.js (`axios`)

```javascript
const axios = require('axios');

const apiClient = axios.create({
  baseURL: 'http://localhost:5000',
  headers: {
    'Authorization': 'Bearer cp_your_api_token_here',
    'Content-Type': 'application/json'
  }
});

async function runTagWorkflow() {
  try {
    // 1. Get current tags
    const getRes = await apiClient.get('/api/tags');
    console.log('Current tags count:', getRes.data.tags.length);

    // 2. Add new tag
    const addRes = await apiClient.post('/api/tags', {
      action: 'add',
      name: 'Security Audit',
      color: '#ef4444'
    });
    const createdTag = addRes.data.tag;
    console.log('Created tag:', createdTag);

    // 3. Edit tag
    const editRes = await apiClient.post('/api/tags', {
      action: 'edit',
      tag_id: createdTag.id,
      name: 'SecOps & Compliance',
      color: '#dc2626'
    });
    console.log('Updated tags list count:', editRes.data.tags.length);

    // 4. Delete tag
    const delRes = await apiClient.post('/api/tags', {
      action: 'delete',
      tag_id: createdTag.id
    });
    console.log('Tag successfully removed. Remaining tags:', delRes.data.tags.length);
  } catch (err) {
    console.error('API Error:', err.response ? err.response.data : err.message);
  }
}

runTagWorkflow();
```

---

### cURL

#### 1. Retrieve all tags
```bash
curl -X GET "http://localhost:5000/api/tags" \
  -H "Authorization: Bearer cp_your_api_token_here" \
  -H "Accept: application/json"
```

#### 2. Create a new tag
```bash
curl -X POST "http://localhost:5000/api/tags" \
  -H "Authorization: Bearer cp_your_api_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "add",
    "name": "Quality Assurance",
    "color": "#10b981"
  }'
```

#### 3. Edit an existing tag
```bash
curl -X POST "http://localhost:5000/api/tags" \
  -H "Authorization: Bearer cp_your_api_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "edit",
    "tag_id": "tag_1724478475000",
    "name": "QA & Automation",
    "color": "#059669"
  }'
```

#### 4. Delete a tag
```bash
curl -X POST "http://localhost:5000/api/tags" \
  -H "Authorization: Bearer cp_your_api_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "delete",
    "tag_id": "tag_1724478475000"
  }'
```

#### 5. Create a task tagged with custom tags
```bash
curl -X POST "http://localhost:5000/api/daily/task/add" \
  -H "Authorization: Bearer cp_your_api_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-08-24",
    "text": "Write end-to-end Cypress tests",
    "priority": "High",
    "tags": ["tag_work", "tag_1724478475000"]
  }'
```
