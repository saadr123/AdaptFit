"""
llm_coach.py — the LLM's only job is to react to the adherence report
and produce next week's plan + a short rationale. It never sees raw
logs, only the summarized signals from adherence.py — that's what
keeps its output grounded instead of hallucinating patterns.

"""

import os
import json
import requests
from dotenv import load_dotenv

from db import get_connection
from adherence import load_data, build_report

load_dotenv()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"  # free tier as of mid-2026; swap here if Groq changes their lineup

SYSTEM_PROMPT = """You are a strength coach adjusting a client's weekly program.
You will be given last week's planned exercises and a JSON adherence report
(completion rates, missed streaks, volume).

Rules:
- If a muscle group has a missed streak of 2+ weeks, don't just repeat the
  same session — shorten it or simplify it so it's easier to actually complete.
- If a muscle group is at 100% completion, you can hold steady or apply a
  small progressive increase.
- Keep the same days of week (Monday/Wednesday/Friday) and roughly the same
  exercise categories unless the data clearly justifies a change.
- Respond with ONLY valid JSON, no markdown, no commentary, in this exact shape:

{
  "rationale": "1-3 sentences explaining what you changed and why, referencing the actual numbers",
  "plan": [
    {"day_of_week": "Monday", "exercise": "...", "muscle_group": "push", "target_sets": 3, "target_reps": 8, "target_weight": 135}
  ]
}

target_weight can be null for bodyweight exercises. Include every planned exercise for the week."""


def get_current_plan(week_number: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT day_of_week, exercise, muscle_group, target_sets, target_reps, target_weight "
            "FROM planned_sessions WHERE week_number = ?",
            (week_number,),
        ).fetchall()
    return [dict(r) for r in rows]


def generate_next_week_plan(current_week: int) -> dict:
    df = load_data()
    report = build_report(df)
    current_plan = get_current_plan(current_week)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not found. Copy .env.example to .env and add your key "
            "from https://console.groq.com"
        )

    user_message = (
        f"Last week's plan (week {current_week}):\n{json.dumps(current_plan, indent=2)}\n\n"
        f"Adherence report:\n{json.dumps(report, indent=2)}"
    )

    response = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw)


def save_generated_plan(new_week_number: int, generated: dict):
    """Inserts the LLM's plan into planned_sessions under the new week number,
    and saves its rationale to coach_notes so the dashboard can show it."""
    with get_connection() as conn:
        for item in generated["plan"]:
            conn.execute(
                """INSERT INTO planned_sessions
                   (week_number, day_of_week, exercise, muscle_group,
                    target_sets, target_reps, target_weight)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_week_number,
                    item["day_of_week"],
                    item["exercise"],
                    item["muscle_group"],
                    item["target_sets"],
                    item["target_reps"],
                    item.get("target_weight"),
                ),
            )
        conn.execute(
            "INSERT INTO coach_notes (week_number, rationale) VALUES (?, ?)",
            (new_week_number, generated["rationale"]),
        )
    print(f"Saved {len(generated['plan'])} exercises and rationale as week {new_week_number}.")


if __name__ == "__main__":
    CURRENT_WEEK = 1
    NEXT_WEEK = 2

    result = generate_next_week_plan(CURRENT_WEEK)

    print("Rationale:")
    print(f"  {result['rationale']}\n")

    print("Next week's plan:")
    for item in result["plan"]:
        weight = item.get("target_weight")
        weight_str = f"{weight} lb" if weight else "bodyweight"
        print(f"  {item['day_of_week']:10s} {item['exercise']:20s} "
              f"{item['target_sets']}x{item['target_reps']}  {weight_str}")

    save_generated_plan(NEXT_WEEK, result)