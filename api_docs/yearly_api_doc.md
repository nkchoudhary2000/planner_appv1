# Yearly Planner REST API Documentation

Complete REST API specification and developer integration guide for the **Yearly Planner** tab. This document details annual goal setting, resolutions, quarterly OKRs/objectives, key annual events/birthday calendars, and year-end retrospectives.

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

## 2. Overview of Yearly Planner Features & State

A Yearly Plan is uniquely identified by `(user_id, year)`.
It includes:
1. **Annual Resolutions**: Categorized resolutions (e.g. `Health & Fitness`, `Career & Skills`, `Financial`, `Personal Growth`) with completion checkboxes.
2. **Quarterly Objectives (OKRs)**: Strategic objectives mapped to quarters (`Q1`, `Q2`, `Q3`, `Q4`, or `Q1-Q4`) with status tracking (`Not Started`, `In Progress`, `Completed`, `Deferred`).
3. **Yearly Events Calendar**: Major dates, birthdays, anniversaries, trips, and milestones throughout the year with auto-cascading into the Daily and Monthly views.
4. **Year-End Reflections / Retrospective**: Free-form summary review of accomplishments, challenges, and lessons learned.
5. **Excel Export**: Download a formatted annual overview `.xlsx` workbook.

---

## 3. Endpoints Reference

### 3.1 Add Annual Resolution
Add a new resolution to the yearly vision board.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_resolution",
    "resolution_text": "Read 24 non-fiction books",
    "category": "Personal Growth"
  }
  ```
  | Field | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `resolution_text` | `string` | Yes | Description of resolution |
  | `category` | `string` | No | Category (e.g. `Personal`, `Health`, `Career`, `Finance`, `Travel`) |

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "add_resolution"
}
```

---

### 3.2 Toggle Resolution Status
Check or uncheck an annual resolution.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_resolution",
    "resolution_id": "1724581234567"
  }
  ```

---

### 3.3 Delete Resolution
Remove a resolution from the yearly plan.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_resolution",
    "resolution_id": "1724581234567"
  }
  ```

---

### 3.4 Add Quarterly Objective (OKR)
Add a quarterly objective associated with a target quarter.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_objective",
    "objective_title": "Achieve $50k ARR on SaaS Product",
    "quarter": "Q2"
  }
  ```
  | Field | Type | Required | Values |
  | :--- | :--- | :--- | :--- |
  | `objective_title` | `string` | Yes | Title/description of objective |
  | `quarter` | `string` | Yes | `Q1`, `Q2`, `Q3`, `Q4`, or `Q1-Q4` |

---

### 3.5 Update Quarterly Objective Status
Update the progress status of a quarterly objective.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "update_objective_status",
    "objective_id": "1724582222000",
    "status": "Completed"
  }
  ```
  *Allowed status values: `Not Started`, `In Progress`, `Completed`, `Deferred`.*

---

### 3.6 Delete Quarterly Objective
Remove an objective from the yearly plan.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_objective",
    "objective_id": "1724582222000"
  }
  ```

---

### 3.7 Add Yearly Event / Birthday
Register an important annual date or milestone.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_yearly_event",
    "event_title": "Mom's 60th Birthday Celebration",
    "event_type": "birthday",
    "event_date": "2026-11-14",
    "notes": "Plan family dinner in advance"
  }
  ```
  | Field | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `event_title` | `string` | Yes | Name of event |
  | `event_type` | `string` | No | `birthday`, `anniversary`, `holiday`, `trip`, `work`, `milestone` |
  | `event_date` | `string` | Yes | `YYYY-MM-DD` date |
  | `notes` | `string` | No | Extra details/notes |

---

### 3.8 Toggle Yearly Event Status
Mark an event as celebrated / completed.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_yearly_event",
    "event_id": "1724583333000"
  }
  ```

---

### 3.9 Delete Yearly Event
Remove an event from the annual calendar.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_yearly_event",
    "event_id": "1724583333000"
  }
  ```

---

### 3.10 Save Year-End Reflections
Save the annual retrospective and reflection review.

- **Method**: `POST`
- **Path**: `/yearly?year=YYYY`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "save_reflections",
    "reflections": "2026 was a foundational year. Launched two major open-source tools and built strong daily habits."
  }
  ```

---

### 3.11 Export Yearly Plan to Excel
Download formatted Excel (`.xlsx`) sheet for the year.

- **Method**: `GET`
- **Path**: `/yearly/export_excel?year=YYYY`
- **Response**: Binary Excel file (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

---

## 4. Frontend TypeScript Data Interfaces

```typescript
export interface YearlyResolution {
  id: string;
  text: string;
  category: string;
  completed: boolean;
}

export type QuarterType = 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'Q1-Q4';
export type ObjectiveStatus = 'Not Started' | 'In Progress' | 'Completed' | 'Deferred';

export interface QuarterlyObjective {
  id: string;
  title: string;
  quarter: QuarterType;
  status: ObjectiveStatus;
}

export interface YearlyEvent {
  id: string;
  title: string;
  event_type: 'birthday' | 'anniversary' | 'holiday' | 'trip' | 'work' | 'milestone';
  date: string; // YYYY-MM-DD
  notes?: string;
  completed: boolean;
}

export interface YearlyPlanData {
  id: number;
  year: number;
  resolutions: YearlyResolution[];
  objectives: QuarterlyObjective[];
  events: YearlyEvent[];
  reflections: string;
}
```

---

## 5. Frontend API Service Example (TypeScript)

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

class YearlyApiService {
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
      throw new Error(data.message || 'Yearly API request failed');
    }
    return data;
  }

  // Add resolution
  public static addResolution(year: number, text: string, category: string = 'Personal') {
    return this.request(`/yearly?year=${year}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_resolution', resolution_text: text, category }),
    });
  }

  // Add objective
  public static addObjective(year: number, title: string, quarter: QuarterType = 'Q1') {
    return this.request(`/yearly?year=${year}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_objective', objective_title: title, quarter }),
    });
  }

  // Add yearly event
  public static addYearlyEvent(year: number, payload: { title: string; eventType: string; date: string; notes?: string }) {
    return this.request(`/yearly?year=${year}`, {
      method: 'POST',
      body: JSON.stringify({
        action: 'add_yearly_event',
        event_title: payload.title,
        event_type: payload.eventType,
        event_date: payload.date,
        notes: payload.notes || '',
      }),
    });
  }
}

export default YearlyApiService;
```
