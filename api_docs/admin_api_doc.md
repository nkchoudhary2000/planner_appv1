# Admin & Authentication REST API Documentation

Complete REST API specification and developer integration guide for **User Authentication**, **Profile Management**, **Security API Token Lifecycle**, **Google OAuth SSO**, and the **System Admin Dashboard**.

---

## 1. Authentication Architecture

The backend supports dual authentication modes:
1. **API Token Authentication (Recommended for Headless / Separate Frontend Repos)**:
   - Header: `Authorization: Bearer <API_TOKEN>`
   - Header: `X-API-Token: <API_TOKEN>`
   - Query Param: `?api_token=<API_TOKEN>`
2. **Session Cookie Authentication**: Standard secure HTTP session cookie created upon `/auth/login` or Google OAuth callback.

---

## 2. Authentication & User Profile Endpoints

### 2.1 User Login
Authenticate using email or username with a password.

- **Method**: `POST`
- **Path**: `/auth/login`
- **Request Format**: `application/json` or `application/x-www-form-urlencoded`
- **Request Body**:
  ```json
  {
    "login_input": "johndoe@example.com",
    "password": "SecurePassword123!",
    "remember": true
  }
  ```
  | Field | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `login_input` | `string` | Yes | Username or Email address |
  | `password` | `string` | Yes | Account password |
  | `remember` | `boolean`| No | Keep session active |

#### Response (`200 OK` / Redirect)
```json
{
  "success": true,
  "message": "Welcome back, johndoe!",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "johndoe@example.com",
    "display_name": "John Doe",
    "is_admin": false
  }
}
```

---

### 2.2 User Registration
Create a new user account.

- **Method**: `POST`
- **Path**: `/auth/register`
- **Request Body**:
  ```json
  {
    "username": "johndoe",
    "email": "johndoe@example.com",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!"
  }
  ```

#### Response (`200 OK` / Redirect)
```json
{
  "success": true,
  "message": "Registration successful! Your account has been created."
}
```

---

### 2.3 User Logout
End the current authenticated session.

- **Method**: `POST` or `GET`
- **Path**: `/auth/logout`

---

### 2.4 Update User Profile
Update display name, username, email, or change password.

- **Method**: `POST`
- **Path**: `/auth/update-profile`
- **Headers**: `Authorization: Bearer <API_TOKEN>` or Cookie Session
- **Request Body (`application/json`)**:
  ```json
  {
    "display_name": "John Doe, Lead Engineer",
    "username": "johndoe_pro",
    "email": "johndoe.new@example.com",
    "new_password": "NewSecurePassword456!",
    "confirm_password": "NewSecurePassword456!"
  }
  ```

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "Profile updated successfully!",
  "user": {
    "username": "johndoe_pro",
    "email": "johndoe.new@example.com",
    "display_name": "John Doe, Lead Engineer",
    "name": "John Doe, Lead Engineer",
    "has_token": true,
    "masked_token": "cp_9a8...1c0d"
  }
}
```

---

### 2.5 Set Password (for Google SSO Accounts)
Allows users who initially registered via Google Sign-In to establish a local password.

- **Method**: `POST`
- **Path**: `/auth/set-password`
- **Request Body**:
  ```json
  {
    "new_password": "MyLocalPassword123!",
    "confirm_password": "MyLocalPassword123!"
  }
  ```

---

## 3. Security API Token Lifecycle

Users can generate persistent secret API tokens prefixed with `cp_` for programmatic API access and headless frontend clients.

### 3.1 Generate New API Token
Creates a secure 256-bit random API key. Overwrites any previous token.

- **Method**: `POST`
- **Path**: `/auth/generate-api-token`
- **Headers**: Requires active session or existing token

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "New API token generated successfully!",
  "api_token": "cp_9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
  "masked_token": "cp_9a8...9a8b",
  "created_at": "2026-08-25 12:55:00 UTC"
}
```

---

### 3.2 Revoke API Token
Immediately invalidates the user's active API token.

- **Method**: `POST`
- **Path**: `/auth/revoke-api-token`

#### Response (`200 OK`)
```json
{
  "success": true,
  "message": "API token revoked successfully!"
}
```

---

### 3.3 Get API Token Status
Check whether a token is active and view the masked token string.

- **Method**: `GET`
- **Path**: `/auth/api-token-info`

#### Response (`200 OK`)
```json
{
  "success": true,
  "has_token": true,
  "masked_token": "cp_9a8...9a8b",
  "created_at": "2026-08-25 12:55:00 UTC"
}
```

---

## 4. Google OAuth2 Integration

- **Initiate Google Sign-In**: Navigate the browser to `/auth/google/login`.
- **OAuth Callback**: Handled automatically at `/auth/google/callback`.
- Once connected, Google Drive sync is automatically activated for nightly automated database backups.

---

## 5. System Admin Panel Endpoints

> [!IMPORTANT]
> Admin endpoints are strictly restricted to the system administrator account (`niraj.choudhary1995@gmail.com`). Unauthorized requests will return `403 Forbidden` or redirect to the dashboard.

### 5.1 Admin Dashboard & System Analytics
Retrieve platform overview, user counts, plan counts, and individual user statistics.

- **Method**: `GET`
- **Path**: `/admin/`
- **Response Data Structure**:
  ```json
  {
    "admin_email": "niraj.choudhary1995@gmail.com",
    "total_users": 42,
    "total_daily_plans": 1250,
    "total_weekly_plans": 310,
    "total_monthly_plans": 84,
    "total_yearly_plans": 18,
    "users": [
      {
        "id": 1,
        "username": "niraj",
        "email": "niraj.choudhary1995@gmail.com",
        "created_at": "2026-01-01 00:00:00",
        "is_admin": true,
        "google_connected": true,
        "daily_count": 180,
        "weekly_count": 32,
        "monthly_count": 8,
        "yearly_count": 1,
        "total_plans": 221
      },
      {
        "id": 2,
        "username": "johndoe",
        "email": "johndoe@example.com",
        "created_at": "2026-02-15 10:30:00",
        "is_admin": false,
        "google_connected": false,
        "daily_count": 45,
        "weekly_count": 10,
        "monthly_count": 3,
        "yearly_count": 1,
        "total_plans": 59
      }
    ]
  }
  ```

---

### 5.2 Admin: Delete User Account
Permanently removes a user and cascades deletion to all their daily, weekly, monthly, yearly plans, planning tasks, and events.

- **Method**: `POST`
- **Path**: `/admin/user/delete/<int:user_id>`

---

### 5.3 Admin: Purge Specific User Plans
Deletes all planner records (Daily, Weekly, Monthly, Yearly) for a specific user while leaving the user account active.

- **Method**: `POST`
- **Path**: `/admin/user/clear-plans/<int:user_id>`

---

### 5.4 Admin: Purge All Database Plans
Global wipe of all plan records across all users in the system.

- **Method**: `POST`
- **Path**: `/admin/db/clear-plans`

---

## 6. Frontend TypeScript Interfaces

```typescript
export interface UserProfile {
  id: number;
  username: string;
  email: string;
  display_name?: string;
  name: string;
  is_admin: boolean;
  google_connected: boolean;
  has_token: boolean;
  masked_token?: string;
  created_at: string;
}

export interface AdminUserListItem {
  id: number;
  username: string;
  email: string;
  created_at: string;
  is_admin: boolean;
  google_connected: boolean;
  daily_count: number;
  weekly_count: number;
  monthly_count: number;
  yearly_count: number;
  total_plans: number;
}

export interface AdminDashboardData {
  admin_email: string;
  total_users: number;
  total_daily_plans: number;
  total_weekly_plans: number;
  total_monthly_plans: number;
  total_yearly_plans: number;
  users: AdminUserListItem[];
}
```
