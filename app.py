from flask import Flask, render_template, request, redirect, url_for
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone
from collections import defaultdict
import requests
import os
from dotenv import load_dotenv
from jira_functions import compare_assignees
from jira_bugs_report import get_all_bugs, summarize_bugs
from project_dashboard import (
    get_projects_summary, get_project_detail,
    get_mtc_summary, get_mtc_detail,
    get_all_assignees, get_all_leaders, get_all_managers
)
from jira_fetcher import fetch_all_issues, DB_PATH
import sqlite3
from leaderboard_dashboard import (
    get_top10_task_uat, get_top10_bugs_uat,
    get_top10_bugs_mtc, get_team_detail
)
from inprogress_dashboard import get_inprogress_summary
from leader_view import get_leader_view, get_all_leaders, get_available_months, get_export_data

load_dotenv()

app = Flask(__name__)

JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
headers = {"Accept": "application/json"}


def now_str():
    return datetime.now().strftime("%d %b %Y, %H:%M")


def jira_search(jql, fields="summary,status,assignee,priority,created,updated,issuetype,project", max_results=200):
    url = f"{JIRA_URL}/rest/api/3/search"
    all_issues = []
    start = 0
    while True:
        res = requests.get(url, headers=headers, auth=auth, params={
            "jql": jql, "maxResults": min(100, max_results - start),
            "startAt": start, "fields": fields
        })
        data = res.json()
        issues = data.get("issues", [])
        all_issues.extend(issues)
        start += len(issues)
        if start >= data.get("total", 0) or len(all_issues) >= max_results:
            break
    return all_issues


def get_bug_count():
    issues = jira_search('issuetype = Bug AND statusCategory != Done ORDER BY created DESC', max_results=1)
    return len(issues) if issues else 0


def days_since(date_str):
    try:
        dt = datetime.fromisoformat(date_str[:19]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0


# ─────────────────────────────────────────────
# 1. STATUS DAILY
# ─────────────────────────────────────────────
@app.route("/")
@app.route("/status-daily")
def status_daily():
    jql = "assignee IN (membersOf('BPI ES'), membersOf('BPI BS')) AND status IN ('SUPPORT INPROGRESS', 'MTC - UAT In Progress', 'UAT In Progress')"
    
    issues = jira_search(jql, max_results=200)

    status_count = defaultdict(int)
    for issue in issues:
        status_count[issue["fields"]["status"]["name"]] += 1

    # Compare assignees
    comparison = compare_assignees([
        "SUPPORT INPROGRESS",
        "MTC - UAT In Progress",
        "UAT In Progress",
    ])

    return render_template("status_daily.html",
        issues=issues[:50],
        status_count=dict(status_count),
        total=len(issues),
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
        not_in_jira=comparison["not_in_jira"],   # Di list, TIDAK di Jira
        not_in_list=comparison["not_in_list"],   # Di Jira, TIDAK di list
        list_names=comparison["list_names"],
        jira_names=comparison["jira_names"],
    )


# ─────────────────────────────────────────────
# 2. BUGS
# ─────────────────────────────────────────────
@app.route("/bugs-report")
def bugs_report():
    menu = request.args.get("menu", "NON-MTC")
    bugs    = get_all_bugs(menu=menu)
    summary = summarize_bugs(bugs)

    return render_template("bugs_report.html",
        bugs=bugs,
        summary=summary,
        menu=menu,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )


# ─────────────────────────────────────────────
# 3. IN PROGRESS > 1 HARI
# ─────────────────────────────────────────────
@app.route("/inprogress")
def inprogress():
    # Ganti JQL sesuai kebutuhan
    jql = 'status = "In Progress" AND updated <= "-1d" ORDER BY updated ASC'
    issues = jira_search(jql, max_results=200)

    for issue in issues:
        issue["days_in_progress"] = days_since(issue["fields"]["updated"])

    issues.sort(key=lambda x: x["days_in_progress"], reverse=True)

    max_days = max((i["days_in_progress"] for i in issues), default=0)
    avg_days = round(sum(i["days_in_progress"] for i in issues) / len(issues), 1) if issues else 0

    return render_template("inprogress.html",
        issues=issues,
        max_days=max_days,
        avg_days=avg_days,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str()
    )

# ─────────────────────────────────────────────
# 4. LEADERBOARD BY PROJECT
# ─────────────────────────────────────────────
@app.route("/leaderboard-project")
def leaderboard_project():
    # Ganti JQL sesuai kebutuhan
    jql = "project in (MUF, DEV) ORDER BY project ASC"
    issues = jira_search(jql, max_results=500)

    proj_map = defaultdict(lambda: {
        "name": "", "key": "", "total": 0, "done": 0,
        "in_progress": 0, "bugs": 0, "members": defaultdict(lambda: {"done": 0, "total": 0})
    })

    for issue in issues:
        proj_key = issue["fields"]["project"]["key"]
        proj_name = issue["fields"]["project"]["name"]
        status = issue["fields"]["status"]["name"]
        assignee = (issue["fields"].get("assignee") or {}).get("displayName", "Unassigned")
        itype = issue["fields"]["issuetype"]["name"]

        p = proj_map[proj_key]
        p["name"] = proj_name
        p["key"] = proj_key
        p["total"] += 1
        p["members"][assignee]["total"] += 1

        if status == "Done":
            p["done"] += 1
            p["members"][assignee]["done"] += 1
        elif status == "In Progress":
            p["in_progress"] += 1
        if itype == "Bug":
            p["bugs"] += 1

    projects = []
    for proj in proj_map.values():
        proj["done_pct"] = round((proj["done"] / proj["total"]) * 100) if proj["total"] else 0
        members = []
        max_done = max((m["done"] for m in proj["members"].values()), default=1) or 1
        for name, stats in sorted(proj["members"].items(), key=lambda x: -x[1]["done"]):
            members.append({"name": name, "done": stats["done"], "total": stats["total"],
                            "pct": round((stats["done"] / max_done) * 100)})
        proj["members"] = members
        projects.append(proj)

    projects.sort(key=lambda x: -x["done_pct"])

    return render_template("leaderboard_project.html",
        projects=projects,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str()
    )


# ─────────────────────────────────────────────
# 5. LEADERBOARD TOP 10
# ─────────────────────────────────────────────
@app.route("/leaderboard-top10")
def leaderboard_top10():
    # Ganti JQL sesuai kebutuhan
    jql = "project in (MUF, DEV) AND created >= -30d"
    issues = jira_search(jql, max_results=500)

    member_map = defaultdict(lambda: {"done": 0, "in_progress": 0, "total": 0})
    for issue in issues:
        name = (issue["fields"].get("assignee") or {}).get("displayName", "Unassigned")
        status = issue["fields"]["status"]["name"]
        member_map[name]["total"] += 1
        if status == "Done":
            member_map[name]["done"] += 1
        elif status == "In Progress":
            member_map[name]["in_progress"] += 1

    ranked = sorted(member_map.items(), key=lambda x: -x[1]["done"])[:10]
    max_score = ranked[0][1]["done"] if ranked else 1

    top10 = []
    for i, (name, stats) in enumerate(ranked, 1):
        stats["name"] = name
        stats["score"] = stats["done"]
        stats["score_pct"] = round((stats["done"] / max_score) * 100) if max_score else 0
        top10.append((i, stats))

    chart_data = {
        "labels": [m["name"].split()[-1] for _, m in top10],
        "done": [m["done"] for _, m in top10],
        "in_progress": [m["in_progress"] for _, m in top10]
    }

    return render_template("leaderboard_top10.html",
        top10=top10,
        chart_data=chart_data,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str()
    )


# ─────────────────────────────────────────────
# 6. PRODUKTIVITAS
# ─────────────────────────────────────────────
@app.route("/productivity")
def productivity():
    # Ganti JQL sesuai kebutuhan
    jql_30d = 'status changed to Done AFTER "-30d" ORDER BY updated DESC'
    done_issues = jira_search(jql_30d, fields="summary,status,assignee,updated", max_results=500)

    done_30d = len(done_issues)
    done_7d = sum(1 for i in done_issues if days_since(i["fields"]["updated"]) <= 7)
    avg_per_day = round(done_30d / 30, 1)
    velocity = round(done_30d / 4, 1)

    # Tren per hari (30 hari)
    from datetime import timedelta
    day_count = defaultdict(int)
    for issue in done_issues:
        day = issue["fields"]["updated"][:10]
        day_count[day] += 1

    today = datetime.now()
    labels, values = [], []
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append((today - timedelta(days=i)).strftime("%d/%m"))
        values.append(day_count.get(d, 0))

    trend_data = {"labels": labels, "values": values}

    # Produktivitas per member
    member_done = defaultdict(int)
    for issue in done_issues:
        name = (issue["fields"].get("assignee") or {}).get("displayName", "Unassigned")
        member_done[name] += 1

    top_members = sorted(member_done.items(), key=lambda x: -x[1])[:8]
    max_done = top_members[0][1] if top_members else 1
    member_stats = [{"name": n, "done": d, "pct": round((d / max_done) * 100)} for n, d in top_members]

    return render_template("productivity.html",
        done_30d=done_30d,
        done_7d=done_7d,
        avg_per_day=avg_per_day,
        velocity=velocity,
        trend_data=trend_data,
        member_stats=member_stats,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str()
    )


# ─────────────────────────────────────────────
# 7. MONITORING PROJECT
# ─────────────────────────────────────────────
@app.route("/project")
def project():
    # Ganti JQL sesuai kebutuhan
    jql = "project in (MUF, DEV) ORDER BY project ASC"
    issues = jira_search(jql, max_results=500)

    proj_map = defaultdict(lambda: {
        "name": "", "key": "", "total": 0, "done": 0, "in_progress": 0, "bugs": 0
    })
    for issue in issues:
        pk = issue["fields"]["project"]["key"]
        p = proj_map[pk]
        p["name"] = issue["fields"]["project"]["name"]
        p["key"] = pk
        p["total"] += 1
        status = issue["fields"]["status"]["name"]
        if status == "Done":
            p["done"] += 1
        elif status == "In Progress":
            p["in_progress"] += 1
        if issue["fields"]["issuetype"]["name"] == "Bug":
            p["bugs"] += 1

    projects = []
    for proj in proj_map.values():
        proj["done_pct"] = round((proj["done"] / proj["total"]) * 100) if proj["total"] else 0
        projects.append(proj)
    projects.sort(key=lambda x: -x["done_pct"])

    return render_template("project.html",
        projects=projects,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str()
    )

@app.route("/project-dashboard")
def project_dashboard():
    tab             = request.args.get("tab", "project")
    name_filter     = request.args.get("name", "")
    assignee_filter = request.args.get("assignee", "")
    leader_filter   = request.args.get("leader", "")
    manager_filter  = request.args.get("manager", "")

    if tab == "mtc":
        projects = []
        mtcs     = get_mtc_summary(name_filter, assignee_filter, leader_filter, manager_filter)
    else:
        tab      = "project"
        projects = get_projects_summary(name_filter, assignee_filter, leader_filter, manager_filter)
        mtcs     = []

    return render_template("project_dashboard.html",
        tab=tab,
        projects=projects,
        mtcs=mtcs,
        all_assignees=get_all_assignees(),
        all_leaders=get_all_leaders(),
        all_managers=get_all_managers(),
        name_filter=name_filter,
        assignee_filter=assignee_filter,
        leader_filter=leader_filter,
        manager_filter=manager_filter,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )


@app.route("/project-dashboard/project/<path:project_name>")
def project_detail(project_name):
    detail = get_project_detail(project_name)
    return render_template("project_detail.html",
        detail=detail,
        mode="project",
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )


@app.route("/project-dashboard/mtc/<path:parent_key>")
def mtc_detail(parent_key):
    detail = get_mtc_detail(parent_key)
    return render_template("project_detail.html",
        detail=detail,
        mode="mtc",
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )

@app.route("/refresh")
def refresh():
    fetch_all_issues()
    return redirect(request.referrer or url_for('status_daily'))

def now_str():
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute(
            "SELECT fetched_at FROM fetch_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        if row:
            # Format: 2026-06-27T10:30:00.123456 → 27 Jun 2026, 10:30
            return datetime.fromisoformat(row[0]).strftime("%d %b %Y, %H:%M")
    except Exception:
        pass
    return datetime.now().strftime("%d %b %Y, %H:%M")

@app.route("/leaderboard-dashboard")
def leaderboard_dashboard():
    top10_task = get_top10_task_uat()
    top10_bugs_uat = get_top10_bugs_uat()
    top10_bugs_mtc = get_top10_bugs_mtc()
    team = get_team_detail()
 
    return render_template("leaderboard_dashboard.html",
        top10_task=top10_task,
        top10_bugs_uat=top10_bugs_uat,
        top10_bugs_mtc=top10_bugs_mtc,
        team=team,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )

@app.route("/inprogress-dashboard")
def inprogress_dashboard():
    summary, all_data = get_inprogress_summary()
 
    return render_template("inprogress_dashboard.html",
        summary=summary,
        all_data=all_data,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )

@app.route("/leader-view")
def leader_view():
    leader_filter    = request.args.get("leader", "")
    month_filter     = request.args.get("month", "")
    leaders_data     = get_leader_view(leader_filter, month_filter)
    all_leaders      = get_all_leaders()
    available_months = get_available_months()

    return render_template("leader_view.html",
        leaders_data=leaders_data,
        all_leaders=all_leaders,
        available_months=available_months,
        leader_filter=leader_filter,
        month_filter=month_filter,
        bug_count=get_bug_count(),
        jira_url=JIRA_URL,
        now=now_str(),
    )


@app.route("/leader-view/export")
def leader_view_export():
    import json
    leader_filter = request.args.get("leader", "")
    month_filter  = request.args.get("month", "")
    data          = get_export_data(leader_filter, month_filter)
    return json.dumps(data, ensure_ascii=False)
 
 

if __name__ == "__main__":
    app.run(debug=True)