from datetime import date
import anthropic
from config import ANTHROPIC_API_KEY
from database import (
    get_tasks_due_today,
    get_overdue_tasks,
    get_reminders_due_today,
    save_briefing,
)
from weather import get_weather
from messaging import send_sms

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# BRIEFING SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
BRIEFING_SYSTEM_PROMPT = """\
You are Han's personal AI assistant delivering his morning briefing via SMS.

About Han:
- Works in inside sales at NetSpark Telecom (Business Development Rep)
- Passionate about wine and hospitality (Level 1 Sommelier, WSET studying)
- Engaged — wedding in December 2026
- From Enterprise, Alabama
- Personal motto: "Work hard so you can rest well."
- Faith-centered; plays keys for worship

Briefing rules:
1. Keep total length under 1,500 characters — this is an SMS
2. Do NOT use markdown (no **, no ##, no ->) — use plain text and line breaks
3. Use emoji sparingly for section headers only
4. Be warm and direct — like a trusted assistant who knows him well
5. Top 3 Priorities: pick the 3 most urgent/important items from all lists
6. Suggested Plan: 2-3 sentences. Be practical, not motivational-poster-y
7. If no tasks due today, say so with a quick encouragement
8. If overdue items exist, lead with urgency — these need to happen today
9. Use Han's name once at the start only

EXACT FORMAT TO USE (do not deviate):
Good morning, Han! [Day], [Month Date]

[One line: weather emoji + temp + description]

Today's Tasks:
[Each task on its own line with a bullet. Or: "Nothing due today!"]

Overdue (do these first!):
[Each task. Or: omit this section entirely if none]

Reminders Today:
[Each reminder. Or: omit if none]

Top 3 Priorities:
1. [most urgent]
2. [second most urgent]
3. [third]

Today's Plan:
[2-3 sentences of practical focus advice]
"""


def _format_task_list(tasks: list) -> str:
    if not tasks:
        return "Nothing due today!"
    lines = []
    for t in tasks:
        due = f" (due {t['due_date']})" if t.get("due_date") else ""
        cat = f" [{t['category']}]" if t.get("category", "general") != "general" else ""
        lines.append(f"• {t['title']}{due}{cat}")
    return "\n".join(lines)


def _format_reminder_list(reminders: list) -> str:
    if not reminders:
        return ""
    lines = []
    for r in reminders:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(r["remind_at"].replace("Z", "+00:00"))
            time_str = dt.strftime("%-I:%M %p")
        except Exception:
            time_str = r["remind_at"]
        lines.append(f"• {r['message']} at {time_str}")
    return "\n".join(lines)


async def generate_and_send_briefing() -> str:
    """Generate the morning briefing, send it via SMS, and log it."""
    weather      = await get_weather()
    tasks_today  = get_tasks_due_today()
    overdue      = get_overdue_tasks()
    reminders    = get_reminders_due_today()
    today_str    = date.today().strftime("%A, %B %-d")

    # ── Build the data context for Claude ────────────────────────────────────
    weather_line = (
        f"{weather['description']}, {weather['temp']}°F "
        f"(High {weather['high']}° / Low {weather['low']}°), "
        f"feels like {weather['feels_like']}°F"
        if not weather["error"]
        else "Weather data unavailable today."
    )

    overdue_block = ""
    if overdue:
        lines = "\n".join([
            f"- {t['title']} [overdue since {t['due_date']}] [{t.get('category','general')}]"
            for t in overdue
        ])
        overdue_block = f"\nOVERDUE TASKS ({len(overdue)}):\n{lines}"

    reminders_block = ""
    if reminders:
        lines = "\n".join([f"- {r['message']} at {r['remind_at']}" for r in reminders])
        reminders_block = f"\nREMINDERS TODAY ({len(reminders)}):\n{lines}"

    context = f"""\
DATE: {today_str}
WEATHER: {weather_line}

TASKS DUE TODAY ({len(tasks_today)}):
{_format_task_list(tasks_today)}
{overdue_block}
{reminders_block}
"""

    # ── Ask Claude to write the briefing ─────────────────────────────────────
    try:
        response = _client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 800,
            system     = BRIEFING_SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": context}],
        )
        briefing_text = response.content[0].text.strip()

    except Exception as exc:
        print(f"[briefing] Claude API error: {exc}")
        # Graceful fallback: plain data dump
        briefing_text = (
            f"Good morning, Han! {today_str}\n\n"
            f"{weather_line}\n\n"
            f"Tasks today: {len(tasks_today)}\n"
            f"Overdue: {len(overdue)}\n"
            f"Reminders: {len(reminders)}\n\n"
            "(AI summary unavailable — check your task list directly.)"
        )

    # ── Send and log ──────────────────────────────────────────────────────────
    send_sms(briefing_text)
    save_briefing(briefing_text)
    print(f"[briefing] Sent:\n{briefing_text}")
    return briefing_text
