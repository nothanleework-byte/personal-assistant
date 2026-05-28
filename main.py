from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import PlainTextResponse
from datetime import datetime

from classifier import classify_message
from database import (
    create_task,
    create_reminder,
    mark_task_complete_by_keyword,
    get_all_pending_tasks,
)
from messaging import send_sms
from briefing import generate_and_send_briefing
from config import MY_PHONE_NUMBER

app = FastAPI(title="Han's Personal Assistant", version="1.0.0")


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "running", "message": "Personal Assistant is online."}


# ─────────────────────────────────────────────────────────────────────────────
# INCOMING SMS  (Twilio webhook → POST /incoming)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/incoming", response_class=PlainTextResponse)
async def incoming_sms(
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Twilio sends a POST here for every inbound SMS.
    We classify the message, act on it, and reply via send_sms().
    We return an empty 200 so Twilio doesn't send a duplicate TwiML reply.
    """

    # ── Security: only accept messages from your own number ──────────────────
    # Normalise both numbers to digits-only for comparison
    def _digits(n: str) -> str:
        return "".join(c for c in n if c.isdigit())

    if _digits(From) not in _digits(MY_PHONE_NUMBER):
        print(f"[incoming] Rejected message from unknown number: {From}")
        return ""

    message = Body.strip()
    if not message:
        return ""

    print(f"[incoming] Message from {From}: {message}")

    # ── Classify ──────────────────────────────────────────────────────────────
    classification = await classify_message(message)
    intent     = classification.get("intent", "unclear")
    confidence = float(classification.get("confidence", 0.0))

    print(f"[incoming] Classified as: {intent} (confidence {confidence:.2f})")

    # ── Low confidence → ask for clarification ────────────────────────────────
    if confidence < 0.70 or intent == "unclear":
        question = classification.get(
            "clarification_needed",
            "I wasn't sure what to do with that. Could you rephrase?"
        )
        send_sms(question)
        return ""

    # ── Handle each intent ────────────────────────────────────────────────────

    if intent == "create_task":
        title    = classification.get("title") or message
        due_date = classification.get("due_date")
        category = classification.get("category", "general")
        priority = classification.get("priority", "medium")

        create_task(
            title    = title,
            category = category,
            priority = priority,
            due_date = due_date,
        )

        due_str = f" — due {due_date}" if due_date else ""
        send_sms(f"Task added: {title}{due_str}")

    elif intent == "create_reminder":
        title      = classification.get("title") or message
        remind_at  = classification.get("remind_at")
        due_date   = classification.get("due_date")
        category   = classification.get("category", "general")
        priority   = classification.get("priority", "medium")

        if not remind_at:
            send_sms(
                "Got it — but I couldn't figure out when to remind you. "
                "Can you add a date or time?"
            )
            return ""

        # Create both a reminder and a linked task
        task = create_task(
            title    = title,
            category = category,
            priority = priority,
            due_date = due_date,
        )
        create_reminder(
            message        = title,
            remind_at      = remind_at,
            linked_task_id = task.get("id"),
        )

        # Format the remind_at timestamp into something readable
        try:
            dt      = datetime.fromisoformat(remind_at.replace("Z", ""))
            readable = dt.strftime("%A, %B %-d at %-I:%M %p")
        except Exception:
            readable = remind_at

        send_sms(f"Reminder set: {title} on {readable}")

    elif intent == "mark_complete":
        search_term = classification.get("search_term", "")
        completed   = mark_task_complete_by_keyword(search_term)

        if completed:
            send_sms(f"Done! Marked complete: {completed['title']}")
        else:
            # Show the user their open tasks so they can be specific
            pending = get_all_pending_tasks()
            if pending:
                lines = "\n".join(
                    [f"• {t['title']}" for t in pending[:6]]
                )
                send_sms(
                    f"Couldn't find a task matching '{search_term}'. "
                    f"Here are your open tasks:\n{lines}"
                )
            else:
                send_sms(
                    f"No pending task found matching '{search_term}'. "
                    "Your task list is empty — nice work!"
                )

    elif intent == "query":
        pending = get_all_pending_tasks()
        if not pending:
            send_sms("You have no open tasks. Your list is clear!")
        else:
            lines = []
            for t in pending[:8]:  # Limit to 8 for SMS length
                due = f" ({t['due_date']})" if t.get("due_date") else ""
                lines.append(f"• {t['title']}{due}")
            if len(pending) > 8:
                lines.append(f"...and {len(pending) - 8} more")
            send_sms("Open tasks:\n" + "\n".join(lines))

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# BRIEFING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/briefing")
async def send_briefing():
    """
    Trigger the morning briefing. Call this via Railway cron or cron-job.org.
    Secured in production by keeping the URL secret (no auth needed for MVP).
    """
    briefing = await generate_and_send_briefing()
    return {"status": "sent", "preview": briefing[:300]}


@app.get("/briefing/preview")
async def preview_briefing():
    """
    Preview the briefing WITHOUT sending an SMS.
    Useful during development and testing.
    """
    briefing = await generate_and_send_briefing()
    return {"briefing": briefing}
