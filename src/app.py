"""
app.py — AdaptFit dashboard.

Pulls from the same db.py / adherence.py modules everything else uses,
so this is purely a visualization layer, not a separate source of truth.
"""

import streamlit as st
import plotly.express as px
import pandas as pd

from db import get_connection
from adherence import load_data, build_report

st.set_page_config(page_title="AdaptFit", page_icon=None, layout="wide")

st.title("AdaptFit")
st.caption("An LLM-adjusted training program that reacts to whether you actually show up.")

df = load_data()

if df.empty:
    st.warning("No data yet. Run `python seed.py` first.")
    st.stop()

report = build_report(df)

# ---- Top-line metrics ----
col1, col2, col3 = st.columns(3)
col1.metric("Overall completion rate", f"{report['overall_completion_rate_pct']}%")

at_risk = [mg for mg, streak in report["missed_streak_by_muscle_group"].items() if streak >= 2]
col2.metric("Muscle groups at risk", len(at_risk), help="2+ consecutive weeks fully missed")

latest_week = int(df["week_number"].max())

with get_connection() as conn:
    latest_planned_week = conn.execute(
        "SELECT MAX(week_number) FROM planned_sessions"
    ).fetchone()[0]
if latest_planned_week is not None:
    latest_week = int(latest_planned_week)

col3.metric("Latest week in plan", latest_week)

st.divider()

# ---- Completion by muscle group + day ----
left, right = st.columns(2)

with left:
    st.subheader("Completion by muscle group")
    mg_df = (
        pd.DataFrame.from_dict(report["completion_by_muscle_group"], orient="index")
        .reset_index()
        .rename(columns={"index": "muscle_group"})
    )
    fig = px.bar(
        mg_df, x="muscle_group", y="completion_rate_pct",
        text="completion_rate_pct", range_y=[0, 100],
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(yaxis_title="Completion %", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Completion by day of week")
    day_df = (
        pd.DataFrame.from_dict(report["completion_by_day"], orient="index")
        .reset_index()
        .rename(columns={"index": "day_of_week"})
    )
    fig = px.bar(
        day_df, x="day_of_week", y="completion_rate_pct",
        text="completion_rate_pct", range_y=[0, 100],
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(yaxis_title="Completion %", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Missed streaks ----
st.subheader("Missed streaks")
streak_cols = st.columns(len(report["missed_streak_by_muscle_group"]) or 1)
for col, (mg, streak) in zip(streak_cols, report["missed_streak_by_muscle_group"].items()):
    label = f"{mg}"
    delta = "needs attention" if streak >= 2 else ("ok" if streak == 0 else "watch")
    col.metric(label, f"{streak} wk(s)", delta=delta, delta_color="inverse" if streak >= 2 else "off")

st.divider()

# ---- Volume trend ----
st.subheader("Volume trend by week")
vol_df = pd.DataFrame(report["volume_by_week"])
if not vol_df.empty:
    fig = px.line(
        vol_df, x="week_number", y="volume", color="muscle_group", markers=True,
    )
    fig.update_layout(xaxis_title="Week", yaxis_title="Estimated volume (sets x reps x weight)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Not enough weeks yet to show a trend.")

st.divider()

# ---- Coach's rationale + current plan ----
st.subheader("Coach's notes")
with get_connection() as conn:
    notes = conn.execute(
        "SELECT week_number, rationale FROM coach_notes ORDER BY week_number DESC"
    ).fetchall()

if notes:
    for note in notes:
        st.info(f"**Week {note['week_number']}:** {note['rationale']}")
else:
    st.caption("No LLM-generated plans yet. Run `python llm_coach.py` to generate one.")

st.subheader(f"Current plan — week {latest_week}")
with get_connection() as conn:
    plan_rows = conn.execute(
        """SELECT day_of_week, exercise, muscle_group, target_sets, target_reps, target_weight
           FROM planned_sessions WHERE week_number = ?
           ORDER BY CASE day_of_week
             WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
             WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END""",
        (latest_week,),
    ).fetchall()

plan_df = pd.DataFrame([dict(r) for r in plan_rows])
st.dataframe(plan_df, use_container_width=True, hide_index=True)