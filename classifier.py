import json
from datetime import date
import anthropic
from config import ANTHROPIC_API_KEY

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION SYSTEM PROMPT
# {today} and {day_of_week} are injected at runtime.
# ─────────────────────────────────────────────────────────────────────────────
CLASSIFICATION_PROMPT = """\
You are an intent classifier for Han's personal AI assistant.
Today's date: {today} ({day_of_week}).

Your ONLY output is a single valid JSON object — no prose, no markdown fences.

─────────────────────────────────────────────
INTENTS
─────────────────────────────────────────────
create_task     → adding a task or to-do item
create_reminder → set a reminder at a specific future time
mark_complete   → marking an existing task as done
query           → asking what tasks/reminders exist
unclear         → not enough information to act on

─────────────────────────────────────────────
REQUIRED JSON SCHEMA
─────────────────────────────────────────────
{{
  "intent":               "create_task" | "create_reminder" | "mark_complete" | "query" | "unclear",
  "title":                "clean task/reminder description (remove filler like 'remind me to')",
  "due_date":             "YYYY-MM-DD or null",
  "remind_at":            "ISO 8601 datetime e.g. 2026-05-28T09:00:00 or null",
  "category":             "work|wine_career|wedding|faith|finance|home|health|networking|errands|personal|general",
  "priority":             "low|medium|high",
  "search_term":          "keyword to find existing task — for mark_complete ONLY, else null",
  "confidence":           0.0-1.0,
  "clarification_needed": "question string if unclear, else null"
}}

─────────────────────────────────────────────
DATE RESOLUTION RULES  (today = {today})
─────────────────────────────────────────────
• "tomorrow"    → next calendar day
• "Friday"      → the next upcoming Friday (not today if today IS Friday, use next week's)
• "next week"   → 7 days from today
• "this weekend" → upcoming Saturday
• If no date given for a task → due_date = null
• If no date given for a reminder → ask for clarification
• Default reminder time when only a date is given: 09:00 AM on that date

─────────────────────────────────────────────
CATEGORY DETECTION RULES
─────────────────────────────────────────────
wine_career  → wine, WSET, sommelier, tasting, hospitality career, Santé
wedding      → venue, ring, invite, rehearsal, florist, December wedding, vows
finance      → bill, credit card, Discover, payment, bank, rent, money
work         → NetSpark, sales, prospect, call, CRM, quota, lead
home         → laundry, dishes, cleaning, groceries, repairs, vacuum
health       → workout, doctor, meds, sleep, exercise
faith        → church, prayer, devotional, worship, Bible, keys
networking   → reaching out to a person socially, LinkedIn, follow-up with a person
errands      → errands, DMV, post office, store trip
personal     → journaling, reading, personal goals, habits

─────────────────────────────────────────────
EXAMPLES
─────────────────────────────────────────────
Input:  "Remind me tomorrow to call John."
Output: {{"intent":"create_reminder","title":"Call John","due_date":"{tomorrow}","remind_at":"{tomorrow}T09:00:00","category":"networking","priority":"medium","search_term":null,"confidence":0.97,"clarification_needed":null}}

Input:  "Add groceries to tomorrow."
Output: {{"intent":"create_task","title":"Groceries","due_date":"{tomorrow}","remind_at":null,"category":"home","priority":"medium","search_term":null,"confidence":0.90,"clarification_needed":null}}

Input:  "Remind me Friday to pay Discover."
Output: {{"intent":"create_reminder","title":"Pay Discover card","due_date":"{next_friday}","remind_at":"{next_friday}T09:00:00","category":"finance","priority":"high","search_term":null,"confidence":0.97,"clarification_needed":null}}

Input:  "Add study wine for 30 minutes."
Output: {{"intent":"create_task","title":"Study wine for 30 minutes","due_date":null,"remind_at":null,"category":"wine_career","priority":"medium","search_term":null,"confidence":0.95,"clarification_needed":null}}

Input:  "Mark laundry done."
Output: {{"intent":"mark_complete","title":null,"due_date":null,"remind_at":null,"category":null,"priority":null,"search_term":"laundry","confidence":0.98,"clarification_needed":null}}

Input:  "Remind me about the thing."
Output: {{"intent":"unclear","title":null,"due_date":null,"remind_at":null,"category":null,"priority":null,"search_term":null,"confidence":0.2,"clarification_needed":"I'd love to set that reminder — what should I remind you about, and when?"}}
"""


async def classify_message(message: str) -> dict:
    """
    Send `message` to Claude for intent classification.
    Returns a structured dict. Falls back gracefully on error.
    """
    today = date.today()

    from datetime import timedelta
    # Pre-compute dates for the prompt examples
    tomorrow = today + timedelta(days=1)
    days_until_friday = (4 - today.weekday()) % 7  # 4 = Friday
    if days_until_friday == 0:
        days_until_friday = 7  # If today IS Friday, use next Friday
    next_friday = today + timedelta(days=days_until_friday)

    system_prompt = CLASSIFICATION_PROMPT.format(
        today        = today.isoformat(),
        day_of_week  = today.strftime("%A"),
        tomorrow     = tomorrow.isoformat(),
        next_friday  = next_friday.isoformat(),
    )

    try:
        response = _client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 500,
            system     = system_prompt,
            messages   = [{"role": "user", "content": message}],
        )
        raw = response.content[0].text.strip()
        # Strip any accidental markdown fences Claude might add
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)

    except json.JSONDecodeError as exc:
        print(f"[classifier] JSON parse error: {exc} | raw: {raw!r}")
        return _fallback("I had trouble parsing that. Could you rephrase?")

    except Exception as exc:
        print(f"[classifier] API error: {exc}")
        return _fallback("Something went wrong on my end. Try again in a moment.")


def _fallback(question: str) -> dict:
    return {
        "intent":               "unclear",
        "title":                None,
        "due_date":             None,
        "remind_at":            None,
        "category":             None,
        "priority":             None,
        "search_term":          None,
        "confidence":           0.0,
        "clarification_needed": question,
    }
