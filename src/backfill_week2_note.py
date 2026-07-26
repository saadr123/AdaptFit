"""
backfill_week2_note.py — one-time script to save the week 2 rationale
that was already generated (before coach_notes existed) so the
dashboard has something to show for it.

Run once, then you can delete this file - it's not part of the
ongoing app.

Run:
    python backfill_week2_note.py
"""

from db import init_db, get_connection

RATIONALE = (
    "The pull muscle group had a 0% completion rate and a 1-week missed "
    "streak, so I simplified the Wednesday workout by reducing the number "
    "of exercises and sets. The legs and push muscle groups had 100% "
    "completion rates, so I held their workouts steady with small "
    "progressive increases."
)

init_db()  # makes sure coach_notes table exists

with get_connection() as conn:
    existing = conn.execute(
        "SELECT COUNT(*) FROM coach_notes WHERE week_number = 2"
    ).fetchone()[0]

    if existing:
        print("Week 2 already has a saved note - skipping to avoid a duplicate.")
    else:
        conn.execute(
            "INSERT INTO coach_notes (week_number, rationale) VALUES (2, ?)",
            (RATIONALE,),
        )
        print("Saved week 2 rationale.")