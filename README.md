# Chronos Planner - Multi-User Full-Stack Planner Web Application

Chronos Planner is a full-stack Python Flask web application designed for personal productivity and multi-user planning across three time horizons: **Daily**, **Monthly**, and **Yearly**. Built with modern dark aesthetics powered by Tailwind CSS, Jinja2 templates, and SQLite/PostgreSQL database support via SQLAlchemy.

---

## Features & Architecture

- **Secure Authentication System**: Multi-user registration, password hashing using Werkzeug, login session persistence via Flask-Login, and strict user data isolation.
- **Daily Planner View**:
  - Task checklist with interactive AJAX check-offs and priority tagging (High, Medium, Low).
  - 24-hour time block hourly schedule grid.
  - End-of-day reflection journal & notes.
- **Monthly Planner View**:
  - Interactive Habit Tracking Matrix with clickable daily grid checkboxes.
  - Monthly goals tracker with status progression (In Progress, Completed).
  - Target day milestone schedule.
- **Yearly Planner View**:
  - Annual resolutions list categorized by life area.
  - Strategic quarterly objectives breakdown with live status indicators.
  - Year-in-Review annual reflection journal.
- **Database Portability**:
  - Local Development: SQLite (`planner.db`).
  - Production Deployment: PostgreSQL supported automatically via standard `DATABASE_URL` environment variable.

---

## Local Development & Installation Setup

### Prerequisites

- **Python**: Version 3.10+ (Tested on Python 3.11)
- **Git**

### Installation Steps

1. **Clone the Repository & Navigate to Workspace**:
   ```bash
   git clone <your-repository-url>
   cd Planner_appV1
   ```

2. **Set Up a Virtual Environment**:
   ```bash
   # On macOS/Linux:
   python3 -m venv .venv
   source .venv/bin/activate

   # On Windows (PowerShell):
   python -m venv .venv
   \.venv\Scripts\Activate.ps1
   ```

3. **Install Required Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the Database & Run the Local Server**:
   ```bash
   python run.py
   ```
   *The application automatically creates database tables in `planner.db` on first start.*

5. **Access the Web Interface**:
   Open your web browser and navigate to:
   [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Application Structure

```
Planner_appV1/
├── app/
│   ├── __init__.py         # Flask app factory, extension initializations
│   ├── models.py           # User, DailyPlan, MonthlyPlan, YearlyPlan database schemas
│   ├── auth/
│   │   ├── __init__.py     # Auth blueprint initialization
│   │   └── routes.py       # Login, Register, Logout routes & logic
│   ├── planner/
│   │   ├── __init__.py     # Planner blueprint initialization
│   │   └── routes.py       # Dashboard, Daily, Monthly, Yearly & AJAX API endpoints
│   ├── templates/          # Jinja2 HTML templates
│   │   ├── base.html       # Main responsive layout with Tailwind CSS CDN & Navbar
│   │   ├── auth/           # Login & Register views
│   │   └── planner/        # Dashboard, Daily, Monthly, Yearly views
│   └── static/
│       ├── css/
│       │   └── custom.css  # Modern dark mode theme, glassmorphism & habit grid styling
│       └── js/
│           └── main.js     # Asynchronous AJAX toggles & interactive elements
├── config.py               # Environment configuration (SQLite local, PostgreSQL prod)
├── run.py                  # Server execution entrypoint
├── requirements.txt        # Python package requirements
├── Procfile                # Gunicorn process config for Render / Heroku
├── render.yaml             # Render Blueprint deployment configuration
└── README.md               # Documentation & Guide
```

---

## Free Tier Deployment Guide (Render)

This application is ready out of the box for free hosting on [Render](https://render.com/).

### Option A: Automatic Blueprint Deployment (Recommended)
1. Push your repository to GitHub / GitLab.
2. Sign in to your [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** -> **Blueprint**.
4. Connect your GitHub repository containing `render.yaml`.
5. Render will automatically detect `render.yaml`, set up the Python web service, install dependencies, and launch `gunicorn run:app`.

### Option B: Manual Web Service Deployment
1. Click **New +** -> **Web Service** on Render.
2. Select your repository.
3. Configure the following deployment settings:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
4. Add Environment Variables:
   - `SECRET_KEY`: (A random secret string)
   - `DATABASE_URL`: (Optional - attach a Render PostgreSQL database string if desired)
5. Click **Create Web Service**.

---

## License & Support

Distributed under the MIT License. Feel free to modify and customize for your productivity needs!
