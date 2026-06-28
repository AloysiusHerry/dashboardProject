import sqlite3
from collections import defaultdict

DB_PATH = "jira_data.db"

# ─────────────────────────────────────────────
# STATUS GROUPING
# ─────────────────────────────────────────────
STATUS_GROUPS = {
    "UAT": [
        "UAT Open", "UAT In Progress",
        "UAT Hold", "HOLD UAT", "UAT Done",
        "Done UAT", "Open",
    ],
    "UAT_BUGS": [
        "UAT Open.", "UAT Done.", "BUGS Open",
    ],
    "MTC": [
        "MTC- UAT Open", "MTC - UAT In Progress", "MTC - UAT Hold",
        "MTC - UAT Done",
    ],
    "MTC_BUGS": [
        "MTC BUG - UAT In Progress",
        "MTC BUG - UAT Done", "MTC BUG - Invalid",
    ],
    "Support": [
        "SUPPORT OPEN", "SUPPORT INPROGRESS", "SUPPORT HOLD",
        "SUPPORT DONE",
    ],
    "OPR": [
        "OPR Open", "OPR Done", "OPR Done.",
    ],
    "Daily Task": [
        "Daily Task Open", "Daily Task In Progress", "Daily Task Hold",
        "Daily Task Done", "Daily Task Drop",
    ],
}

STATUS_TO_GROUP = {}
for group, statuses in STATUS_GROUPS.items():
    for s in statuses:
        STATUS_TO_GROUP[s] = group

DONE_STATUSES = {
    # UAT
    "UAT Done", "Done UAT",
    # UAT Bugs
    "UAT Done.",
    # MTC
    "MTC - UAT Done",
    # MTC Bugs
    "MTC BUG - UAT Done",
    # Support
    "SUPPORT DONE",
    # OPR
    "OPR Done", "OPR Done.",
    # Daily Task
    "Daily Task Done",
}

BUGS_GROUPS    = {"UAT_BUGS", "MTC_BUGS"}
BUGS_DONE      = {"UAT Done.", "MTC BUG - UAT Done"}
BUGS_INPROGRESS_EXCLUDE = BUGS_DONE


# ─────────────────────────────────────────────
# HELPER DB
# ─────────────────────────────────────────────
def query_db(sql: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def get_all_assignees() -> list[str]:
    rows = query_db(
        "SELECT DISTINCT assignee FROM issues WHERE assignee IS NOT NULL ORDER BY assignee"
    )
    return [r["assignee"] for r in rows]


# ─────────────────────────────────────────────
# SHARED — hitung stats level 1
# ─────────────────────────────────────────────
def _build_summary(rows: list[dict], name_key: str, key_key: str) -> list[dict]:
    item_map = defaultdict(lambda: {
        "name":          "",
        "key":           "",
        "total":         0,
        "done":          0,
        "total_mtc":     0,
        "total_uat":     0,
        "bugs_done":     0,
        "bugs_inprog":   0,
        "groups":        defaultdict(int),
        "assignees":     set(),
    })

    for row in rows:
        name   = row.get(name_key) or "Unknown"
        d      = item_map[name]
        status = row.get("status") or ""
        group  = STATUS_TO_GROUP.get(status, "Lainnya")

        d["name"]  = name
        d["key"]   = row.get(key_key) or ""
        d["total"] += 1
        d["groups"][group] += 1

        if status in DONE_STATUSES:
            d["done"] += 1

        # Total Task MTC (group MTC saja, bukan MTC_BUGS)
        if group == "MTC":
            d["total_mtc"] += 1

        # Total Task UAT (group UAT saja, bukan UAT_BUGS)
        if group == "UAT":
            d["total_uat"] += 1

        # Bugs done
        if status in BUGS_DONE:
            d["bugs_done"] += 1

        # Bugs in progress (group bugs tapi belum done)
        if group in BUGS_GROUPS and status not in BUGS_DONE:
            d["bugs_inprog"] += 1

        if row.get("assignee"):
            d["assignees"].add(row["assignee"])

    result = []
    for name, data in item_map.items():
        total    = data["total"]
        done     = data["done"]
        done_pct = round((done / total) * 100) if total else 0

        result.append({
            "name":         data["name"],
            "key":          data["key"],
            "total":        total,
            "done":         done,
            "done_pct":     done_pct,
            "is_done":      done == total and total > 0,
            "total_mtc":    data["total_mtc"],
            "total_uat":    data["total_uat"],
            "bugs_done":    data["bugs_done"],
            "bugs_inprog":  data["bugs_inprog"],
            "groups":       dict(data["groups"]),
            "assignees":    sorted(data["assignees"]),
        })

    result.sort(key=lambda x: x["name"])
    return result


# ─────────────────────────────────────────────
# SHARED — hitung stats level 2
# ─────────────────────────────────────────────
def _build_detail(rows: list[dict], name: str) -> dict:
    total      = len(rows)
    done       = sum(1 for r in rows if r["status"] in DONE_STATUSES)
    bugs_done  = sum(1 for r in rows if r["status"] in BUGS_DONE)
    bugs_inprog = sum(
        1 for r in rows
        if STATUS_TO_GROUP.get(r["status"] or "", "") in BUGS_GROUPS
        and r["status"] not in BUGS_DONE
    )

    # Group → status → count
    groups = defaultdict(lambda: defaultdict(int))
    for row in rows:
        status = row["status"] or "UNKNOWN"
        group  = STATUS_TO_GROUP.get(status, "Lainnya")
        groups[group][status] += 1

    # Assignee breakdown
    assignee_map = defaultdict(lambda: {"total": 0, "done": 0, "groups": defaultdict(int)})
    for row in rows:
        aname  = row["assignee"] or "Unassigned"
        status = row["status"] or "UNKNOWN"
        group  = STATUS_TO_GROUP.get(status, "Lainnya")

        assignee_map[aname]["total"]       += 1
        assignee_map[aname]["groups"][group] += 1
        if status in DONE_STATUSES:
            assignee_map[aname]["done"] += 1

    assignees = []
    for aname, data in assignee_map.items():
        assignees.append({
            "name":     aname,
            "total":    data["total"],
            "done":     data["done"],
            "done_pct": round((data["done"] / data["total"]) * 100) if data["total"] else 0,
            "groups":   dict(data["groups"]),
        })
    assignees.sort(key=lambda x: -x["total"])

    return {
        "name":        name,
        "total":       total,
        "done":        done,
        "done_pct":    round((done / total) * 100) if total else 0,
        "bugs_done":   bugs_done,
        "bugs_inprog": bugs_inprog,
        "groups":      {g: dict(s) for g, s in groups.items()},
        "assignees":   assignees,
    }


# ─────────────────────────────────────────────
# QUERY LEVEL 1 — Summary per PROJECT
# ─────────────────────────────────────────────
def get_projects_summary(project_filter: str = "", assignee_filter: str = "", leader_filter: str = "", manager_filter: str = "") -> list[dict]:
    sql    = """
        SELECT project_name, project_key, status, assignee
        FROM issues
        WHERE project_name IS NOT NULL
        AND project_name != 'Project Management - MUF'
        AND LOWER(status) NOT LIKE '%bug%'
    """
    params = []

    if project_filter:
        sql += " AND project_name LIKE ?"
        params.append(f"%{project_filter}%")
    if assignee_filter:
        sql += " AND assignee = ?"
        params.append(assignee_filter)
    if leader_filter:
        sql += " AND leader = ?"
        params.append(leader_filter)
    if manager_filter:
        sql += " AND manager = ?"
        params.append(manager_filter)

    rows = query_db(sql, tuple(params))
    return _build_summary(rows, "project_name", "project_key")


# ─────────────────────────────────────────────
# QUERY LEVEL 1 — Summary per MTC
# ─────────────────────────────────────────────
def get_mtc_summary(mtc_filter: str = "", assignee_filter: str = "", leader_filter: str = "", manager_filter: str = "") -> list[dict]:
    sql    = """
        SELECT parent_key, parent_summary, status, assignee
        FROM issues
        WHERE project_name = 'Project Management - MUF'
        AND parent_key IS NOT NULL
        AND LOWER(status) NOT LIKE '%bug%'
    """
    params = []

    if mtc_filter:
        sql += " AND parent_summary LIKE ?"
        params.append(f"%{mtc_filter}%")
    if assignee_filter:
        sql += " AND assignee = ?"
        params.append(assignee_filter)
    if leader_filter:
        sql += " AND leader = ?"
        params.append(leader_filter)
    if manager_filter:
        sql += " AND manager = ?"
        params.append(manager_filter)

    rows = query_db(sql, tuple(params))
    return _build_summary(rows, "parent_summary", "parent_key")


# ─────────────────────────────────────────────
# QUERY LEVEL 2 — Detail per PROJECT
# ─────────────────────────────────────────────
def get_project_detail(project_name: str) -> dict:
    rows = query_db(
        """SELECT * FROM issues
           WHERE project_name = ?
           AND project_name != 'Project Management - MUF'
           AND status not in ('UAT Drop', 'OPR Drop','SUPPORT DROP','INVALID UAT')
           ORDER BY status""",
        (project_name,)
    )
    return _build_detail(rows, project_name)


# ─────────────────────────────────────────────
# QUERY LEVEL 2 — Detail per MTC
# ─────────────────────────────────────────────
def get_mtc_detail(parent_key: str) -> dict:
    rows = query_db(
        """SELECT * FROM issues
           WHERE parent_key = ?
           AND project_name = 'Project Management - MUF'
           ORDER BY status""",
        (parent_key,)
    )
    name = rows[0]["parent_summary"] if rows else parent_key
    return _build_detail(rows, name)

def get_all_leaders() -> list[str]:
    rows = query_db(
        "SELECT DISTINCT leader FROM issues WHERE leader IS NOT NULL AND leader != 'Unassigned' ORDER BY leader"
    )
    return [r["leader"] for r in rows]


def get_all_managers() -> list[str]:
    rows = query_db(
        "SELECT DISTINCT manager FROM issues WHERE manager IS NOT NULL AND manager != 'Unassigned' ORDER BY manager"
    )
    return [r["manager"] for r in rows]