# Personal AI Assistant — Phase 1 Build Guide

A complete beginner-friendly guide for building a two-way SMS personal assistant
using Twilio, Python/FastAPI, Claude API, Supabase, and OpenWeatherMap.

---

## Table of Contents

1. [Project File Structure](#1-project-file-structure)
2. [Supabase Setup and SQL Schema](#2-supabase-setup-and-sql-schema)
3. [Required Environment Variables](#3-required-environment-variables)
4. [Account Setup — All Services](#4-account-setup--all-services)
5. [OpenWeatherMap Setup](#5-openweathermap-setup)
6. [Twilio Setup](#6-twilio-setup)
7. [Local Development Setup](#7-local-development-setup)
8. [Testing Locally](#8-testing-locally)
9. [Railway Deployment](#9-railway-deployment)
10. [Twilio Webhook Configuration](#10-twilio-webhook-configuration)
11. [Morning Briefing Cron Job](#11-morning-briefing-cron-job)
12. [Test Messages to Send](#12-test-messages-to-send)
13. [Common Bugs and Fixes](#13-common-bugs-and-fixes)

---

## 1. Project File Structure

```
personal-assistant/
├── app/
│   ├── __init__.py       ← makes app/ a Python package
│   ├── main.py           ← FastAPI app: routes, webhook handler
│   ├── classifier.py     ← Claude intent classification
│   ├── briefing.py       ← morning briefing generator
│   ├── database.py       ← Supabase CRUD operations
│   ├── weather.py        ← OpenWeatherMap fetcher
│   ├── messaging.py      ← Twilio SMS sender
│   └── config.py         ← environment variable loader
├── .env                  ← YOUR secrets (never commit this)
├── .env.example          ← template (safe to commit)
├── .gitignore
├── Procfile              ← tells Railway how to start the server
├── requirements.txt      ← Python dependencies
└── GUIDE.md              ← this file
```

---

## 2. Supabase Setup and SQL Schema

### Step 1 — Create a Supabase account
Go to https://supabase.com and sign up (free). Create a new project.
Name it something like `personal-assistant`. Save the database password somewhere safe.

### Step 2 — Run this SQL in the Supabase SQL Editor

Open your project → click "SQL Editor" in the left sidebar → paste and run:

```sql
-- ─────────────────────────────────────────────
-- TASKS
-- ─────────────────────────────────────────────
CREATE TABLE tasks (
    id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    title        TEXT        NOT NULL,
    category     TEXT        DEFAULT 'general',
    status       TEXT        DEFAULT 'pending'
                             CHECK (status IN ('pending', 'complete', 'deleted')),
    priority     TEXT        DEFAULT 'medium'
                             CHECK (priority IN ('low', 'medium', 'high')),
    due_date     DATE,
    notes        TEXT,
    source       TEXT        DEFAULT 'sms',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- REMINDERS
-- ─────────────────────────────────────────────
CREATE TABLE reminders (
    id             UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    message        TEXT        NOT NULL,
    remind_at      TIMESTAMPTZ NOT NULL,
    status         TEXT        DEFAULT 'pending'
                               CHECK (status IN ('pending', 'sent', 'cancelled')),
    linked_task_id UUID        REFERENCES tasks(id) ON DELETE SET NULL,
    recurrence     TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- BRIEFING LOG
-- ─────────────────────────────────────────────
CREATE TABLE briefing_log (
    id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    date         DATE        NOT NULL UNIQUE,
    content_sent TEXT,
    sent_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- INDEXES (for faster queries)
-- ─────────────────────────────────────────────
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_status   ON tasks(status);
CREATE INDEX idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX idx_reminders_status    ON reminders(status);
```

### Step 3 — Get your Supabase credentials
In your Supabase project: Settings → API
- Copy `Project URL` → this is your `SUPABASE_URL`
- Copy `anon public` key → this is your `SUPABASE_KEY`

---

## 3. Required Environment Variables

Create a file called `.env` in the project root (same folder as `requirements.txt`).
Copy `.env.example` and fill in every value:

```
ANTHROPIC_API_KEY=sk-ant-...          # From console.anthropic.com
TWILIO_ACCOUNT_SID=AC...              # From Twilio Console
TWILIO_AUTH_TOKEN=...                 # From Twilio Console
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX     # Your Twilio number (with +1)
MY_PHONE_NUMBER=+1XXXXXXXXXX         # Your real phone number (with +1)
SUPABASE_URL=https://....supabase.co  # From Supabase → Settings → API
SUPABASE_KEY=eyJ...                   # anon/public key from Supabase
OPENWEATHER_API_KEY=...               # From openweathermap.org
CITY=Enterprise,AL,US                 # Your city for weather
BRIEFING_HOUR=7
BRIEFING_MINUTE=15
```

IMPORTANT: Phone numbers must be in E.164 format: +12223334444 (no spaces, no dashes).

---

## 4. Account Setup — All Services

### Anthropic API
1. Go to https://console.anthropic.com
2. Sign in with your Claude.ai account
3. Click "API Keys" → "Create Key"
4. Copy the key — you can only see it once

### Twilio
1. Go to https://twilio.com → sign up (free trial gives ~$15 credit)
2. Verify your phone number
3. Go to Console → "Get a phone number" → buy one (~$1/month)
4. Go to Console → Account Info → copy Account SID and Auth Token
5. Your Twilio number is on the main dashboard

### Supabase
Follow the SQL steps in Section 2 above.

### OpenWeatherMap
1. Go to https://openweathermap.org/api
2. Sign up (free)
3. Go to "My API Keys" → copy the default key
4. NOTE: New keys take up to 2 hours to activate

---

## 5. OpenWeatherMap Setup

The free tier (1,000 calls/day) is more than enough. The app calls it once per morning.

Test your key by pasting this in a browser (replace YOUR_KEY and your city):
```
https://api.openweathermap.org/data/2.5/weather?q=Enterprise,AL,US&appid=YOUR_KEY&units=imperial
```

You should get back a JSON object with temperature data. If you get a 401, the key
isn't active yet (wait 1-2 hours after creating a new account).

---

## 6. Twilio Setup

### Buy a number
1. Twilio Console → Phone Numbers → Manage → Buy a number
2. Search by area code if you want a local number
3. Make sure it has SMS capability (check the SMS checkbox)
4. Buy it (~$1.15/month)

### Configure the webhook
This is done AFTER you deploy (Section 10), but here's what you'll need:
- Navigate to: Phone Numbers → Manage → Active Numbers → click your number
- Under "Messaging" → "A Message Comes In":
  - Set type to "Webhook"
  - URL: `https://YOUR-RAILWAY-URL.railway.app/incoming`
  - Method: `HTTP POST`

---

## 7. Local Development Setup

### Prerequisites
- Python 3.11+ installed (check: `python --version`)
- A terminal (Terminal on Mac, Command Prompt or PowerShell on Windows)

### Step-by-step

```bash
# 1. Navigate to your project folder
cd personal-assistant

# 2. Create a virtual environment (keeps dependencies isolated)
python -m venv venv

# 3. Activate it
# On Mac/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy and fill in your .env
cp .env.example .env
# Now open .env in a text editor and fill in all values

# 6. Start the server
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

Open http://localhost:8000 in your browser. You should see:
```json
{"status": "running", "message": "Personal Assistant is online."}
```

### Expose your local server to the internet (for Twilio testing)

Twilio needs a public URL to send webhooks to. Use ngrok during development:

```bash
# Install ngrok: https://ngrok.com/download
# Then in a NEW terminal tab (keep uvicorn running):
ngrok http 8000
```

ngrok will give you a public URL like `https://abc123.ngrok.io`.
Use THAT URL as your Twilio webhook during local testing.

---

## 8. Testing Locally

### Test 1 — Health check
Open your browser: http://localhost:8000
Should return: `{"status": "running", ...}`

### Test 2 — Briefing preview (no SMS sent)
Open your browser: http://localhost:8000/briefing/preview
This generates a full briefing and shows it in the browser WITHOUT texting you.
Check that weather loads, formatting looks right.

### Test 3 — Trigger a real briefing (sends SMS)
In your terminal:
```bash
curl -X POST http://localhost:8000/briefing
```
You should receive a text message within a few seconds.

### Test 4 — Simulate an incoming text
You can simulate Twilio's webhook locally using curl:

```bash
# Test: create a reminder
curl -X POST http://localhost:8000/incoming \
  -d "From=%2B1YOUR_NUMBER" \
  -d "Body=Remind+me+tomorrow+to+call+John"

# Test: create a task
curl -X POST http://localhost:8000/incoming \
  -d "From=%2B1YOUR_NUMBER" \
  -d "Body=Add+study+wine+for+30+minutes"

# Test: mark complete
curl -X POST http://localhost:8000/incoming \
  -d "From=%2B1YOUR_NUMBER" \
  -d "Body=Mark+laundry+done"
```

Replace `%2B1YOUR_NUMBER` with your number (the + becomes %2B in URL encoding).
Example: if your number is +12045559876, use `%2B12045559876`

### Test 5 — Check Supabase
After running tests, go to Supabase → Table Editor → tasks
You should see the tasks you just created.

### Interactive API docs
FastAPI auto-generates docs at: http://localhost:8000/docs
You can test every endpoint from there with a UI.

---

## 9. Railway Deployment

Railway is the simplest way to host this. Free tier is enough for Phase 1.

### Step 1 — Push code to GitHub
```bash
# From your project folder:
git init
git add .
git commit -m "Initial commit — Phase 1 personal assistant"
# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/personal-assistant.git
git push -u origin main
```

### Step 2 — Deploy on Railway
1. Go to https://railway.app → Sign up with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `personal-assistant` repo
4. Railway will detect Python and auto-configure

### Step 3 — Add environment variables
In Railway: your project → Variables tab → "Add Variable"
Add EVERY variable from your `.env` file one by one:
- ANTHROPIC_API_KEY
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_PHONE_NUMBER
- MY_PHONE_NUMBER
- SUPABASE_URL
- SUPABASE_KEY
- OPENWEATHER_API_KEY
- CITY

### Step 4 — Get your public URL
Railway → your project → Settings → Domains
You'll see something like `personal-assistant-production.up.railway.app`
That's your public URL.

### Step 5 — Verify deployment
Open `https://YOUR-RAILWAY-URL/` in browser.
Should show: `{"status": "running", ...}`

---

## 10. Twilio Webhook Configuration

Now that you have a public URL from Railway:

1. Go to Twilio Console → Phone Numbers → Manage → Active Numbers
2. Click your phone number
3. Scroll to "Messaging Configuration"
4. Under "A Message Comes In":
   - Type: Webhook
   - URL: `https://YOUR-RAILWAY-URL/incoming`
   - Method: HTTP POST
5. Click Save

### Test the full loop
Text your Twilio number from your real phone:
"Remind me tomorrow to call John"

Within 5-10 seconds you should get a reply back.
Then check Supabase → tasks table — you should see the new task.

---

## 11. Morning Briefing Cron Job

You need something to hit `POST /briefing` every morning.
The simplest free solution: cron-job.org

### Setup with cron-job.org (free, no account limits)
1. Go to https://cron-job.org → sign up free
2. Click "Create Cronjob"
3. Fill in:
   - Title: "Han's Morning Briefing"
   - URL: `https://YOUR-RAILWAY-URL/briefing`
   - Schedule: Custom
   - Time: 07:15 (or whatever you want)
   - Timezone: America/Chicago (Central Time — Alabama)
   - Days: Every day
   - Request method: POST
4. Save

That's it. Every morning at 7:15 AM Central, cron-job.org will hit your endpoint
and your briefing will arrive as a text.

### Alternative: Railway Cron Service
Railway also has native cron support (slightly more advanced):
- Add a new service in Railway → "Cron Job"
- Command: `curl -X POST https://YOUR-URL/briefing`
- Schedule: `15 7 * * *` (7:15 AM UTC — adjust for your timezone)

---

## 12. Test Messages to Send

Once your Twilio webhook is live, text these to your Twilio number:

### Create reminders
```
Remind me tomorrow to call John.
Remind me Friday to pay Discover.
Remind me Saturday to review wine notes.
Remind me next week to follow up with the prospect from Monday.
```

### Create tasks
```
Add study wine for 30 minutes.
Add groceries to tomorrow.
Add pray and journal to this morning.
Add review NetSpark CRM notes.
```

### Mark complete
```
Mark laundry done.
Mark call John done.
I finished studying wine.
```

### Query your tasks
```
What do I have today?
What's on my list?
Show me my tasks.
```

### Edge cases (test the clarification flow)
```
Remind me about the thing.
Add it to tomorrow.
Mark that done.
```

These should trigger clarification questions back to you.

---

## 13. Common Bugs and How to Fix Them

─────────────────────────────────────────────────────────────────────────────
BUG: SMS comes in but nothing happens / no reply
─────────────────────────────────────────────────────────────────────────────
1. Check Railway logs: your project → Deployments → click latest → View Logs
2. Most common cause: MY_PHONE_NUMBER doesn't match exactly what Twilio sends
   Fix: Add a print statement temporarily:
        print(f"From: {repr(From)}, My number: {repr(MY_PHONE_NUMBER)}")
   Make sure both use E.164 format: +12223334444

─────────────────────────────────────────────────────────────────────────────
BUG: ImportError or ModuleNotFoundError on startup
─────────────────────────────────────────────────────────────────────────────
Most common: `python-multipart` not installed
Fix: pip install python-multipart
Then add it to requirements.txt and redeploy

─────────────────────────────────────────────────────────────────────────────
BUG: 422 Unprocessable Entity from the /incoming route
─────────────────────────────────────────────────────────────────────────────
FastAPI can't parse the form data. Usually means python-multipart is missing.
Also check that Twilio webhook is set to HTTP POST (not GET).

─────────────────────────────────────────────────────────────────────────────
BUG: Weather shows "Weather unavailable"
─────────────────────────────────────────────────────────────────────────────
1. New OpenWeatherMap keys take 1-2 hours to activate
2. Check your CITY value — use format: "Enterprise,AL,US" (no spaces around commas)
3. Test your key directly in a browser (see Section 5)

─────────────────────────────────────────────────────────────────────────────
BUG: Claude returns malformed JSON / classification fails
─────────────────────────────────────────────────────────────────────────────
The classifier has a fallback for this, so it won't crash — it'll ask for
clarification instead. But if it happens constantly:
1. Check your ANTHROPIC_API_KEY in Railway variables
2. Check Railway logs for the raw Claude response
3. Make sure you're using model "claude-sonnet-4-20250514"

─────────────────────────────────────────────────────────────────────────────
BUG: Supabase insert fails with "could not find the table"
─────────────────────────────────────────────────────────────────────────────
The SQL schema wasn't run, or ran with an error.
Fix: Go to Supabase → SQL Editor → re-run the full schema from Section 2.
Then Supabase → Table Editor — you should see tasks, reminders, briefing_log.

─────────────────────────────────────────────────────────────────────────────
BUG: "Mark laundry done" can't find the task
─────────────────────────────────────────────────────────────────────────────
The task title in the database needs to match the search keyword.
If you added the task as "Do laundry" but search for "laundry", it should still
work because the query uses ILIKE with wildcards (%laundry%).
If it still fails, check Supabase → tasks table to see the exact stored title.

─────────────────────────────────────────────────────────────────────────────
BUG: Railway build fails
─────────────────────────────────────────────────────────────────────────────
1. Check Railway build logs for the specific error
2. Most common: requirements.txt has a version conflict
   Fix: Remove all version pins and let pip resolve: just list package names
3. Make sure your Procfile is in the ROOT of the project (not inside app/)

─────────────────────────────────────────────────────────────────────────────
BUG: Getting texts but they say "Something went wrong on my end"
─────────────────────────────────────────────────────────────────────────────
This is the fallback from the classifier. Check Railway logs for the full error.
Usually: ANTHROPIC_API_KEY is wrong or has expired.

─────────────────────────────────────────────────────────────────────────────
BUG: Briefing never arrives in the morning
─────────────────────────────────────────────────────────────────────────────
1. Check cron-job.org → Job history — did it fire?
2. Check the timezone setting in cron-job.org (Alabama = America/Chicago, CST/CDT)
3. Test manually: POST https://YOUR-RAILWAY-URL/briefing
4. Check Railway logs for errors during briefing generation

─────────────────────────────────────────────────────────────────────────────
BUG: "422: value is not a valid integer" for PORT on Railway
─────────────────────────────────────────────────────────────────────────────
The Procfile uses $PORT which Railway injects automatically.
Make sure your Procfile is exactly:
  web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
No quotes around $PORT.

─────────────────────────────────────────────────────────────────────────────
GENERAL DEBUG TIP
─────────────────────────────────────────────────────────────────────────────
FastAPI has an automatic interactive docs page.
Locally:  http://localhost:8000/docs
Deployed: https://YOUR-RAILWAY-URL/docs

You can test every endpoint, see request/response schemas, and debug
without writing curl commands.

---

## Quick Reference Card

| What you want to do               | URL / Command                              |
|-----------------------------------|--------------------------------------------|
| Check server is running           | GET /                                      |
| Preview briefing (no SMS)         | GET /briefing/preview                      |
| Send briefing now                 | POST /briefing                             |
| Receive incoming SMS (Twilio)     | POST /incoming   (set as Twilio webhook)   |
| Interactive API docs              | GET /docs                                  |
| View your tasks                   | Supabase → Table Editor → tasks            |
| Start server locally              | uvicorn app.main:app --reload --port 8000  |

---

That's Phase 1. When it's working reliably for a few weeks, you're ready for Phase 2:
Google Calendar sync, shopping lists, and the clarification flow.
