import os
import re
import sqlite3
from dotenv import load_dotenv
from list_team import LIST_TEAMS

load_dotenv()

DB_PATH = "jira_data.db"


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def get_assignees_from_db(jql_statuses: list[str] = None) -> list[str]:
    """Ambil daftar unik assignee dari DB."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    if jql_statuses:
        placeholders = ",".join("?" * len(jql_statuses))
        cur.execute(
            f"""SELECT DISTINCT assignee FROM issues
                WHERE assignee IS NOT NULL
                AND assignee != 'Unassigned'
                AND status IN ({placeholders})
                ORDER BY assignee""",
            tuple(jql_statuses)
        )
    else:
        cur.execute(
            """SELECT DISTINCT assignee FROM issues
               WHERE assignee IS NOT NULL
               AND assignee != 'Unassigned'
               ORDER BY assignee"""
        )

    rows = [r[0] for r in cur.fetchall()]
    con.close()
    return rows


def compare_assignees(statuses: list[str] = None) -> dict:
    """
    Bandingkan LIST_TEAMS dengan assignee di DB.

    Args:
        statuses: filter status tertentu, None = semua status

    Returns:
        {
            "jira_names"  : [...],   # dari DB
            "list_names"  : [...],   # dari list_team.py
            "not_in_jira" : [...],   # ada di list tapi TIDAK di DB
            "not_in_list" : [...],   # ada di DB tapi TIDAK di list
        }
    """
    jira_names = get_assignees_from_db(statuses)
    list_names = LIST_TEAMS

    jira_set = {normalize(n) for n in jira_names}
    list_set  = {normalize(n) for n in list_names}

    not_in_jira = [n for n in list_names if normalize(n) not in jira_set]
    not_in_list = [n for n in jira_names if normalize(n) not in list_set]

    return {
        "jira_names":  jira_names,
        "list_names":  list_names,
        "not_in_jira": not_in_jira,
        "not_in_list": not_in_list,
    }


if __name__ == "__main__":
    STATUSES = [
        "SUPPORT INPROGRESS",
        "MTC - UAT In Progress",
        "UAT In Progress",
    ]
    result = compare_assignees(STATUSES)
    print(f"DB      : {result['jira_names']}")
    print(f"List    : {result['list_names']}")
    print(f"❌ Di list, TIDAK di DB : {result['not_in_jira']}")
    print(f"➕ Di DB, TIDAK di list : {result['not_in_list']}")