import os
import requests
import sqlite3
import time
from datetime import datetime
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from staff_mapping import STAFF_MAPPING

load_dotenv()

JIRA_URL   = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")

auth    = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
headers = {"Accept": "application/json"}

DB_PATH = "jira_data.db"

FIELDS = ",".join([
    "key",
    "summary",
    "status",
    "assignee",
    "reporter",
    "project",
    "parent",
    "created",
    "updated",
    "customfield_10206",  # bugs_open_date
    "customfield_10207",  # plan_start_date
    "customfield_10208",  # plan_end_date
    "customfield_10203",  # actual_end_dev_done
    "customfield_10008",  # actual_start_date
    "customfield_10009",  # actual_end_date
    "customfield_10243",  # actual_duration_hours
])

JQL = (
    'assignee IN (membersOf("BPI ES"), membersOf("BPI BS")) '
    'AND created >= startOfYear()'
)


# ─────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            key                   TEXT PRIMARY KEY,
            summary               TEXT,
            status                TEXT,
            assignee              TEXT,
            reporter              TEXT,
            leader                TEXT,
            manager               TEXT,
            project_key           TEXT,
            project_name          TEXT,
            parent_key            TEXT,
            parent_summary        TEXT,
            created               TEXT,
            updated               TEXT,
            bugs_open_date        TEXT,
            plan_start_date       TEXT,
            plan_end_date         TEXT,
            actual_end_dev_done   TEXT,
            actual_start_date     TEXT,
            actual_end_date       TEXT,
            actual_duration_hours REAL,
            fetched_at            TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fetch_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            total      INTEGER,
            duration_s REAL,
            fetched_at TEXT
        )
    """)
    con.commit()
    con.close()
    print("[DB] Initialized")


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────
def parse_date(val) -> str | None:
    """Ambil YYYY-MM-DD dari berbagai format datetime Jira."""
    if not val:
        return None
    try:
        s = str(val).strip()
        
        # Format ISO: 2026-06-24T10:00:00.000+0700
        if s[0].isdigit() and "T" in s:
            return s[:10]
        
        # Format Jira custom: 24/Jun/2026 05:00 PM
        if "/" in s:
            return datetime.strptime(s, "%d/%b/%Y %I:%M %p").strftime("%Y-%m-%d")
        
        # Format date only: 2026-06-24
        return s[:10]

    except Exception as e:
        print(f"[parse_date] GAGAL: {val!r} → {e}")
        return None


def parse_float(val) -> float | None:
    """Parse nilai float dari customfield."""
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


def map_issue(issue: dict) -> dict:
    """Mapping raw issue dari Jira ke struktur DB."""
    f        = issue.get("fields", {})
    assignee = f.get("assignee") or {}
    reporter = f.get("reporter") or {}
    project  = f.get("project") or {}
    parent   = f.get("parent") or {}

    assignee_name = assignee.get("displayName", "Unassigned")
    staff_info    = STAFF_MAPPING.get(assignee_name, {})

    return {
        "key":                   issue.get("key"),
        "summary":               f.get("summary"),
        "status":                (f.get("status") or {}).get("name", "UNKNOWN"),
        "assignee":              assignee_name,
        "reporter":              reporter.get("displayName", "Unassigned"),
        "leader":                staff_info.get("leader", "Unassigned"),
        "manager":               staff_info.get("manager", "Unassigned"),
        "project_key":           project.get("key"),
        "project_name":          project.get("name"),
        "parent_key":            parent.get("key"),
        "parent_summary":        (parent.get("fields") or {}).get("summary"),
        "created":               parse_date(f.get("created")),
        "updated":               parse_date(f.get("updated")),
        "bugs_open_date":        parse_date(f.get("customfield_10206")),
        "plan_start_date":       parse_date(f.get("customfield_10207")),
        "plan_end_date":         parse_date(f.get("customfield_10208")),
        "actual_end_dev_done":   parse_date(f.get("customfield_10203")),
        "actual_start_date":     parse_date(f.get("customfield_10008")),
        "actual_end_date":       parse_date(f.get("customfield_10009")),
        "actual_duration_hours": parse_float(f.get("customfield_10243")),
        "fetched_at":            datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────
def save_to_db(issues: list[dict]):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.executemany("""
        INSERT INTO issues VALUES (
            :key, :summary, :status, :assignee, :reporter, :leader, :manager, 
            :project_key, :project_name, :parent_key, :parent_summary,
            :created, :updated,
            :bugs_open_date, :plan_start_date, :plan_end_date,
            :actual_end_dev_done, :actual_start_date, :actual_end_date,
            :actual_duration_hours, :fetched_at
        )
        ON CONFLICT(key) DO UPDATE SET
            summary               = excluded.summary,
            status                = excluded.status,
            assignee              = excluded.assignee,
            reporter              = excluded.reporter,
            project_key           = excluded.project_key,
            project_name          = excluded.project_name,
            parent_key            = excluded.parent_key,
            parent_summary        = excluded.parent_summary,
            created               = excluded.created,
            updated               = excluded.updated,
            bugs_open_date        = excluded.bugs_open_date,
            plan_start_date       = excluded.plan_start_date,
            plan_end_date         = excluded.plan_end_date,
            actual_end_dev_done   = excluded.actual_end_dev_done,
            actual_start_date     = excluded.actual_start_date,
            actual_end_date       = excluded.actual_end_date,
            actual_duration_hours = excluded.actual_duration_hours,
            leader                = excluded.leader,
            manager               = excluded.manager,
            fetched_at            = excluded.fetched_at
    """, issues)

    con.commit()
    con.close()


# ─────────────────────────────────────────────
# FETCH
# ─────────────────────────────────────────────
def fetch_all_issues() -> int:
    """
    Fetch semua issue dari Jira berdasarkan JQL,
    simpan ke SQLite dengan upsert.
    Returns total issue yang berhasil disimpan.
    """
    url        = f"{JIRA_URL}/rest/api/3/search/jql"
    all_mapped = []
    next_token = None
    api_hit    = 0
    start_time = time.time()

    print(f"[FETCH] Mulai fetch — JQL: {JQL[:60]}...")

    while True:
        api_hit += 1
        params = {
            "jql":        JQL,
            "maxResults": 100,
            "fields":     FIELDS,
        }
        if next_token:
            params["nextPageToken"] = next_token

        res = requests.get(url, headers=headers, auth=auth, params=params)

        if res.status_code != 200:
            print(f"[ERROR] {res.status_code}: {res.text}")
            break

        data   = res.json()
        issues = data.get("issues", [])

        if not issues:
            break

        # Mapping dan langsung save per batch 100
        mapped = [map_issue(i) for i in issues]
        save_to_db(mapped)
        all_mapped.extend(mapped)

        print(f"[FETCH] Hit #{api_hit} — total tersimpan: {len(all_mapped)}")

        next_token = data.get("nextPageToken")
        is_last    = data.get("isLast", True)

        if is_last or not next_token or api_hit >= 1000:
            break

    duration = round(time.time() - start_time, 2)

    # Log hasil fetch
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO fetch_log (total, duration_s, fetched_at) VALUES (?,?,?)",
        (len(all_mapped), duration, datetime.now().isoformat())
    )
    con.commit()
    con.close()

    print(f"[DONE] {len(all_mapped)} issues dalam {duration}s")
    return len(all_mapped)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    fetch_all_issues()