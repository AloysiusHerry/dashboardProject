import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from staff_mapping import LEADER_MAPPING, STAFF_MAPPING
from holiday import HOLIDAYS, WORK_HOURS_PER_DAY

DB_PATH = "jira_data.db"

UAT_STATUSES      = ["UAT Open", "UAT In Progress", "UAT Hold", "HOLD UAT", "UAT Done", "UAT Drop", "Done UAT", "Open"]
UAT_DONE          = {"UAT Done", "Done UAT"}
UAT_ACTIVE        = {"UAT In Progress", "UAT Open", "UAT Hold", "HOLD UAT", "Open"}
UAT_BUGS_STATUSES = ["UAT Open.", "UAT Done.", "BUGS Open"]
UAT_BUGS_DONE     = {"UAT Done."}
MTC_BUGS_STATUSES = ["MTC BUG - UAT In Progress", "MTC BUG - UAT Done", "MTC BUG - Invalid"]
MTC_BUGS_DONE     = {"MTC BUG - UAT Done"}
HOLIDAY_SET       = set(HOLIDAYS)


def query_db(sql: str, params: tuple = ()) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


def get_available_months() -> list[str]:
    rows = query_db(
        "SELECT DISTINCT substr(created, 1, 7) as ym FROM issues WHERE created IS NOT NULL ORDER BY ym DESC"
    )
    return [r["ym"] for r in rows if r["ym"]]


def get_work_hours_in_month(year_month: str) -> float:
    """Hitung jam kerja efektif dalam 1 bulan (exclude weekend + holiday)."""
    try:
        y, m  = int(year_month[:4]), int(year_month[5:7])
        start = date(y, m, 1)
        end   = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    except Exception:
        return 0.0
    work_days = 0
    current   = start
    while current < end:
        if current.weekday() < 5 and current.strftime("%Y-%m-%d") not in HOLIDAY_SET:
            work_days += 1
        current += timedelta(days=1)
    return work_days * WORK_HOURS_PER_DAY


def get_work_hours_until_today(year_month: str) -> float:
    """Hitung jam kerja efektif dari awal bulan sampai hari ini."""
    try:
        y, m  = int(year_month[:4]), int(year_month[5:7])
        start = date(y, m, 1)
        end   = min(date.today() + timedelta(days=1),
                    date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1))
    except Exception:
        return 0.0
    work_days = 0
    current   = start
    while current < end:
        if current.weekday() < 5 and current.strftime("%Y-%m-%d") not in HOLIDAY_SET:
            work_days += 1
        current += timedelta(days=1)
    return work_days * WORK_HOURS_PER_DAY


def get_capacity_hours(month_filter: str = "") -> dict:
    today_ym = date.today().strftime("%Y-%m")
    if month_filter:
        if month_filter < today_ym:
            return {month_filter: get_work_hours_in_month(month_filter)}
        else:
            return {month_filter: get_work_hours_until_today(month_filter)}
    else:
        months = query_db(
            "SELECT DISTINCT substr(created, 1, 7) as ym FROM issues WHERE created IS NOT NULL ORDER BY ym"
        )
        result = {}
        for row in months:
            ym = row["ym"]
            if not ym:
                continue
            if ym < today_ym:
                result[ym] = get_work_hours_in_month(ym)
            elif ym == today_ym:
                result[ym] = get_work_hours_until_today(ym)
        return result


def get_leader_view(leader_filter: str = "", month_filter: str = "") -> dict:
    def build_query(statuses: list) -> list[dict]:
        placeholders = ",".join("?" * len(statuses))
        sql = f"""
            SELECT assignee, reporter, status, project_name, project_key,
                   key, summary, created, actual_duration_hours
            FROM issues
            WHERE status IN ({placeholders})
        """
        params = list(statuses)
        if month_filter:
            sql += " AND substr(created, 1, 7) = ?"
            params.append(month_filter)
        return query_db(sql, tuple(params))

    uat_rows      = build_query(UAT_STATUSES)
    uat_bugs_rows = build_query(UAT_BUGS_STATUSES)
    mtc_bugs_rows = build_query(MTC_BUGS_STATUSES)

    capacity_map   = get_capacity_hours(month_filter)
    total_capacity = sum(capacity_map.values())

    staff_stats = defaultdict(lambda: {
        "task_uat":        0,
        "task_done":       0,
        "task_inprog":     0,
        "bugs_uat":        0,
        "bugs_uat_done":   0,
        "bugs_mtc":        0,
        "bugs_mtc_done":   0,
        "projects":        set(),
        "duration_hours":  0.0,
        "duration_by_month": defaultdict(float),
    })

    for row in uat_rows:
        name = row["assignee"] or ""
        if not name or name == "Unassigned":
            continue
        staff_stats[name]["task_uat"] += 1
        if row["status"] in UAT_DONE:
            staff_stats[name]["task_done"] += 1
        if row["status"] in UAT_ACTIVE:
            staff_stats[name]["task_inprog"] += 1
            if row["project_name"]:
                staff_stats[name]["projects"].add(row["project_name"])
        dur = 0.0
        try:
            dur = float(row.get("actual_duration_hours") or 0)
        except Exception:
            pass
        staff_stats[name]["duration_hours"] += dur
        ym = (row.get("created") or "")[:7]
        if ym:
            staff_stats[name]["duration_by_month"][ym] += dur

    for row in uat_bugs_rows:
        name = row["reporter"] or ""
        if not name or name == "Unassigned":
            continue
        staff_stats[name]["bugs_uat"] += 1
        if row["status"] in UAT_BUGS_DONE:
            staff_stats[name]["bugs_uat_done"] += 1

    for row in mtc_bugs_rows:
        name = row["reporter"] or ""
        if not name or name == "Unassigned":
            continue
        staff_stats[name]["bugs_mtc"] += 1
        if row["status"] in MTC_BUGS_DONE:
            staff_stats[name]["bugs_mtc_done"] += 1

    leaders_data = {}
    for leader_name, info in LEADER_MAPPING.items():
        if leader_filter and leader_name != leader_filter:
            continue

        staff_list = []
        for staff_name in info["staff"]:
            stats    = staff_stats.get(staff_name, {})
            task_uat = stats.get("task_uat", 0)
            done     = stats.get("task_done", 0)
            done_pct = round((done / task_uat) * 100) if task_uat else 0
            dur_hrs  = round(stats.get("duration_hours", 0.0), 1)
            util_pct = round((dur_hrs / total_capacity) * 100) if total_capacity else 0

            staff_list.append({
                "name":           staff_name,
                "leader":         leader_name,
                "manager":        info["manager"],
                "task_uat":       task_uat,
                "task_done":      done,
                "task_inprog":    stats.get("task_inprog", 0),
                "done_pct":       done_pct,
                "bugs_uat":       stats.get("bugs_uat", 0),
                "bugs_uat_done":  stats.get("bugs_uat_done", 0),
                "bugs_mtc":       stats.get("bugs_mtc", 0),
                "bugs_mtc_done":  stats.get("bugs_mtc_done", 0),
                "projects":       sorted(stats.get("projects", set())),
                "overload":       len(stats.get("projects", set())) > 1,
                "duration_hours": dur_hrs,
                "util_pct":       util_pct,
                "dur_by_month":   dict(stats.get("duration_by_month", {})),
            })

        staff_list.sort(key=lambda x: -x["task_uat"])

        total_task   = sum(s["task_uat"] for s in staff_list)
        total_done   = sum(s["task_done"] for s in staff_list)
        done_pct     = round((total_done / total_task) * 100) if total_task else 0

        leaders_data[leader_name] = {
            "leader":         leader_name,
            "manager":        info["manager"],
            "staff":          staff_list,
            "staff_count":    len(staff_list),
            "total_task":     total_task,
            "total_done":     total_done,
            "total_inprog":   sum(s["task_inprog"] for s in staff_list),
            "done_pct":       done_pct,
            "overload_count": sum(1 for s in staff_list if s["overload"]),
            "bugs_uat":       sum(s["bugs_uat"] for s in staff_list),
            "bugs_mtc":       sum(s["bugs_mtc"] for s in staff_list),
            "total_capacity": total_capacity,
            "capacity_map":   capacity_map,
        }

    return leaders_data


def get_all_leaders() -> list[str]:
    return sorted(LEADER_MAPPING.keys())


def get_export_data(leader_filter: str = "", month_filter: str = "") -> list[dict]:
    """Ambil semua task detail untuk export Excel."""
    target_staff = []
    for leader_name, info in LEADER_MAPPING.items():
        if leader_filter and leader_name != leader_filter:
            continue
        for staff_name in info["staff"]:
            target_staff.append({
                "name":    staff_name,
                "leader":  leader_name,
                "manager": info["manager"],
            })

    if not target_staff:
        return []

    staff_names  = [s["name"] for s in target_staff]
    staff_map    = {s["name"]: s for s in target_staff}
    placeholders = ",".join("?" * len(staff_names))

    sql = f"""
        SELECT key, summary, status, assignee, reporter,
               project_name, project_key, parent_key, parent_summary,
               created, updated, actual_duration_hours,
               bugs_open_date, plan_start_date, plan_end_date,
               actual_start_date, actual_end_date, actual_end_dev_done
        FROM issues
        WHERE assignee IN ({placeholders})
    """
    params = list(staff_names)
    if month_filter:
        sql += " AND substr(created, 1, 7) = ?"
        params.append(month_filter)
    sql += " ORDER BY assignee, created DESC"

    rows   = query_db(sql, tuple(params))
    result = []
    for row in rows:
        info = staff_map.get(row["assignee"], {})
        result.append({
            "Leader":              info.get("leader", "-"),
            "Manager":             info.get("manager", "-"),
            "Nama Staff":          row["assignee"] or "-",
            "Key":                 row["key"] or "-",
            "Summary":             row["summary"] or "-",
            "Status":              row["status"] or "-",
            "Project":             row["project_name"] or "-",
            "Project Key":         row["project_key"] or "-",
            "Parent Key":          row["parent_key"] or "-",
            "Parent Summary":      row["parent_summary"] or "-",
            "Created":             row["created"] or "-",
            "Updated":             row["updated"] or "-",
            "Duration (Jam)":      row["actual_duration_hours"] or 0,
            "Bugs Open Date":      row["bugs_open_date"] or "-",
            "Plan Start":          row["plan_start_date"] or "-",
            "Plan End":            row["plan_end_date"] or "-",
            "Actual Start":        row["actual_start_date"] or "-",
            "Actual End":          row["actual_end_date"] or "-",
            "Actual End Dev Done": row["actual_end_dev_done"] or "-",
        })
    return result