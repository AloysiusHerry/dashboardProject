import sqlite3
from collections import defaultdict
from staff_mapping import STAFF_MAPPING, LEADER_MAPPING

DB_PATH = "jira_data.db"

# Status group UAT dan bugs
UAT_GROUPS     = {"UAT"}
UAT_BUGS_GROUP = {"UAT_BUGS"}
MTC_BUGS_GROUP = {"MTC_BUGS"}

UAT_STATUSES = [
    "UAT Open", "UAT In Progress", "UAT Hold", "HOLD UAT",
    "UAT Done", "UAT Drop", "Done UAT", "Open",
]
UAT_BUGS_STATUSES = [
    "UAT Open.", "UAT Done.", "BUGS Open",
]
MTC_BUGS_STATUSES = [
    "MTC BUG - UAT In Progress", "MTC BUG - UAT Done", "MTC BUG - Invalid",
]


def query_db(sql: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


# ─────────────────────────────────────────────
# TOP 10
# ─────────────────────────────────────────────
def get_top10_task_uat() -> list[dict]:
    """Top 10 assignee by total UAT task (semua status)."""
    placeholders = ",".join("?" * len(UAT_STATUSES))
    rows = query_db(
        f"""
        SELECT assignee, COUNT(*) as total
        FROM issues
        WHERE status IN ({placeholders})
        AND assignee IS NOT NULL
        AND assignee != 'Unassigned'
        GROUP BY assignee
        ORDER BY total DESC
        LIMIT 10
        """,
        tuple(UAT_STATUSES)
    )
    return [{"rank": i+1, "name": r["assignee"], "total": r["total"]} for i, r in enumerate(rows)]


def get_top10_bugs_uat() -> list[dict]:
    """Top 10 reporter by total UAT bugs (semua status)."""
    placeholders = ",".join("?" * len(UAT_BUGS_STATUSES))
    rows = query_db(
        f"""
        SELECT reporter, COUNT(*) as total
        FROM issues
        WHERE status IN ({placeholders})
        AND reporter IS NOT NULL
        AND reporter != 'Unassigned'
        GROUP BY reporter
        ORDER BY total DESC
        LIMIT 10
        """,
        tuple(UAT_BUGS_STATUSES)
    )
    return [{"rank": i+1, "name": r["reporter"], "total": r["total"]} for i, r in enumerate(rows)]


def get_top10_bugs_mtc() -> list[dict]:
    """Top 10 reporter by total MTC bugs (semua status)."""
    placeholders = ",".join("?" * len(MTC_BUGS_STATUSES))
    rows = query_db(
        f"""
        SELECT reporter, COUNT(*) as total
        FROM issues
        WHERE status IN ({placeholders})
        AND reporter IS NOT NULL
        AND reporter != 'Unassigned'
        GROUP BY reporter
        ORDER BY total DESC
        LIMIT 10
        """,
        tuple(MTC_BUGS_STATUSES)
    )
    return [{"rank": i+1, "name": r["reporter"], "total": r["total"]} for i, r in enumerate(rows)]


# ─────────────────────────────────────────────
# DETAIL TIM — semua member dari staff_mapping
# ─────────────────────────────────────────────
def get_team_detail() -> list[dict]:
    """
    Detail semua member dari staff_mapping:
    total task UAT, bugs UAT, bugs MTC, done%, leader, manager
    """
    # Ambil semua issue relevan dari DB sekaligus
    all_statuses = UAT_STATUSES + UAT_BUGS_STATUSES + MTC_BUGS_STATUSES
    placeholders = ",".join("?" * len(all_statuses))

    rows = query_db(
        f"""
        SELECT assignee, reporter, status
        FROM issues
        WHERE status IN ({placeholders})
        """,
        tuple(all_statuses)
    )

    UAT_DONE = {"UAT Done", "Done UAT"}
    UAT_BUGS_DONE = {"UAT Done."}
    MTC_BUGS_DONE = {"MTC BUG - UAT Done"}

    # Build per-member stats
    member_stats = defaultdict(lambda: {
        "task_uat":       0,
        "task_uat_done":  0,
        "bugs_uat":       0,
        "bugs_mtc":       0,
    })

    for row in rows:
        status   = row["status"] or ""
        assignee = row["assignee"] or ""
        reporter = row["reporter"] or ""

        # Task UAT — by assignee
        if status in UAT_STATUSES and assignee and assignee != "Unassigned":
            member_stats[assignee]["task_uat"] += 1
            if status in UAT_DONE:
                member_stats[assignee]["task_uat_done"] += 1

        # Bugs UAT — by reporter
        if status in UAT_BUGS_STATUSES and reporter and reporter != "Unassigned":
            member_stats[reporter]["bugs_uat"] += 1

        # Bugs MTC — by reporter
        if status in MTC_BUGS_STATUSES and reporter and reporter != "Unassigned":
            member_stats[reporter]["bugs_mtc"] += 1

    # Build result dari staff_mapping
    result = []
    for staff_name, info in STAFF_MAPPING.items():
        stats    = member_stats.get(staff_name, {})
        task_uat = stats.get("task_uat", 0)
        done     = stats.get("task_uat_done", 0)
        done_pct = round((done / task_uat) * 100) if task_uat else 0

        result.append({
            "name":      staff_name,
            "leader":    info["leader"],
            "manager":   info["manager"],
            "task_uat":  task_uat,
            "done":      done,
            "done_pct":  done_pct,
            "bugs_uat":  stats.get("bugs_uat", 0),
            "bugs_mtc":  stats.get("bugs_mtc", 0),
        })

    # Sort by task_uat desc
    result.sort(key=lambda x: -x["task_uat"])
    return result
