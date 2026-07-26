"""
adherence.py — turns raw planned_sessions + session_logs into the
signals that matter: completion rate, which muscle groups keep getting
skipped, and volume trends over time.

"""

import pandas as pd
from db import get_connection


def load_data() -> pd.DataFrame:
    """
    Joins planned_sessions + session_logs into one flat table, one row
    per exercise per week. This is the single source every function
    below works from.
    """
    query = """
        SELECT
            p.week_number,
            p.day_of_week,
            p.exercise,
            p.muscle_group,
            p.target_sets,
            p.target_reps,
            p.target_weight,
            l.log_date,
            l.completed,
            l.actual_sets,
            l.actual_reps,
            l.actual_weight,
            l.notes
        FROM session_logs l
        JOIN planned_sessions p ON l.planned_session_id = p.id
        ORDER BY p.week_number, l.log_date
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)

    df["completed"] = df["completed"].astype(bool)
    return df


def overall_completion_rate(df: pd.DataFrame) -> float:
    """% of all logged sessions that were completed, across everything."""
    if df.empty:
        return 0.0
    return round(df["completed"].mean() * 100, 1)


def completion_by_muscle_group(df: pd.DataFrame) -> pd.DataFrame:
    """
    Completion rate per muscle group. This is the first place a pattern
    like 'legs keep getting skipped' shows up numerically.
    """
    grouped = df.groupby("muscle_group")["completed"].agg(["mean", "count"])
    grouped["completion_rate_pct"] = (grouped["mean"] * 100).round(1)
    return grouped[["completion_rate_pct", "count"]].sort_values(
        "completion_rate_pct"
    )


def completion_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Completion rate per day of week — surfaces things like 'Wednesdays are the problem'."""
    grouped = df.groupby("day_of_week")["completed"].agg(["mean", "count"])
    grouped["completion_rate_pct"] = (grouped["mean"] * 100).round(1)
    return grouped[["completion_rate_pct", "count"]].sort_values(
        "completion_rate_pct"
    )


def missed_streak_by_muscle_group(df: pd.DataFrame) -> dict:
    """
    For each muscle group, counts how many of the MOST RECENT
    consecutive weeks were missed entirely (every exercise for that
    group skipped that week). This is the number that should trigger
    the LLM to actually change the plan rather than repeat it.

    Returns e.g. {'pull': 1, 'push': 0, 'legs': 0} with only 1 week of
    data so far — this will become meaningful once week 2+ exists.
    """
    streaks = {}
    for muscle_group, group_df in df.groupby("muscle_group"):
        # Was the muscle group fully missed in each week? (all exercises skipped)
        weekly_missed = (
            group_df.groupby("week_number")["completed"]
            .apply(lambda s: not s.any())  # True if NONE were completed
            .sort_index(ascending=False)   # most recent week first
        )

        streak = 0
        for missed in weekly_missed:
            if missed:
                streak += 1
            else:
                break
        streaks[muscle_group] = streak

    return streaks


def estimated_volume_by_week(df: pd.DataFrame) -> pd.DataFrame:
    """
    Total training volume (sets x reps x weight) per muscle group per
    week, using actual logged values when completed, falling back to 0
    for skipped sessions. Bodyweight moves (no weight) count sets x reps
    only, weighted at 1, so they still show up rather than vanishing.
    """
    def row_volume(row):
        if not row["completed"]:
            return 0
        weight = row["actual_weight"] if pd.notnull(row["actual_weight"]) else 1
        sets = row["actual_sets"] or 0
        reps = row["actual_reps"] or 0
        return sets * reps * weight

    df = df.copy()
    df["volume"] = df.apply(row_volume, axis=1)
    return (
        df.groupby(["week_number", "muscle_group"])["volume"]
        .sum()
        .reset_index()
        .sort_values(["week_number", "muscle_group"])
    )


def build_report(df: pd.DataFrame) -> dict:
    """
    Bundles everything into one dict — this is the exact structure
    step 3 will hand to the LLM as context for generating next week's
    plan. Keeping it as a plain dict (not printed text) now so it's
    ready to be serialized to JSON later.
    """
    return {
        "overall_completion_rate_pct": overall_completion_rate(df),
        "completion_by_muscle_group": completion_by_muscle_group(df).to_dict("index"),
        "completion_by_day": completion_by_day(df).to_dict("index"),
        "missed_streak_by_muscle_group": missed_streak_by_muscle_group(df),
        "volume_by_week": estimated_volume_by_week(df).to_dict("records"),
    }


if __name__ == "__main__":
    df = load_data()

    if df.empty:
        print("No data yet — run seed.py first.")
    else:
        report = build_report(df)

        print(f"Overall completion rate: {report['overall_completion_rate_pct']}%\n")

        print("By muscle group:")
        for mg, stats in report["completion_by_muscle_group"].items():
            print(f"  {mg:6s} {stats['completion_rate_pct']:5.1f}%  ({int(stats['count'])} sessions)")

        print("\nBy day of week:")
        for day, stats in report["completion_by_day"].items():
            print(f"  {day:10s} {stats['completion_rate_pct']:5.1f}%")

        print("\nCurrent missed streak (consecutive weeks fully skipped):")
        for mg, streak in report["missed_streak_by_muscle_group"].items():
            flag = "  <-- needs attention" if streak >= 2 else ""
            print(f"  {mg:6s} {streak} week(s){flag}")

        print("\nEstimated volume by week:")
        for row in report["volume_by_week"]:
            print(f"  week {row['week_number']}  {row['muscle_group']:6s}  {row['volume']:.0f}")