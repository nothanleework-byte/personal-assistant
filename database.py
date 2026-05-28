from supabase import create_client, Client
from datetime import date, datetime
from typing import Optional
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────

def create_task(
    title: str,
    category: str = "general",
    priority: str = "medium",
    due_date: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Insert a new pending task and return the created row."""
    payload = {
        "title":    title,
        "category": category,
        "priority": priority,
        "status":   "pending",
        "source":   "sms",
    }
    if due_date:
        payload["due_date"] = due_date
    if notes:
        payload["notes"] = notes

    result = supabase.table("tasks").insert(payload).execute()
    return result.data[0] if result.data else {}


def get_tasks_due_today() -> list:
    today = date.today().isoformat()
    result = (
        supabase.table("tasks")
        .select("*")
        .eq("due_date", today)
        .eq("status", "pending")
        .execute()
    )
    return result.data or []


def get_overdue_tasks() -> list:
    today = date.today().isoformat()
    result = (
        supabase.table("tasks")
        .select("*")
        .lt("due_date", today)
        .eq("status", "pending")
        .execute()
    )
    return result.data or []


def get_all_pending_tasks() -> list:
    result = (
        supabase.table("tasks")
        .select("*")
        .eq("status", "pending")
        .execute()
    )
    # Sort in Python: tasks with a due_date first, then by date
    rows = result.data or []
    rows.sort(key=lambda t: (t.get("due_date") is None, t.get("due_date") or ""))
    return rows


def mark_task_complete_by_keyword(search_term: str) -> Optional[dict]:
    """
    Find the first pending task whose title contains `search_term`
    and mark it complete. Returns the updated row or None.
    """
    result = (
        supabase.table("tasks")
        .select("*")
        .eq("status", "pending")
        .ilike("title", f"%{search_term}%")
        .execute()
    )
    if not result.data:
        return None

    task = result.data[0]
    updated = (
        supabase.table("tasks")
        .update({
            "status":       "complete",
            "completed_at": datetime.utcnow().isoformat(),
        })
        .eq("id", task["id"])
        .execute()
    )
    return updated.data[0] if updated.data else None


# ─────────────────────────────────────────────
# REMINDERS
# ─────────────────────────────────────────────

def create_reminder(
    message: str,
    remind_at: str,
    linked_task_id: Optional[str] = None,
) -> dict:
    """Insert a new reminder and return the created row."""
    payload = {
        "message":   message,
        "remind_at": remind_at,
        "status":    "pending",
    }
    if linked_task_id:
        payload["linked_task_id"] = linked_task_id

    result = supabase.table("reminders").insert(payload).execute()
    return result.data[0] if result.data else {}


def get_reminders_due_today() -> list:
    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    today_end = datetime.utcnow().replace(
        hour=23, minute=59, second=59, microsecond=0
    ).isoformat()

    result = (
        supabase.table("reminders")
        .select("*")
        .gte("remind_at", today_start)
        .lte("remind_at", today_end)
        .eq("status", "pending")
        .execute()
    )
    return result.data or []


# ─────────────────────────────────────────────
# BRIEFING LOG
# ─────────────────────────────────────────────

def save_briefing(briefing_text: str):
    supabase.table("briefing_log").upsert({
        "date": str(date.today()),
        "briefing": briefing_text
    }, on_conflict="date").execute()
