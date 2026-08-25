# Weekly Planner REST API Documentation

Complete REST API specification and developer integration guide for the **Weekly Planner** tab. This document provides everything needed to build a standalone frontend in React, Next.js, Vue, Angular, or mobile.

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

## 2. Overview of Weekly Planner Features & State

A Weekly Plan is uniquely identified by `(user_id, year, week_number)`.
It includes:
1. **Weekly Goals**: High-level focus targets with completion checkboxes.
2. **7-Day Daily To-Dos**: Day-by-day task lists for Monday through Sunday (`Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun`).
3. **Smart Shopping List**: Categorized shopping items (e.g. `Groceries`, `Electronics`, `Supplements`, `Household`) with purchase checkboxes. **Unbought items automatically carry forward to future weeks.**
4. **7-Day Meal Menu**: 3-meals-a-day tracker for each day of the week (`breakfast`, `lunch`, `dinner`).
5. **Weekly Reflection / Notes**: End-of-week review and notes.
6. **Overall Execution Score**: Calculated dynamically based on goal completion, daily todos completed, and meal prep consistency.
7. **Excel Export & Text Aggregator**: Generate Excel reports or copy formatted text datasets for AI analysis.

---

## 3. Endpoints Reference

### 3.1 Get Weekly Plan Data
To read weekly planner data, the primary UI view or API endpoint retrieves the weekly record for a given `year` and `week`.

- **Method**: `GET`
- **Path**: `/weekly` (UI / JSON view)
- **Query Parameters**:
  | Param | Type | Required | Default | Description |
  | :--- | :--- | :--- | :--- | :--- |
  | `year` | `integer` | No | Current ISO Year | Year (e.g. `2026`) |
  | `week` | `integer` | No | Current ISO Week | ISO Week number (1–53) |

---

### 3.2 Add Weekly Goal
Add a primary high-level weekly goal to the current week's goal checklist.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_weekly_goal",
    "goal_title": "Launch new frontend repository with full test coverage"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "add_weekly_goal",
  "todo_pct": 75,
  "goals_pct": 50,
  "weekly_score": 68
}
```

---

### 3.3 Toggle Weekly Goal Status
Toggle a weekly goal between completed and active.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_weekly_goal",
    "goal_id": "1724581234567"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "toggle_weekly_goal",
  "todo_pct": 80,
  "goals_pct": 100,
  "weekly_score": 85
}
```

---

### 3.4 Delete Weekly Goal
Remove a goal from the weekly plan.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_weekly_goal",
    "goal_id": "1724581234567"
  }
  ```

---

### 3.5 Add Daily To-Do to a Specific Day
Add a daily task item under a specific day of the week (`Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun`).

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_daily_todo",
    "day_abbr": "Wed",
    "todo_text": "Code review & backend migration test"
  }
  ```
  | Field | Type | Required | Values |
  | :--- | :--- | :--- | :--- |
  | `day_abbr` | `string` | Yes | `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun` |
  | `todo_text` | `string` | Yes | Task title |

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "add_daily_todo",
  "todo_pct": 60,
  "weekly_score": 70
}
```

---

### 3.6 Toggle Daily To-Do Status
Check or uncheck a day's to-do item.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_daily_todo",
    "day_abbr": "Wed",
    "todo_id": "1724589999000"
  }
  ```

---

### 3.7 Delete Daily To-Do
Remove a task from a specific day of the week.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_daily_todo",
    "day_abbr": "Wed",
    "todo_id": "1724589999000"
  }
  ```

---

### 3.8 Add Shopping List Item
Add an item to the weekly grocery and supplies shopping checklist.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "add_shopping_item",
    "item_name": "Organic Greek Yogurt",
    "category": "Groceries"
  }
  ```
  *Common categories: `Groceries`, `Produce`, `Supplements`, `Household`, `Electronics`, `Work`.*

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "add_shopping_item",
  "shopping_count": 8,
  "weekly_score": 74
}
```

---

### 3.9 Toggle Shopping Item (`bought`)
Mark an item as purchased or pending.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "toggle_shopping_item",
    "item_id": "1724587777000"
  }
  ```

---

### 3.10 Delete Shopping Item
Remove an item from the shopping list.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "delete_shopping_item",
    "item_id": "1724587777000"
  }
  ```

---

### 3.11 Save 7-Day Meal Menu Matrix
Save the planned `breakfast`, `lunch`, and `dinner` for all 7 days of the week in a single request.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "save_meals_menu",
    "meal_bf_Mon": "Avocado Toast & Boiled Eggs",
    "meal_lu_Mon": "Grilled Chicken Salad",
    "meal_dn_Mon": "Steamed Salmon with Asparagus",
    "meal_bf_Tue": "Overnight Oats with Berries",
    "meal_lu_Tue": "Quinoa Veggie Bowl",
    "meal_dn_Tue": "Turkey Meatball Pasta",
    "meal_bf_Wed": "Protein Smoothie Bowl",
    "meal_lu_Wed": "Mediterranean Wrap",
    "meal_dn_Wed": "Tofu Stir-fry",
    "meal_bf_Thu": "Eggs & Whole Wheat Toast",
    "meal_lu_Thu": "Lentil Soup with Bread",
    "meal_dn_Thu": "Chicken Tikka & Rice",
    "meal_bf_Fri": "Granola with Almond Milk",
    "meal_lu_Fri": "Sushi Roll Bento",
    "meal_dn_Fri": "Homemade Veggie Pizza",
    "meal_bf_Sat": "Pancakes & Fresh Fruit",
    "meal_lu_Sat": "Grilled Cheese & Tomato Soup",
    "meal_dn_Sat": "Dining Out / Social",
    "meal_bf_Sun": "Scrambled Eggs & Fruit",
    "meal_lu_Sun": "Roast Chicken Salad",
    "meal_dn_Sun": "Meal Prep Batch Cooking"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "action": "save_meals_menu",
  "meal_pct": 100,
  "weekly_score": 92
}
```

---

### 3.12 Save Weekly Reflection Notes
Save markdown or text notes for weekly retrospective.

- **Method**: `POST`
- **Path**: `/weekly?year=YYYY&week=WW`
- **Request Body (`application/json`)**:
  ```json
  {
    "action": "save_weekly_notes",
    "notes": "Excellent execution this week. Maintained 90% workout consistency and hit code sprint goals."
  }
  ```

---

### 3.13 Fetch Weekly Activity Dataset (7-Day Aggregation)
Returns an aggregated text summary of all 7 days of daily logs in that week for copy-pasting or LLM analysis.

- **Method**: `GET`
- **Path**: `/weekly/fetch_activity?year=YYYY&week=WW`

#### Response (`200 OK`)
```json
{
  "success": true,
  "year": 2026,
  "week": 35,
  "formatted_text": "=== DATASET: DAILY ACTIVITY LOGS (Week 35, 2026: Aug 24, 2026 - Aug 30, 2026) ===\n\n--- Day 1: Mon 2026-08-24 (Monday) ---\n  - 09:00 - 10:00 AM: Weekly Kickoff [Mood: 🚀]\n  Tasks: [Completed] Review architecture doc\n  Sleep: 7.5 hrs (Quality: 8/10)\n\n--- Day 2: Tue 2026-08-25 (Tuesday) ---\n  - 10:00 - 11:00 AM: Feature Implementation [Mood: 💻]\n  Tasks: [Completed] Setup frontend auth client"
}
```

---

### 3.14 Export Weekly Plan to Excel
Download a formatted Excel (`.xlsx`) sheet containing the full weekly schedule, daily to-dos, shopping list, and meal matrix.

- **Method**: `GET`
- **Path**: `/weekly/export_excel?year=YYYY&week=WW`
- **Response**: Binary Excel file (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

---

## 4. Frontend TypeScript Data Interfaces

```typescript
export type DayAbbreviation = 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri' | 'Sat' | 'Sun';

export interface WeeklyGoal {
  id: string;
  title: string;
  completed: boolean;
}

export interface WeeklyDailyTodo {
  id: string;
  text: string;
  completed: boolean;
}

export interface ShoppingItem {
  id: string;
  item: string;
  category: string;
  bought: boolean;
  added_date?: string;
}

export interface DayMeals {
  breakfast: string;
  lunch: string;
  dinner: string;
}

export interface WeeklyPlanData {
  id: number;
  year: number;
  week_number: number;
  start_date: string;
  goals: WeeklyGoal[];
  daily_todos: Record<DayAbbreviation, WeeklyDailyTodo[]>;
  shopping_list: ShoppingItem[];
  meals_menu: Record<DayAbbreviation, DayMeals>;
  notes: string;
  metrics?: {
    todo_pct: number;
    goals_pct: number;
    meal_pct: number;
    weekly_score: number;
  };
}
```

---

## 5. Frontend API Service Example (TypeScript)

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

class WeeklyApiService {
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
      throw new Error(data.message || 'Weekly API request failed');
    }
    return data;
  }

  // Add goal
  public static addGoal(year: number, week: number, title: string) {
    return this.request(`/weekly?year=${year}&week=${week}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_weekly_goal', goal_title: title }),
    });
  }

  // Toggle goal
  public static toggleGoal(year: number, week: number, goalId: string) {
    return this.request(`/weekly?year=${year}&week=${week}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'toggle_weekly_goal', goal_id: goalId }),
    });
  }

  // Add day todo
  public static addDailyTodo(year: number, week: number, dayAbbr: DayAbbreviation, text: string) {
    return this.request(`/weekly?year=${year}&week=${week}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_daily_todo', day_abbr: dayAbbr, todo_text: text }),
    });
  }

  // Add shopping item
  public static addShoppingItem(year: number, week: number, itemName: string, category: string = 'Groceries') {
    return this.request(`/weekly?year=${year}&week=${week}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'add_shopping_item', item_name: itemName, category }),
    });
  }

  // Toggle shopping item
  public static toggleShoppingItem(year: number, week: number, itemId: string) {
    return this.request(`/weekly?year=${year}&week=${week}`, {
      method: 'POST',
      body: JSON.stringify({ action: 'toggle_shopping_item', item_id: itemId }),
    });
  }
}

export default WeeklyApiService;
```
