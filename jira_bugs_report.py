import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from datetime import date
from collections import defaultdict

load_dotenv()

JIRA_URL   = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")

auth    = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
headers = {"Accept": "application/json"}

FIELDS = "parent,summary,status,assignee,reporter,project,customfield_10206,customfield_10207,customfield_10203"


def parse_jira_date(val) -> date | None:
    """Parse tanggal dari customfield Jira (bisa string ISO atau None)."""
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return None


def get_all_bugs(menu: str = "NON-MTC", max_hits: int = 200) -> list[dict]:
    if menu == "MTC":
        issue_type = "Subtask MTC [BUG]"
    else:
        issue_type = "Subtask Bug"

    jql = (
        f'created >= startOfYear() '
        f'AND type IN ("{issue_type}") '
        f'AND reporter IN (membersOf("BPI ES"), membersOf("BPI BS"))'
    )

    url        = f"{JIRA_URL}/rest/api/3/search/jql"
    all_issues = []
    next_token = None
    api_hit    = 0

    while True:
        api_hit += 1
        params = {
            "jql":        jql,
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

        all_issues.extend(issues)
        print(f"[DEBUG] Hit #{api_hit} — total: {len(all_issues)}")

        is_last    = data.get("isLast", True)
        next_token = data.get("nextPageToken")

        if is_last or not next_token or api_hit >= max_hits:
            break

    print(f"[DEBUG] Selesai — total {len(all_issues)} issues")

    result = []
    for issue in all_issues:
        fields   = issue.get("fields", {})
        parent   = fields.get("parent") or {}
        project  = fields.get("project") or {}
        reporter = fields.get("reporter") or {}

        create = parse_jira_date(fields.get("customfield_10206"))
        start  = parse_jira_date(fields.get("customfield_10207"))
        end    = parse_jira_date(fields.get("customfield_10203"))

        # Sama persis dengan Groovy: end ?: start ?: create
        base = end or start or create

        # Sama persis dengan Groovy: if (!base) return
        if not base:
            continue
        
        for i, issue in enumerate(all_issues[:5]):
            fields = issue.get("fields", {})

            print("=" * 50)
            print("Issue:", issue.get("key"))
            print("10206:", fields.get("customfield_10206"))
            print("10207:", fields.get("customfield_10207"))
            print("10203:", fields.get("customfield_10203"))
            print("Available fields:", list(fields.keys()))
            
        result.append({
            "mtc_no":       parent.get("key", "-"),
            "mtc_name":     (parent.get("fields") or {}).get("summary", "-"),
            "project_no":   project.get("key", "-"),
            "project_name": project.get("name", "-"),
            "status":       (fields.get("status") or {}).get("name", "UNKNOWN"),
            "uat_reporter": reporter.get("displayName", "Unassigned"),
            "year_month":   base.strftime("%Y-%m")
        })

    print(f"[DEBUG] Result: {len(result)} items")
    return result
    
def summarize_bugs(bugs: list[dict]) -> dict:
    """Buat summary untuk kebutuhan tampilan dashboard."""
    total        = len(bugs)
    by_status    = defaultdict(int)
    by_project   = defaultdict(int)
    by_reporter  = defaultdict(int)
    by_yearmonth = defaultdict(int)

    for b in bugs:
        by_status[b["status"]]         += 1
        by_project[b["project_name"]]  += 1
        by_reporter[b["uat_reporter"]] += 1
        by_yearmonth[b["year_month"]]  += 1

    # Urutkan yearMonth ascending
    by_yearmonth_sorted = dict(sorted(by_yearmonth.items()))

    return {
        "total":             total,
        "by_status":         dict(by_status),
        "by_project":        dict(sorted(by_project.items(), key=lambda x: -x[1])),
        "by_reporter":       dict(sorted(by_reporter.items(), key=lambda x: -x[1])),
        "by_yearmonth":      by_yearmonth_sorted,
    }


if __name__ == "__main__":
    bugs    = get_all_bugs(menu="NON-MTC")
    summary = summarize_bugs(bugs)
    print(f"\nTotal bugs  : {summary['total']}")
    print(f"By status   : {summary['by_status']}")
    print(f"By project  : {summary['by_project']}")
    print(f"By reporter : {summary['by_reporter']}")
    print(f"By month    : {summary['by_yearmonth']}")