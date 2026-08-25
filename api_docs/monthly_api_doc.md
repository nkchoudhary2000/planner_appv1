# Monthly Planner REST API Documentation

Complete REST API specification and developer integration guide for the **Monthly Planner** tab. This document provides everything needed to build monthly calendar grids, habit tracking matrices, milestone timelines, and momentum charts in a standalone frontend repository.

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

## 2. Overview of Monthly Planner Features & State

A Monthly Plan is uniquely identified by `(user_id, year, month)` where `month` is 1 to 12.
It includes:
1. **Monthly Goals**: Target goals categorized by area (e.g. `Career`, `Finance`, `Health`, `Personal`) with deadlines and status (`In Progress`, `Completed`).
2. **Key Milestones**: Date-specific milestones mapped to days of the month (e.g. Day 15: "Ship Beta Version").
3. **Monthly Calendar Days Grid**: Rich day-by-day calendar data containing:
   - Calendar items (deadlines, events, reminders).
   - Custom emoji stickers (e.g. `🚀`, `🎉`, `💪`, `🔥`).
   - Image URLs attached to specific calendar days.
4. **Habit Tracker Matrix**: Multi-habit tracker tracking daily completion across all days in the month (e.g. Days 1 through 31).
5. **Granular Habit Day Toggle**: Fast checkbox toggle endpoint without reloading or modifying the rest of the plan.
6. **Yearly Habit Momentum Heatmap API**: 12-month aggregated streak and habit volume data across the entire year.
7. **Monthly Reflection / Notes**: Free-form retrospective notes.
8. **Excel Export**: Download formatted monthly `.xlsx` workbook.

---

## 3. Endpoints Reference

### 3.1 Toggle Habit Day Completion (Granular API)
Direct, ultra-fast toggle endpoint for checking or unchecking a habit on a specific day of the month.

- **Method**: `POST`
- **Path**: `/api/monthly/habit/toggle`
- **Request Body (`application/json`)**:
  ```json
  {
    "year": 2026,
    "month": 8,
    "habit_id": "1724581111000",
    "day": 25
  }
  ```
  | Field | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `year` | `integer` | Yes | Calendar year (e.g. `2026`) |
  | `month` | `integer` | Yes | Calendar month (`1` to `12`) |
  | `habit_id` | `string` | Yes | Habit unique ID |
  | `day` | `integer` | Yes | Day of the month (`1` to `31`) |

#### Response (`200 OK`)
```json
{
  "success": true,
  "checked": true
}
```

---

### 3.2 Yearly Habit Momentum Aggregation
Retrieve aggregated 12-month habit performance across the year for heatmaps, streak charts, and momentum gauges.

- **Method**: `GET`
- **Path**: `/api/monthly/habit/momentum-yearly`
- **Query Parameters**:
  | Param | Type | Required | Default | Description |
  | :--- | :--- | :--- | :--- | :--- |
  | `year` | `integer` | No | Current Year | Calendar year (e.g. `2026`) |

#### Response (`200 OK`)
```json
{
  "success": true,
  "data": [
    {
      "month": 1,
      "label": "Jan",
      "total_habits": 3,
      "days_in_month": 31,
      "completed_slots": 78,
      "habits": [
        { "id": "h1", "name": "Morning Meditation", "completed_count": 28 },
        { "id": "h2", "name": "10k Daily Steps", "completed_count": 25 },
        { "id": "h3", "name": "Read 20 Pages", "completed_count": 25 }
      ]
    },
    {
      "month": 8,
      "label": "Aug",
      "total_habits": 4,
      "days_in_month": 31,
      "completed_slots": 92,
      "habits": [
        { "id": "h1", "name": "Morning Meditation", "completed_count": 24 },
        { "id": "h2", "name": "10k Daily Steps", "completed_count": 22 },
        { "id": "h3", "name": "Read 20 Pages", "completed_count": 26 },
        { "id": "h4", "name": "Drink 3L Water", "completed_count": 20 }
      ]
    }
  ]
}
```

---

### 3.3 Add Monthly Goal
Add a monthly goal target with category and target deadline.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_goal",
    "goal_title": "Launch Mobile App MVP on App Store",
    "category": "Career",
    "deadline": "2026-08-30"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "add_goal",
  "goals_pct": 50,
  "monthly_score": 75
}
```

---

### 3.4 Toggle Monthly Goal Status
Toggle goal status between `In Progress` and `Completed`.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_goal",
    "goal_id": "1724582222000"
  }
  ```

---

### 3.5 Delete Monthly Goal
Remove a goal from the monthly plan.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_goal",
    "goal_id": "1724582222000"
  }
  ```

---

### 3.6 Add Monthly Milestone
Add a key dated milestone in the month.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_milestone",
    "milestone_title": "Investor Pitch Deck Review",
    "milestone_date": "15"
  }
  ```

---

### 3.7 Toggle Monthly Milestone Status
Toggle milestone completion status.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_milestone",
    "milestone_id": "1724583333000"
  }
  ```

---

### 3.8 Delete Monthly Milestone
Remove a milestone from the monthly plan.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_milestone",
    "milestone_id": "1724583333000"
  }
  ```

---

### 3.9 Add Habit to Monthly Tracker
Create a new habit column/row for the current month.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_habit",
    "habit_name": "Zero Sugar Day",
    "category": "Health"
  }
  ```

---

### 3.10 Delete Habit from Monthly Tracker
Delete a habit from the tracker.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_habit",
    "habit_id": "1724584444000"
  }
  ```

---

### 3.11 Save Calendar Day Event / Sticker / Image
Attach a custom event item, emoji sticker, or image banner to a specific day on the monthly grid.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "save_calendar_day",
    "day": 25,
    "item_text": "Team Product Demo",
    "item_type": "event",
    "sticker": "🚀",
    "image_url": "https://cdn.example.com/banners/launch.png"
  }
  ```

---

### 3.12 Delete Calendar Day Item or Sticker
- **Delete Calendar Event Item**:
  ```json
  {
    "action": "delete_calendar_item",
    "day": 25,
    "item_id": "1724585555000"
  }
  ```
- **Delete Day Sticker**:
  ```json
  {
    "action": "delete_day_sticker",
    "day": 25
  }
  ```

---

### 3.13 Save Monthly Reflection Notes
Save monthly notes or retrospective thoughts.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "save_notes",
    "notes": "Solid month overall. Surpassed user acquisition targets by 20%."
  }
  ```

---

### 3.14 Export Monthly Plan to Excel
Download formatted Excel (`.xlsx`) sheet for the month.

- **Method**: `GET`
- **Path**: `/monthly/export_excel?year=YYYY&month=MM`
- **Response**: Binary Excel file (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

---

## 4. Frontend TypeScript Data Interfaces

```typescript
export interface MonthlyGoal {
  id: string;
  title: string;
  category: string;
  deadline?: string;
  status: 'In Progress' | 'Completed';
}

export interface MonthlyMilestone {
  id: string;
  title: string;
  date: string; // day of month (e.g. "15")
  completed: boolean;
}

export interface MonthlyHabit {
  id: string;
  name: string;
  category?: string;
  completed_days: number[]; // array of day integers e.g. [1, 2, 5, 12, 25]
}

export interface CalendarDayItem {
  id: string;
  text: string;
  type: 'event' | 'deadline' | 'meeting' | 'reminder';
}

export interface CalendarDayData {
  items: CalendarDayItem[];
  sticker?: string;
  image_url?: string;
}

export interface MonthlyPlanData {
  id: number;
  year: number;
  month: number;
  goals: MonthlyGoal[];
  milestones: MonthlyMilestone[];
  habits: MonthlyHabit[];
  calendar_days: Record<string, CalendarDayData>; // keys are day strings: "1", "2", ... "31"
  notes: string;
}

export interface HabitMomentumMonth {
  month: number;
  label: string;
  total_habits: number;
  days_in_month: number;
  completed_slots: number;
  habits: Array<{
    id: string;
    name: string;
    completed_count: number;
  }>;
}
```

---

## 5. Frontend API Service Example (TypeScript)

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

class MonthlyApiService {
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
      throw new Error(data.message || 'Monthly API request failed');
    }
    return data;
  }

  // Toggle habit day checkbox
  public static toggleHabitDay(year: number, month: number, habitId: string, day: number) {
    return this.request<{ success: boolean; checked: boolean }>('/api/monthly/habit/toggle', {
      method: 'POST',
      body: JSON.stringify({ year, month, habit_id: habitId, day }),
    });
  }

  // Fetch yearly habit momentum
  public static getYearlyHabitMomentum(year?: number) {
    const query = year ? `?year=${year}` : '';
    return this.request<{ success: boolean; data: HabitMomentumMonth[] }>(`/api/monthly/habit/momentum-yearly${query}`);
  }

  // Add goal
  public static addGoal(year: number, month: number, title: string, category: string = 'General', deadline?: string) {
    return this.request(`/monthly?year=${year}&month=${month}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_goal', goal_title: title, category, deadline }),
    });
  }

  // Add habit
  public static addHabit(year: number, month: number, habitName: string, category: string = 'General') {
    return this.request(`/monthly?year=${year}&month=${month}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_habit', habit_name: habitName, category }),
    });
  }
}

export default MonthlyApiService;
```
