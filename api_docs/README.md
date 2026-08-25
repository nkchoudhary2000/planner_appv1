# Chronos Planner REST API Documentation Hub

Welcome to the comprehensive REST API documentation for the **Chronos Planner** platform. This directory contains detailed, modular documentation for every tab and subsystem so you can build a complete, state-of-the-art frontend application (React, Next.js, Vue, Svelte, iOS/Android mobile apps, or CLI tools) in a completely separate repository.

---

## 📑 Documentation Modules

| Module / Tab | Documentation File | Description |
| :--- | :--- | :--- |
| ☀️ **Daily Planner** | [daily_api_doc.md](file:///d:/NIOM/Codex%20project/Planner_appV1/api_docs/daily_api_doc.md) | Tasks, 24-hour hourly schedule & moods, sleep metrics, depression/symptom logs, memory logs, cascaded items, Excel export. |
| 📅 **Weekly Planner** | [weekly_api_doc.md](file:///d:/NIOM/Codex%20project/Planner_appV1/api_docs/weekly_api_doc.md) | Weekly goals, 7-day daily to-dos, shopping list with automatic unbought carry-forward, 7-day meal matrix, execution score. |
| 🗓️ **Monthly Planner** | [monthly_api_doc.md](file:///d:/NIOM/Codex%20project/Planner_appV1/api_docs/monthly_api_doc.md) | Monthly goals, milestones, calendar day events/stickers/images, habit tracker matrix, yearly habit momentum heatmap API. |
| 🎯 **Yearly Planner** | [yearly_api_doc.md](file:///d:/NIOM/Codex%20project/Planner_appV1/api_docs/yearly_api_doc.md) | Annual resolutions by category, quarterly OKRs/objectives, key annual events & birthdays calendar, year-end retrospectives. |
| 🗂️ **Planner & Core** | [planner_api_doc.md](file:///d:/NIOM/Codex%20project/Planner_appV1/api_docs/planner_api_doc.md) | Planning backlog tasks, event time-trackers & countdowns, user custom tags, full JSON backup/restore, Google Drive cloud sync. |
| 🔐 **Admin & Auth** | [admin_api_doc.md](file:///d:/NIOM/Codex%20project/Planner_appV1/api_docs/admin_api_doc.md) | User registration, login, logout, profile updates, API token lifecycle (`cp_...`), Google SSO, admin statistics & database management. |

---

## 🚀 Quick Start Guide for Frontend Developers

### 1. Base URL
- **Local API**: `http://localhost:5000`
- **Deployed Production**: `https://<YOUR_DEPLOYED_DOMAIN>`

### 2. Authentication Methods
The backend supports 3 token delivery formats for all protected endpoints:

1. **HTTP Authorization Header (Standard & Recommended)**:
   ```http
   Authorization: Bearer cp_9a8b7c6d5e4f3a2b1c0d...
   ```
2. **Custom Header**:
   ```http
   X-API-Token: cp_9a8b7c6d5e4f3a2b1c0d...
   ```
3. **URL Query Parameter**:
   ```http
   https://api.example.com/api/daily?api_token=cp_9a8b7c6d5e4f3a2b1c0d...
   ```

### 3. Standard Request Headers
```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer <YOUR_API_TOKEN>
```

### 4. Cross-Origin Resource Sharing (CORS)
CORS is globally enabled on the backend for all origins (`*`) and supports methods `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`, `PATCH`, allowing direct AJAX calls from `http://localhost:3000`, `http://localhost:5173`, or any external web origin.

---

## 🛠️ Ready-to-Use Frontend API Client (TypeScript)

Save this `ApiClient.ts` file in your frontend repository to immediately start consuming the Chronos API:

```typescript
// src/api/ApiClient.ts

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

class ApiClient {
  private static token: string | null = null;

  public static setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('chronos_api_token', token);
    }
  }

  public static getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('chronos_api_token');
    }
    return this.token;
  }

  public static async request<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string>),
    };

    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok || (data && data.success === false)) {
      const errorMsg = data?.message || `HTTP Error ${response.status}: ${response.statusText}`;
      throw new Error(errorMsg);
    }

    return data as T;
  }

  // HTTP Helper Methods
  public static get<T = any>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  public static post<T = any>(endpoint: string, body?: any) {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  public static delete<T = any>(endpoint: string, body?: any) {
    return this.request<T>(endpoint, {
      method: 'DELETE',
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

export default ApiClient;
```

---

## 📦 API Data Flow & Cascading Architecture

```
                       ┌─────────────────────────┐
                       │   Yearly Planner (OKRs) │
                       │    - Annual Events      │
                       └───────────┬─────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
       ┌─────────────────────────┐   ┌─────────────────────────┐
       │     Monthly Planner     │   │   Weekly Planner (W1-53)│
       │  - Milestones & Habits  │   │  - Goals & Daily Todos  │
       └────────────┬────────────┘   └────────────┬────────────┘
                    │                             │
                    └──────────────┬──────────────┘
                                   ▼
                       ┌─────────────────────────┐
                       │   Daily Planner (Today) │
                       │  - Cascaded Multi-View  │
                       │  - Hourly Schedule Log  │
                       │  - Tasks Checklist      │
                       └─────────────────────────┘
                                   ▲
                                   │
                       ┌───────────┴─────────────┐
                       │  Planning Tasks Backlog │
                       │  - Date-Independent     │
                       └─────────────────────────┘
```
