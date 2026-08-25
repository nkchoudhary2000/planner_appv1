import json
import logging
from datetime import datetime
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

def fetch_monthly_github_commits(username: str, year: int, month: int) -> dict:
    """
    Fetches public GitHub commit activity for a given user and target month.
    
    Returns a dictionary containing:
      - success: bool
      - username: str
      - year: int
      - month: int
      - daily_counts: dict of day strings to commit counts e.g. {"1": 2, "25": 5}
      - total_commits: int
      - active_days: list of day integers e.g. [1, 25]
      - message: str
    """
    clean_username = (username or '').strip()
    if not clean_username:
        return {
            'success': False,
            'message': 'GitHub username is required.',
            'daily_counts': {},
            'total_commits': 0,
            'active_days': []
        }

    daily_counts = {}
    target_year = int(year)
    target_month = int(month)

    headers = {
        'User-Agent': 'PlannerApp-GitHubSync/1.0',
        'Accept': 'application/vnd.github.v3+json'
    }

    try:
        # Fetch up to 3 pages (up to 300 recent public events)
        for page in range(1, 4):
            url = f"https://api.github.com/users/{clean_username}/events?per_page=100&page={page}"
            req = urllib.request.Request(url, headers=headers)
            
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        break
                    data = json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {
                        'success': False,
                        'message': f"GitHub user '{clean_username}' was not found.",
                        'daily_counts': {},
                        'total_commits': 0,
                        'active_days': []
                    }
                elif e.code == 403:
                    return {
                        'success': False,
                        'message': "GitHub API rate limit exceeded. Please try again later.",
                        'daily_counts': {},
                        'total_commits': 0,
                        'active_days': []
                    }
                else:
                    logger.warning(f"GitHub API returned HTTP {e.code} for {clean_username}: {e.reason}")
                    break

            if not data or not isinstance(data, list):
                break

            reached_older_month = False
            for event in data:
                created_at_str = event.get('created_at', '')
                if not created_at_str:
                    continue

                try:
                    # ISO-8601 parsing (e.g. 2026-08-25T07:15:30Z)
                    event_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        event_dt = datetime.strptime(created_at_str[:19], "%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        continue

                # Check date boundary
                if (event_dt.year < target_year) or (event_dt.year == target_year and event_dt.month < target_month):
                    reached_older_month = True
                    break

                if event_dt.year == target_year and event_dt.month == target_month:
                    event_type = event.get('type')
                    if event_type == 'PushEvent':
                        payload = event.get('payload') or {}
                        commits = payload.get('commits', [])
                        # Use commit list length, or payload size, fallback to 1
                        commit_count = len(commits) if commits else payload.get('size', 1)
                        if commit_count <= 0:
                            commit_count = 1

                        day_key = str(event_dt.day)
                        daily_counts[day_key] = daily_counts.get(day_key, 0) + commit_count

            if reached_older_month or len(data) < 100:
                break

        total_commits = sum(daily_counts.values())
        active_days = sorted([int(d) for d in daily_counts.keys()])

        return {
            'success': True,
            'username': clean_username,
            'year': target_year,
            'month': target_month,
            'daily_counts': daily_counts,
            'total_commits': total_commits,
            'active_days': active_days,
            'message': f"Synced {total_commits} commits across {len(active_days)} active days in {target_month}/{target_year}."
        }

    except urllib.error.URLError as e:
        logger.error(f"Network error contacting GitHub API: {e}")
        return {
            'success': False,
            'message': f"Network error connecting to GitHub: {e.reason}",
            'daily_counts': {},
            'total_commits': 0,
            'active_days': []
        }
    except Exception as e:
        logger.error(f"Unexpected error in GitHub commit fetch: {e}")
        return {
            'success': False,
            'message': f"Error fetching GitHub commits: {str(e)}",
            'daily_counts': {},
            'total_commits': 0,
            'active_days': []
        }
