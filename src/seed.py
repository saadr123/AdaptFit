"""
seed.py — populates one week of a Push/Pull/Legs plan, plus realistic
(mixed completed/skipped) session logs, so there's real data to compute
adherence stats against before the LLM is wired in at all.

"""

from datetime import date, timedelta
from db import get_connection, init_db, reset_db

# A basic 3-day/week PPL split for week 1. target_weight is None for
# bodyweight-style moves.
WEEK_1_PLAN = [
    # (day_of_week, exercise, muscle_group, sets, reps, weight)
    ("Monday",    "Bench Press",     "push", 4, 8, 135),
    ("Monday",    "Overhead Press",  "push", 3, 10, 65),
    ("Monday",    "Tricep Pushdown", "push", 3, 12, 40),
    ("Wednesday", "Deadlift",        "pull", 4, 6, 185),
    ("Wednesday", "Barbell Row",     "pull", 4, 8, 95),
    ("Wednesday", "Bicep Curl",      "pull", 3, 12, 25),
    ("Friday",    "Squat",           "legs", 4, 8, 155),
    ("Friday",    "Leg Press",       "legs", 3, 10, 220),
    ("Friday",    "Calf Raise",      "legs", 3, 15, None),
]

# Simulated real-world adherence: Monday and Friday happened, Wednesday
# got skipped entirely (the exact "missed leg/pull day" pattern the
# adherence logic and LLM will need to notice and react to later).
LOG_OVERRIDES = {
    "Wednesday": {"completed": False, "notes": "Skipped — ran out of time after class"},
}

DAY_TO_OFFSET = {"Monday": 0, "Wednesday": 2, "Friday": 4}


def seed_week(week_number: int = 1, week_start: date | None = None):
    week_start = week_start or (date.today() - timedelta(days=date.today().weekday()))

    with get_connection() as conn:
        cur = conn.cursor()

        for day, exercise, muscle_group, sets, reps, weight in WEEK_1_PLAN:
            cur.execute(
                """INSERT INTO planned_sessions
                   (week_number, day_of_week, exercise, muscle_group,
                    target_sets, target_reps, target_weight)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (week_number, day, exercise, muscle_group, sets, reps, weight),
            )
            planned_id = cur.lastrowid

            log_date = week_start + timedelta(days=DAY_TO_OFFSET[day])
            override = LOG_OVERRIDES.get(day)

            if override and not override["completed"]:
                cur.execute(
                    """INSERT INTO session_logs
                       (planned_session_id, log_date, completed, notes)
                       VALUES (?, ?, 0, ?)""",
                    (planned_id, log_date.isoformat(), override["notes"]),
                )
            else:
                # Completed as planned (minor realistic variance on weight)
                cur.execute(
                    """INSERT INTO session_logs
                       (planned_session_id, log_date, completed,
                        actual_sets, actual_reps, actual_weight)
                       VALUES (?, ?, 1, ?, ?, ?)""",
                    (planned_id, log_date.isoformat(), sets, reps, weight),
                )

    print(f"Seeded week {week_number} starting {week_start.isoformat()}: "
          f"{len(WEEK_1_PLAN)} planned sessions logged.")


if __name__ == "__main__":
    init_db()
    seed_week(week_number=1)