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

### 3.1 Toggle Habit Day (Granular API)
Direct, ultra-fast toggle endpoint for updating a habit on a specific day of the month. Supports **Standard Checkboxes**, **Numeric Counters** (e.g. coffee cups, water glasses), and **Sub-Habits Groups** (e.g. medicines/vitamins).

- **Method**: `POST`
- **Path**: `/api/monthly/habit/toggle`
- **Request Body Examples (`application/json`)**:

#### A. Standard Boolean Checkbox Habit
```json
{
  "year": 2026,
  "month": 8,
  "habit_id": "1724581111000",
  "day": 25
}
```

#### B. Numeric Counter Habit (Increment / Decrement / Set Value)
```json
{
  "year": 2026,
  "month": 8,
  "habit_id": "1724582222000",
  "day": 25,
  "delta": 1
}
```
*Or set explicit count: `{"year": 2026, "month": 8, "habit_id": "...", "day": 25, "count": 3}`*

#### C. Sub-Habits Group Habit (Toggle specific medicine/sub-item)
```json
{
  "year": 2026,
  "month": 8,
  "habit_id": "1724583333000",
  "day": 25,
  "sub_habit_id": "sh_1"
}
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `year` | `integer` | Yes | Calendar year (e.g. `2026`) |
| `month` | `integer` | Yes | Calendar month (`1` to `12`) |
| `habit_id` | `string` | Yes | Habit unique ID |
| `day` | `integer` | Yes | Day of the month (`1` to `31`) |
| `delta` | `integer` | No | For counter habits (`+1` or `-1`) |
| `count` | `integer` | No | For counter habits: explicit count |
| `sub_habit_id` | `string` | No | For sub-habits: target sub-item ID |

#### Response (`200 OK`)
```json
// For Counter Habit:
{
  "success": true,
  "habit_id": "1724582222000",
  "day": 25,
  "type": "counter",
  "count": 3,
  "unit": "cups",
  "target_count": 2,
  "checked": true,
  "daily_counts": { "25": 3 }
}

// For Sub-Habits Habit:
{
  "success": true,
  "habit_id": "1724583333000",
  "day": 25,
  "type": "sub_habits",
  "sub_habit_id": "sh_1",
  "sub_checked": true,
  "completed_sub_ids": ["sh_1", "sh_2"],
  "completed_sub_count": 2,
  "total_sub_count": 3,
  "all_done": false,
  "checked": false
}
```

---

### 3.2 Reorder & Auto-Arrange Habits (Granular API)
Reorder habits in the monthly plan. Supports moving a habit up/down, supplying a custom ID array, or auto-arranging habits (`type_standard`: Checklists top ➔ Sub-habits middle ➔ Counters bottom; `alphabetical`; `completion`).

- **Method**: `POST`
- **Path**: `/api/monthly/habit/reorder`
- **Request Body Examples (`application/json`)**:

#### Option A: Move a Specific Habit Up / Down
```json
{
  "year": 2026,
  "month": 8,
  "habit_id": "1724581111000",
  "direction": "up"
}
```

#### Option B: Auto-Arrange by Strategy
```json
{
  "year": 2026,
  "month": 8,
  "arrange_by": "type_standard"
}
```
*Supported `arrange_by` values: `"type_standard"` (Checklists ➔ Sub-Habits ➔ Counters), `"alphabetical"`, `"completion"`.*

#### Option C: Supply Full Custom Array Order
```json
{
  "year": 2026,
  "month": 8,
  "order": ["1724581111000", "1724583333000", "1724582222000"]
}
```

#### Response (`200 OK`)
```json
{
  "success": true,
  "habits": [ ... ],
  "message": "Habits reordered successfully"
}
```

---

### 3.3 Yearly Habit Momentum Aggregation
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
Create a new habit in the monthly tracker. Supports 3 habit types:
1. `boolean`: Standard checkbox habit (e.g. "Morning Walk").
2. `counter`: Numeric counter habit (e.g. "Drink Coffee" with unit "cups" and target 2/day).
3. `sub_habits`: Sub-habits checklist group (e.g. "Take Medicine" with individual sub-items "Vitamin D", "Omega 3").

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body Examples (`application/json`)**:

#### Example 1: Add Standard Checkbox Habit
```json
{
  "action": "add_habit",
  "habit_name": "Morning Walk",
  "habit_type": "boolean",
  "category": "Fitness"
}
```

#### Example 2: Add Numeric Counter Habit
```json
{
  "action": "add_habit",
  "habit_name": "Drink Coffee",
  "habit_type": "counter",
  "category": "Health",
  "unit": "cups",
  "target_count": 2
}
```

#### Example 3: Add Sub-Habits Group Habit
```json
{
  "action": "add_habit",
  "habit_name": "Daily Medicine & Supplements",
  "habit_type": "sub_habits",
  "category": "Health",
  "sub_habits": "Vitamin D, Omega 3, Iron, Blood Pressure"
}
```

---

### 3.10 Manage Sub-Habits / Edit Habit
Update the list of sub-items (e.g. add/remove specific medicines) or update target count/unit for an existing habit.

- **Method**: `POST`
- **Path**: `/monthly?year=YYYY&month=MM`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "manage_sub_habits",
    "habit_id": "1724583333000",
    "sub_habits": [
      { "id": "sh_1", "name": "Vitamin D" },
      { "id": "sh_2", "name": "Omega 3" },
      { "id": "sh_3", "name": "Iron Supplement" }
    ]
  }
  ```

---

### 3.11 Delete Habit from Monthly Tracker
Delete a habit (and all its sub-habit items) from the tracker.

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

### 3.12 Save Calendar Day Event / Sticker / Image
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

### 3.13 Delete Calendar Day Item or Sticker
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

### 3.14 Save Monthly Reflection Notes
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

### 3.15 Export Monthly Plan to Excel
Download formatted Excel (`.xlsx`) sheet for the month with full habit breakdown.

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

export type HabitType = 'boolean' | 'counter' | 'sub_habits';

export interface SubHabitItem {
  id: string;
  name: string;
}

export interface MonthlyHabit {
  id: string;
  name: string;
  type?: HabitType;
  category?: string;
  completed_days: number[]; // days meeting completion criteria
  
  // For 'counter' habits:
  unit?: string; // e.g. "cups", "glasses", "pages"
  target_count?: number; // daily target
  daily_counts?: Record<string, number>; // e.g. { "1": 2, "2": 3 }

  // For 'sub_habits' habits:
  sub_habits?: SubHabitItem[]; // list of sub-items e.g. [{ id: "sh_1", name: "Vitamin D" }]
  daily_sub_completions?: Record<string, string[]>; // e.g. { "1": ["sh_1", "sh_2"] }
}

export interface CalendarDayItem {
  id: string;
  text: string;
  type: 'event' | 'deadline' | 'meeting' | 'reminder';
  remind_me?: boolean;
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
  calendar_days: Record<string, CalendarDayData>;
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

  // Toggle habit day (Standard, Counter, or Sub-Habit)
  public static toggleHabitDay(year: number, month: number, habitId: string, day: number, options?: { delta?: number; count?: number; subHabitId?: string }) {
    return this.request('/api/monthly/habit/toggle', {
      method: 'POST',
      body: JSON.stringify({
        year,
        month,
        habit_id: habitId,
        day,
        delta: options?.delta,
        count: options?.count,
        sub_habit_id: options?.subHabitId,
      }),
    });
  }

  // Add new habit
  public static addHabit(year: number, month: number, payload: {
    name: string;
    type?: HabitType;
    category?: string;
    unit?: string;
    targetCount?: number;
    subHabits?: string | string[];
  }) {
    return this.request(`/monthly?year=${year}&month=${month}`, {
      method: 'POST',
      body: JSON.stringify({
        action: 'add_habit',
        habit_name: payload.name,
        habit_type: payload.type || 'boolean',
        category: payload.category || 'General',
        unit: payload.unit,
        target_count: payload.targetCount,
        sub_habits: payload.subHabits,
      }),
    });
  }

  // Manage sub-habits
  public static manageSubHabits(year: number, month: number, habitId: string, subHabits: Array<{ id?: string; name: string } | string>) {
    return this.request(`/monthly?year=${year}&month=${month}`, {
      method: 'POST',
      body: JSON.stringify({
        action: 'manage_sub_habits',
        habit_id: habitId,
        sub_habits: subHabits,
      }),
    });
  }

  // Move habit up or down
  public static moveHabit(year: number, month: number, habitId: string, direction: 'up' | 'down') {
    return this.request('/api/monthly/habit/reorder', {
      method: 'POST',
      body: JSON.stringify({ year, month, habit_id: habitId, direction }),
    });
  }

  // Auto-arrange habits by strategy
  public static autoArrangeHabits(year: number, month: number, strategy: 'type_standard' | 'alphabetical' | 'completion') {
    return this.request('/api/monthly/habit/reorder', {
      method: 'POST',
      body: JSON.stringify({ year, month, arrange_by: strategy }),
    });
  }

  // Custom habit reorder by ID list
  public static reorderHabits(year: number, month: number, order: string[]) {
    return this.request('/api/monthly/habit/reorder', {
      method: 'POST',
      body: JSON.stringify({ year, month, order }),
    });
  }

  // Fetch yearly habit momentum
  public static getYearlyHabitMomentum(year?: number) {
    const query = year ? `?year=${year}` : '';
    return this.request<{ success: boolean; data: HabitMomentumMonth[] }>(`/api/monthly/habit/momentum-yearly${query}`);
  }
}

export default MonthlyApiService;
```
