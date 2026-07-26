"""
check_db.py — prints planned sessions and logs
per week, so you can confirm each week looks right (9 planned per
week; logs only exist for weeks you've actually lived through).


"""

from db import get_connection

with get_connection() as conn:
    weeks = conn.execute(
        "SELECT DISTINCT week_number FROM planned_sessions ORDER BY week_number"
    ).fetchall()

    for row in weeks:
        wk = row["week_number"]
        planned = conn.execute(
            "SELECT COUNT(*) FROM planned_sessions WHERE week_number = ?", (wk,)
        ).fetchone()[0]
        logs = conn.execute(
            """SELECT COUNT(*) FROM session_logs l
               JOIN planned_sessions p ON l.planned_session_id = p.id
               WHERE p.week_number = ?""",
            (wk,),
        ).fetchone()[0]
        print(f"week {wk}: planned={planned}  logs={logs}")

print("\n[OK] A week with planned>0 and logs=0 just means you haven't trained it yet — that's expected for a future week.")
print("     Only worry if a PAST week's planned count is a multiple of 9 (e.g. 18) — that means it was seeded twice.")