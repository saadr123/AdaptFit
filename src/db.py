"""
db.py — schema + connection helper for AdaptFit.

Two tables:
  planned_sessions  -> what the program says you SHOULD do
  session_logs      -> what actually happened when you trained (or didn't)

"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "adaptfit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS planned_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number     INTEGER NOT NULL,
    day_of_week     TEXT NOT NULL,          -- 'Monday', 'Tuesday', ...
    exercise        TEXT NOT NULL,
    muscle_group    TEXT NOT NULL,          -- 'legs', 'push', 'pull', etc.
    target_sets     INTEGER NOT NULL,
    target_reps     INTEGER NOT NULL,
    target_weight   REAL,                   -- nullable: bodyweight work has no load
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    planned_session_id  INTEGER NOT NULL,
    log_date            TEXT NOT NULL,       -- ISO date the session actually happened/was due
    completed           INTEGER NOT NULL,    -- 0 or 1
    actual_sets         INTEGER,
    actual_reps         INTEGER,
    actual_weight       REAL,
    notes               TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (planned_session_id) REFERENCES planned_sessions (id)
);

CREATE TABLE IF NOT EXISTS coach_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number     INTEGER NOT NULL,
    rationale       TEXT NOT NULL,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def get_connection():
    """Yields a sqlite3 connection with row access by column name."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Creates tables if they don't exist. Safe to call every run."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"Database ready at {DB_PATH}")


def reset_db():
    """Drops and recreates both tables. Useful while iterating during dev."""
    with get_connection() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS session_logs;
            DROP TABLE IF EXISTS planned_sessions;
        """)
    init_db()


if __name__ == "__main__":
    init_db()