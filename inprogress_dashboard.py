import sqlite3
from collections import defaultdict

DB_PATH = "jira_data.db"

INPROGRESS_STATUSES = {
    "UAT":        "UAT In Progress",
    "Support":    "SUPPORT INPROGRESS",
    "MTC":        "MTC - UAT In Progress",
    "Daily Task": "Daily Task In Progress",
}


def query_db(sql: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def get_inprogress_by_group(group: str) -> list[dict]:
    """
    Ambil assignee yang punya > 1 task di status inprogress group tertentu.
    Returns list of dict: { name, total, tasks: [{key, summary}] }
    """
    status = INPROGRESS_STATUSES.get(group)
    if not status:
        return []

    rows = query_db(
        """
        SELECT assignee, key, summary
        FROM issues
        WHERE status = ?
        AND assignee IS NOT NULL
        AND assignee != 'Unassigned'
        ORDER BY assignee, key
        """,
        (status,)
    )

    # Group by assignee
    assignee_map = defaultdict(list)
    for row in rows:
        assignee_map[row["assignee"]].append({
            "key":     row["key"],
            "summary": row["summary"] or "-",
        })

    # Filter hanya yang > 1 task
    result = []
    for name, tasks in assignee_map.items():
        if len(tasks) > 1:
            result.append({
                "name":  name,
                "total": len(tasks),
                "tasks": tasks,
            })

    result.sort(key=lambda x: -x["total"])
    return result


def get_all_inprogress() -> dict:
    """Ambil semua group sekaligus."""
    return {
        group: get_inprogress_by_group(group)
        for group in INPROGRESS_STATUSES
    }


def get_inprogress_summary() -> dict:
    """Summary count per group untuk stat cards."""
    all_data = get_all_inprogress()
    return {
        group: {
            "pic_count":  len(items),
            "task_count": sum(i["total"] for i in items),
        }
        for group, items in all_data.items()
    }, all_data
