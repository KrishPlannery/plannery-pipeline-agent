# Claude Code Prompt: Plannery Pipeline Intelligence Agent

## BEHAVIORAL INSTRUCTIONS

Apply these to every decision, output, and code choice:

Your intellectual firepower, scope of knowledge, incisive thought process, and level of erudition are on par with the smartest people in the world. Answer with complete, detailed, specific answers. Process information and explain your answers step by step. Verify your own work. Double check all facts, figures, citations, names, dates, and examples. Never hallucinate or make anything up. If you don't know something, say so explicitly.

Never praise questions or validate premises before answering. If something is wrong, say so immediately. Lead with the strongest counterargument to any position before supporting it. Do not capitulate unless presented with new evidence or a superior argument. Use explicit confidence levels: High / Moderate / Low / Unknown. Accuracy is the success metric, not approval.

Before writing any code: state your architecture plan, explain the key design decisions, and flag any risks or tradeoffs. Wait for confirmation before proceeding if anything is ambiguous.

---

## WHAT YOU ARE BUILDING

A nightly AI agent that runs between 12:00 AM and 5:00 AM Pacific Time. It analyzes every active deal in two Plannery Attio pipelines, determines which accounts need follow-up based on a defined cadence schedule, researches each flagged account using web search, drafts a personalized follow-up email, and sends a Slack message to Krish with the draft for approval. When Krish approves via Slack comment, the agent sends the email through his Gmail account.

The agent also maintains a living skill file (`krish_email_skill.md`) that accumulates and summarizes Krish's email preferences, value prop priorities, and communication style. Every night it reviews and condenses this file before running the pipeline analysis.

This agent runs on a schedule — it is not triggered manually. It must be robust to API failures, rate limits, and empty pipelines. It must never send an email without explicit approval from Krish.

---

## ARCHITECTURE OVERVIEW

Build this as a single Python application with the following components:

```
plannery-agent/
├── main.py                    # Orchestrator — runs nightly, coordinates all components
├── attio_client.py            # Attio API wrapper
├── slack_client.py            # Slack bot — send messages, listen for approvals
├── gmail_client.py            # Gmail API — send approved emails
├── web_researcher.py          # Web search and news research per account
├── email_drafter.py           # Drafts emails using Claude API + skill file
├── skill_manager.py           # Reads, updates, and summarizes krish_email_skill.md
├── cadence_engine.py          # Determines which accounts need follow-up tonight
├── scheduler.py               # Cron scheduler (12 AM PT daily)
├── config.py                  # Environment variables and constants
├── krish_email_skill.md       # Living email preference file (auto-maintained)
├── state/
│   └── pending_approvals.json # Tracks messages sent to Slack awaiting approval
├── logs/
│   └── agent.log              # Nightly run logs
└── requirements.txt
```

---

## COMPONENT 1: CADENCE ENGINE

This is the decision brain. It reads every active deal from both Attio pipelines and determines whether a follow-up is due tonight based on the rules below.

### Pipeline Definitions

**Pipeline A: HealthStream Channel**
Attio list slug: `hospital_pipeline_healthstream`

**Pipeline B: Direct Channel**
Attio list slug: `hospital_pipeline_direct`

### Follow-Up Cadence Rules

#### HealthStream Pipeline

| Stage | Stage Name | Follow-Up Cadence | Cold Trigger |
|---|---|---|---|
| HS-1 | HS Flagged | Touch every 7 days until demo scheduled | 21 days no response → Cold |
| HS-2 | Demo Done | Touch every 7 days | 14 days no response → Cold |
| HS-3 | Benefits Engaged | Touch every 7 days | 21 days no movement → Cold |
| HS-4 | Verbal Commit | Touch every 5 days until activated | 21 days or 3 follow-ups → Cold |
| HS-5 | Live | Check-in at Day 7, Day 30 post-activation | Ongoing relationship |
| HS-6 | Enrolled | Quarterly check-in (every 90 days) | N/A |
| Cold | Cold | Week 1: value-add email. Week 3: dollar value email. Week 6: permission to close. Week 10: quarterly track | Re-engagement → return to last active stage |

#### Direct Pipeline

| Stage | Stage Name | Follow-Up Cadence | Cold Trigger |
|---|---|---|---|
| D-1 | Qualified Lead | Touch every 5 days | 14 days no response → Cold |
| D-2 | Discovery & Demo | Touch every 7 days | 14 days no response → Cold |
| D-3 | Multi-Stakeholder | Touch every 10 days | 28 days no movement → Cold |
| D-4 | Internal Review | Touch every 14 days | 35 days no update → Cold |
| D-5 | Contract | Touch every 7 days | 21 days no response → Cold |
| D-6 | Live | Check-in at Day 7, Day 30 | Ongoing |
| D-7 | Enrolled | Quarterly check-in (every 90 days) | N/A |
| Cold | Cold | Week 1: value-add. Week 3: dollar model. Week 6: permission to close. Week 10: quarterly track | Re-engagement → return to last active stage |

### Cadence Logic

For each active deal, the engine must:

1. Pull `last_email_interaction` and `last_calendar_interaction` from the Attio company record
2. Pull the current `stage` from the list entry
3. Calculate days since last contact (use the more recent of email or calendar)
4. Compare against the cadence rule for that stage
5. If follow-up is due: flag the account, pull full context, research, draft email
6. If cold threshold is crossed: flag for stage update to Cold AND draft re-engagement email
7. If no follow-up due: skip silently, log the decision

**Do not flag accounts where:**
- Last contact was within the cadence window
- Stage is HS-6 or D-7 (Enrolled) and last check-in was within 90 days
- A Slack approval is already pending for this account (check `pending_approvals.json`)

---

## COMPONENT 2: ATTIO CLIENT

Use the Attio REST API. Base URL: `https://api.attio.com/v2`
Authentication: Bearer token from environment variable `ATTIO_API_KEY`

Required operations:

```python
# Get all entries in a list with their stage and parent company record
GET /lists/{list_slug}/entries
# params: limit=500, offset=0

# Get full company record including all attributes and interaction history
GET /objects/companies/records/{record_id}

# Get notes on a company record (for deal history context)
GET /notes?parent_object=companies&parent_record_id={record_id}

# Update stage when moving to Cold
PATCH /lists/{list_slug}/entries/{entry_id}
body: {"data": {"stage": {"status": "Cold"}}}

# Add a note after sending an approved email
POST /notes
body: {
  "data": {
    "parent_object": "companies",
    "parent_record_id": "{record_id}",
    "title": "Follow-up email sent - {date}",
    "content": "{email body}"
  }
}
```

Build a rate-limit-aware client that:
- Retries on 429 with exponential backoff
- Logs all API calls with timestamp and response code
- Raises a typed exception on 4xx errors that are not retryable

---

## COMPONENT 3: WEB RESEARCHER

For each flagged account, the researcher must find recent, relevant context to personalize the follow-up email. This makes the email feel timely and informed rather than generic.

Use the Serper API (serper.dev) for full Google Search results without site restrictions. Authentication uses SEARCH_API_KEY from Secret Manager. POST requests to https://google.serper.dev/search with the API key in the X-API-KEY header. Search queries to run per account:

```python
queries = [
    f"{company_name} nursing shortage 2025 2026",
    f"{company_name} workforce retention news",
    f"{company_name} financial wellness employee benefits",
    f"{company_name} nurse turnover staffing",
    f"{company_name} hospital news {current_year}",
]
```

Rules:
- Run maximum 3 queries per account (pick the 3 most likely to yield relevant results based on the account's stage and last known conversation context)
- Fetch only articles published in the last 90 days
- Extract: headline, publication, date, URL, and a 2-sentence summary
- If no relevant results found, note that explicitly — do not fabricate context
- Cap total web research time per account at 45 seconds

Return a structured object:
```python
{
  "company": "Baptist Health South Florida",
  "recent_news": [
    {
      "headline": "...",
      "publication": "...",
      "date": "...",
      "url": "...",
      "summary": "..."
    }
  ],
  "research_confidence": "High | Moderate | Low",
  "research_notes": "..."
}
```

---

## COMPONENT 4: EMAIL DRAFTER

Uses the Claude API (`claude-sonnet-4-20250514`) to draft follow-up emails. Must read `krish_email_skill.md` before every draft run.

### System Prompt for Email Drafting

```
You are drafting follow-up emails on behalf of Krish Gopalakrishan, founder and CEO of Plannery Inc.

ABOUT KRISH AND PLANNERY:
Plannery is a healthcare fintech company offering AI-powered financial coaching and debt consolidation lending to healthcare workers, distributed through HealthStream. Plannery is already embedded in HealthStream's hStream Benefits platform. No cost to the hospital, no IT integration required, no liability for HR.

Key proof points to draw from when relevant:
- NPS: 86 among enrolled nurses
- Zero employee complaints across all hospital activations
- NSI 2026: each 1% reduction in RN turnover saves the average hospital $295,000
- NSI 2026: cost of RN turnover is $60,090 per nurse
- 75% of healthcare professionals experience financial stress daily (Nursegrid/Plannery 2024 survey)

KRISH'S EMAIL PREFERENCES:
{contents of krish_email_skill.md}

ACCOUNT CONTEXT:
- Company: {company_name}
- Pipeline: {pipeline_name}
- Stage: {stage_name}
- Days since last contact: {days_since_contact}
- Last interaction type: {last_interaction_type}
- Key contacts: {contacts}
- Recent Attio notes: {notes_summary}
- Recent web research: {research_summary}
- Cold sequence position (if Cold): {cold_week}

DRAFT RULES:
1. Never start with "I hope this finds you well" or any variant
2. Never use "just following up" or "circling back"
3. Lead with a specific, relevant hook — a news item, a data point, or a direct reference to the last conversation
4. The email must have one clear ask — not multiple asks
5. Maximum 150 words in the email body
6. Subject line must be specific — never generic like "Checking in" or "Following up"
7. If web research surfaced a relevant news item about this account, reference it naturally
8. Match the tone to the stage: warmer and more exploratory at early stages, more direct and time-aware at later stages
9. Never mention competitor products by name
10. Sign off as: Krish | Founder, Plannery | krishnan@planneryapp.com

OUTPUT FORMAT — return exactly this JSON:
{
  "subject": "...",
  "to": "contact email if known, else blank",
  "body": "...",
  "rationale": "one sentence explaining why this message was chosen for this account at this stage",
  "value_props_used": ["list of Plannery proof points used in the draft"],
  "research_used": true/false
}
```

### Cold Sequence Email Templates

For accounts in Cold stage, the agent must follow a prescribed sequence based on how many weeks the account has been in Cold. Override the general drafting instructions with these specific objectives:

- **Cold Week 1:** Lead with a new data point or Nursegrid insight. No ask for a meeting. Purely a value-add touch.
- **Cold Week 3:** Lead with the dollar model calculation specific to their hospital size. Make the inaction feel costly. One soft ask.
- **Cold Week 6:** The "permission to close" email. Short — under 80 words. Create loss aversion. Direct ask: are they interested or should we stop reaching out?
- **Cold Week 10:** Move to quarterly track. Tone shifts to long-term relationship, no immediate ask.

---

## COMPONENT 5: SLACK CLIENT

Build a Slack bot that:

**Sends messages** to a dedicated channel (environment variable `SLACK_CHANNEL_ID`) formatted as follows:

```
🏥 *[COMPANY NAME]* — [PIPELINE] | Stage: [STAGE NAME]
📅 Days since last contact: [N]
👤 Contact: [Name, Title]

*Why this account needs follow-up:*
[1-2 sentence explanation from cadence engine]

*Recent context:*
[Web research summary if available, else "No recent news found"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*📧 Proposed email:*

*Subject:* [subject line]

[email body]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reply to this message with:
• *approved* → sends immediately via Gmail
• *edit: [your revised version]* → sends your version via Gmail
• *skip* → skips this account tonight
• *cold* → moves account to Cold stage in Attio
```

**Listens for replies** using Slack's Events API (specifically `message.channels` events on the approval channel). Parse the reply:
- If reply starts with `approved` (case-insensitive): send the drafted email via Gmail
- If reply starts with `edit:`: send the text after `edit:` as the email body via Gmail
- If reply starts with `skip`: log and move on, do not update Attio
- If reply starts with `cold`: update Attio stage to Cold, do not send email

After any action (approved, edit, cold), post a confirmation reply in the same Slack thread:
```
✅ Email sent to [contact] at [timestamp] | Attio note added
```
or
```
❄️ [Company] moved to Cold in Attio
```

**Approval timeout:** If a Slack message has not received a reply within 48 hours, post a reminder in the thread: `⏰ This follow-up is still pending your approval. Reply approved, edit, skip, or cold.`

Store all pending approvals in `state/pending_approvals.json`:
```json
{
  "slack_message_ts": {
    "company_name": "...",
    "pipeline": "...",
    "stage": "...",
    "attio_record_id": "...",
    "attio_entry_id": "...",
    "contact_email": "...",
    "draft_subject": "...",
    "draft_body": "...",
    "created_at": "ISO timestamp",
    "expires_at": "ISO timestamp (48 hours later)"
  }
}
```

---

## COMPONENT 6: GMAIL CLIENT

Use the Gmail API with OAuth2. Credentials stored in environment variable `GMAIL_CREDENTIALS_JSON`.

```python
def send_email(to: str, subject: str, body: str, reply_to: str = None):
    # Send from krishnan@planneryapp.com
    # Always BCC: krishnan@planneryapp.com for record-keeping
    # Plain text only — no HTML
    # Add header: X-Plannery-Agent: pipeline-followup
```

After sending:
1. Add a note to the Attio company record via the Attio client with the full email body and timestamp
2. Remove the entry from `pending_approvals.json`
3. Log the send in `logs/agent.log`

---

## COMPONENT 7: SKILL MANAGER

Manages `krish_email_skill.md`. This file learns from every interaction and is summarized nightly to stay concise.

### File Structure

```markdown
# Krish Email Skill File
## Last summarized: [date]
## Version: [n]

## Email Style Preferences
[learned preferences about tone, length, structure]

## Value Props Krish Prioritizes
[which Plannery proof points he uses most, in which contexts]

## Opening Lines That Work
[patterns from approved emails]

## Phrases to Avoid
[patterns from edited or skipped emails]

## Stage-Specific Patterns
[what works at each pipeline stage]

## Account-Specific Notes
[any account-specific preferences learned]
```

### Update Logic

After each approved or edited email:
- If approved with no edits: note that the drafted style worked, extract any distinctive phrases
- If approved with edits (`edit:` command): compare the draft to the edit, extract the delta, note what changed and why (infer from the edit)
- If skipped: note that no email was appropriate tonight, do not extract style signals

### Nightly Summarization

Before the pipeline analysis runs each night, the skill manager must:
1. Read the current `krish_email_skill.md`
2. If the file exceeds 500 lines: call the Claude API to summarize it
3. Summarization prompt:

```
You are condensing a living skill file that captures email preferences for Krish Gopalakrishan, CEO of Plannery. 

The file has grown to {N} lines. Condense it to under 200 lines while preserving every distinct preference, pattern, and instruction. Do not generalize away specifics. Do not lose any rule that has been explicitly stated. Merge redundant entries. Keep the most recent version of any preference that has evolved over time.

Current file:
{file contents}

Return only the condensed file content, starting with the header.
```

4. Write the condensed version back to `krish_email_skill.md`
5. Log the summarization: original line count → new line count

---

## COMPONENT 8: ORCHESTRATOR (main.py)

The nightly run sequence, in exact order:

```python
async def nightly_run():
    log("=== Plannery Pipeline Agent — nightly run started ===")
    
    # Step 1: Summarize skill file if needed
    await skill_manager.summarize_if_needed()
    
    # Step 2: Check for pending Slack approvals from prior nights
    await slack_client.check_pending_approvals()
    
    # Step 3: Pull all active deals from both pipelines
    hs_deals = await attio_client.get_pipeline_entries("hospital_pipeline_healthstream")
    direct_deals = await attio_client.get_pipeline_entries("hospital_pipeline_direct")
    all_deals = hs_deals + direct_deals
    
    # Step 4: Run cadence engine — determine which accounts need follow-up
    flagged_accounts = cadence_engine.evaluate(all_deals)
    log(f"{len(flagged_accounts)} accounts flagged for follow-up tonight")
    
    # Step 5: For each flagged account — research, draft, post to Slack
    for account in flagged_accounts:
        try:
            # Research
            research = await web_researcher.research(account)
            
            # Pull full Attio context
            context = await attio_client.get_full_context(account.record_id)
            
            # Draft email
            draft = await email_drafter.draft(account, context, research)
            
            # Post to Slack
            ts = await slack_client.post_for_approval(account, draft, research)
            
            # Store in pending approvals
            state_manager.add_pending(ts, account, draft)
            
            # Rate limit — don't spam Slack
            await asyncio.sleep(30)
            
        except Exception as e:
            log(f"ERROR processing {account.company_name}: {e}")
            continue
    
    # Step 6: Update Cold stages in Attio for accounts that crossed threshold
    for account in cadence_engine.cold_escalations:
        await attio_client.update_stage(account, "Cold")
        log(f"Moved {account.company_name} to Cold")
    
    log(f"=== Nightly run complete. {len(flagged_accounts)} accounts processed ===")
```

**Error handling rules:**
- Never let a single account failure stop the entire run
- If the Slack API is down: log drafts locally, retry on next run
- If the Attio API is down: abort the run, send a Slack DM to Krish directly
- If the Claude API is down: log and skip drafting, post a raw summary to Slack instead

---

## COMPONENT 9: SCHEDULER

Use `APScheduler` with a cron trigger. Schedule: `0 0 * * *` (midnight PT). Convert to UTC: `0 8 * * *` (8:00 AM UTC = midnight PT, adjusting for daylight saving time dynamically).

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

scheduler = AsyncIOScheduler(timezone=pytz.timezone("America/Los_Angeles"))
scheduler.add_job(
    nightly_run,
    CronTrigger(hour=0, minute=0, timezone=pytz.timezone("America/Los_Angeles"))
)
```

Deploy on a always-on server (Railway, Fly.io, or a small DigitalOcean droplet). Do not use a serverless function — the nightly run may exceed 10 minutes for a full pipeline.

---

## ENVIRONMENT VARIABLES

```bash
ATTIO_API_KEY=                  # Attio API key
ANTHROPIC_API_KEY=              # Claude API key
SLACK_BOT_TOKEN=                # Slack bot OAuth token
SLACK_SIGNING_SECRET=           # Slack app signing secret
SLACK_CHANNEL_ID=               # Channel ID for pipeline approvals (e.g. #pipeline-followup)
SLACK_DM_USER_ID=               # Krish's Slack user ID for direct error alerts
GMAIL_CREDENTIALS_JSON=         # Path to Gmail OAuth2 credentials file
GMAIL_SENDER=                   # krishnan@planneryapp.com
SEARCH_API_KEY=                 # Serper API key (serper.dev)
SEARCH_PROVIDER=serper
TZ=America/Los_Angeles
```

---

## INITIAL krish_email_skill.md CONTENTS

Seed the file with the following before the first run. The agent will learn and update from here:

```markdown
# Krish Email Skill File
## Last summarized: initialized
## Version: 1

## Email Style Preferences
- Emails are short — 100 to 150 words maximum in the body
- Never start with "I hope this finds you well" or any greeting filler
- Never use "just following up", "circling back", "touching base", or "checking in"
- Lead with something specific — a news item, a data point, or a direct reference to the last conversation
- One clear ask per email — never multiple asks
- Tone is direct but warm — not corporate, not overly casual
- Write like a peer who has done their homework, not like a salesperson
- Subject lines are specific and curiosity-driven — never generic

## Value Props Krish Prioritizes
- Zero cost to the hospital and no IT integration required — leads with this for HR audiences
- NPS 86 among enrolled nurses — use this to defuse safety concerns
- Zero employee complaints across all activations — use this when HR raises liability concerns
- NSI 2026: each 1% reduction in RN turnover = $295,000 saved — use this for CFO/CNO audiences
- NSI 2026: $60,090 per RN turnover — use this to make the cost of inaction concrete
- Already embedded in HealthStream — reduces friction objection for HS pipeline accounts
- 75% of healthcare professionals experience daily financial stress (Nursegrid 2024)

## Opening Lines That Work
- Reference a specific news story about the hospital or health system
- Reference a data point from the Nursegrid survey relevant to their workforce
- Reference something said in the last meeting or email thread
- Ask a direct question that requires a yes/no answer

## Phrases to Avoid
- "I wanted to reach out"
- "Hope you are doing well"
- "As per my last email"
- "I wanted to follow up on"
- "Excited to share"
- "Revolutionary" or "game-changing"
- "Synergy" or "ecosystem"
- Any phrase that sounds like it was written by a marketing department

## Stage-Specific Patterns
- Early stages (HS-1, HS-2, D-1, D-2): Lead with insight or data. Soft ask. Build the relationship before pushing for a meeting.
- Mid stages (HS-3, D-3, D-4): More direct. Reference what was discussed. Clear ask for next step.
- Late stages (HS-4, D-5): Urgency is appropriate. Reference the specific next action needed to move forward.
- Cold accounts: Week 1 = pure value, no ask. Week 3 = make inaction costly. Week 6 = permission to close. Week 10 = long game.
- Enrolled accounts: Quarterly check-in. Reference their specific enrollment data if available. Ask how it is going for their team.

## Account-Specific Notes
[To be populated as the agent learns from interactions]
```

---

## SLACK CHANNEL SETUP

Create a private Slack channel called `#plannery-pipeline` (or use an existing channel — set the ID in `SLACK_CHANNEL_ID`). Invite the Plannery Slack bot to this channel. This is the only channel the bot posts to and monitors for replies.

The bot needs these OAuth scopes:
- `chat:write` — post messages
- `channels:history` — read replies
- `channels:join` — join the channel
- `users:read` — look up user IDs

Enable Event Subscriptions in the Slack app settings. Subscribe to `message.channels`. Set the request URL to your deployed server's `/slack/events` endpoint.

---

## DEPLOYMENT: GOOGLE CLOUD PLATFORM

Deploy to the existing Plannery GCP account. Do not use Railway or Fly.io.

### Architecture

```
Cloud Scheduler (12:00 AM PT daily)
    → triggers Cloud Run Job (nightly batch runner)
        → reads/writes state from Cloud Storage bucket
        → reads secrets from Secret Manager
        → posts to Slack, drafts via Claude API, researches via Search API

Cloud Run Service (always-on Slack listener)
    → receives Slack webhook events (message replies)
    → processes approvals, edits, skips, cold commands
    → sends Gmail, updates Attio, updates state in Cloud Storage
```

### Two Cloud Run Resources

**Resource 1: Cloud Run Job — nightly batch**
- Triggered by Cloud Scheduler at `0 0 * * *` America/Los_Angeles
- Runs `main.py`, completes, shuts down — no idle cost
- Max runtime: 30 minutes (set `--task-timeout 1800`)
- Machine type: `e2-standard-2` (2 vCPU, 8GB RAM)

**Resource 2: Cloud Run Service — Slack listener**
- Always-on, handles incoming Slack webhook POST requests
- Runs a lightweight FastAPI app at `/slack/events`
- Min instances: 1 (to avoid cold start delays on Slack event delivery)
- Machine type: `e2-micro`
- Set Slack Event Subscriptions request URL to this service's Cloud Run URL

### Persistent State: Cloud Storage

Create a GCS bucket: `gs://plannery-agent-state/`

Replace all local file operations with GCS reads/writes:

```python
from google.cloud import storage

def read_state_file(filename: str) -> str:
    client = storage.Client()
    bucket = client.bucket("plannery-agent-state")
    blob = bucket.blob(filename)
    return blob.download_as_text() if blob.exists() else ""

def write_state_file(filename: str, content: str):
    client = storage.Client()
    bucket = client.bucket("plannery-agent-state")
    blob = bucket.blob(filename)
    blob.upload_from_string(content)
```

Files stored in GCS:
- `krish_email_skill.md` — living email preference file
- `state/pending_approvals.json` — approvals awaiting Krish's response
- `logs/{date}.log` — nightly run logs (retained 30 days via lifecycle policy)

### Secrets: GCP Secret Manager

All credentials stored in Secret Manager under the `plannery` project. Never hardcode or pass as Cloud Run environment variables directly.

**Secrets to create:**

```
plannery/attio-api-key
plannery/anthropic-api-key
plannery/slack-bot-token
plannery/slack-signing-secret
plannery/slack-channel-id
plannery/slack-test-channel-id
plannery/slack-dm-user-id
plannery/gmail-oauth-token
plannery/search-api-key
plannery/search-provider
```

**Access pattern at runtime:**

```python
from google.cloud import secretmanager

def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/plannery-agents/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

ATTIO_API_KEY = get_secret("plannery/attio-api-key")
ANTHROPIC_API_KEY = get_secret("plannery/anthropic-api-key")
SLACK_BOT_TOKEN = get_secret("plannery/slack-bot-token")
SLACK_SIGNING_SECRET = get_secret("plannery/slack-signing-secret")
SLACK_CHANNEL_ID = get_secret("plannery/slack-channel-id")
SLACK_TEST_CHANNEL_ID = get_secret("plannery/slack-test-channel-id")
SLACK_DM_USER_ID = get_secret("plannery/slack-dm-user-id")
GMAIL_TOKEN_JSON = get_secret("plannery/gmail-oauth-token")
SEARCH_API_KEY = get_secret("plannery/search-api-key")
SEARCH_PROVIDER = get_secret("plannery/search-provider")
```

**Gmail OAuth note:** Run the initial OAuth flow once locally, save the token JSON, then upload to Secret Manager:

```bash
python scripts/gmail_auth.py
# Authenticate as krishnan@planneryapp.com in browser
gcloud secrets create plannery/gmail-oauth-token --data-file=token.json --project=plannery-agents-agents
```

After this one-time step, the agent reads and refreshes the token from Secret Manager automatically.

### Service Account and IAM

Create a dedicated service account:
```
pipeline-agent@plannery-agents.iam.gserviceaccount.com
```

Grant exactly these roles:
```
roles/secretmanager.secretAccessor   # read secrets
roles/storage.objectAdmin            # read/write GCS bucket
roles/run.invoker                    # allow Cloud Scheduler to trigger the job
```

Assign this service account to both Cloud Run resources. No credentials file needed — Cloud Run uses the service account identity automatically.

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Cloud Run Job:     CMD ["python", "main.py"]
# Cloud Run Service: CMD ["uvicorn", "slack_listener:app", "--host", "0.0.0.0", "--port", "8080"]
```

Build and push:
```bash
gcloud builds submit --tag gcr.io/plannery-agents/pipeline-agent
```

---

## TESTING

Implement four testing layers in sequence. Do not deploy to production until all four pass.

### Layer 1: Unit Tests (pytest)

Test every component in isolation using mocked external APIs. Must run in under 60 seconds with no real API calls.

```python
# tests/unit/test_cadence_engine.py

def test_hs2_flagged_after_14_days():
    deal = MockDeal(stage="Demo Done", pipeline="healthstream", days_since_contact=15)
    result = cadence_engine.evaluate([deal])
    assert len(result.flagged) == 1

def test_hs2_not_flagged_within_14_days():
    deal = MockDeal(stage="Demo Done", pipeline="healthstream", days_since_contact=10)
    result = cadence_engine.evaluate([deal])
    assert len(result.flagged) == 0

def test_cold_escalation_triggers_at_threshold():
    deal = MockDeal(stage="Demo Done", pipeline="healthstream", days_since_contact=15)
    result = cadence_engine.evaluate([deal])
    assert deal.company in [a.company for a in result.cold_escalations]

def test_enrolled_account_not_flagged_within_90_days():
    deal = MockDeal(stage="Enrolled", pipeline="direct", days_since_contact=60)
    result = cadence_engine.evaluate([deal])
    assert len(result.flagged) == 0

def test_pending_approval_account_skipped():
    deal = MockDeal(stage="Multi-Stakeholder", pipeline="direct", days_since_contact=30)
    state = {"existing_ts": {"company_name": deal.company}}
    result = cadence_engine.evaluate([deal], pending_approvals=state)
    assert len(result.flagged) == 0

def test_email_draft_under_150_words():
    draft = email_drafter.draft(mock_account, mock_context, mock_research)
    assert len(draft["body"].split()) <= 150

def test_cold_week_determined_correctly():
    deal = MockDeal(stage="Cold", cold_since_days=22)
    week = cadence_engine.get_cold_week(deal)
    assert week == 3
```

Write unit tests covering: every cadence threshold for both pipelines, cold week calculation, skill file summarization trigger (>500 lines), email word count, Slack message formatting, pending approval timeout (48 hours), stage update logic.

Run with:
```bash
pytest tests/unit/ -v --tb=short --cov=. --cov-report=term-missing
```

Target: 80%+ code coverage on `cadence_engine.py` and `email_drafter.py`.

### Layer 2: Integration Test Mode

Create a permanent test record in Attio:
- Company name: `TEST HOSPITAL — DO NOT CONTACT`
- Pipeline: Hospital Pipeline — Direct
- Stage: Discovery & Demo
- Last email interaction: set to 20 days ago

Run the agent against this record only:

```bash
python main.py --test-mode --account-id {test_record_id}
```

In `--test-mode`:
- Attio reads are real
- Web research is real
- Email is drafted real using the skill file
- Slack posts to `#plannery-pipeline-test` (create this channel)
- Gmail send intercepted — goes to `krishnan@planneryapp.com` only
- Attio stage and notes are NOT updated
- All output logged to `logs/test_{date}.json`

### Layer 3: Approval Flow Test

Verifies the full Slack → Gmail → Attio chain. Run manually before any production deployment and after any change to `slack_client.py`, `gmail_client.py`, or `attio_client.py`.

```bash
python tests/integration/test_approval_flow.py
```

This script:
1. Posts a synthetic approval request to `#plannery-pipeline-test`
2. Waits up to 5 minutes for a human reply — you reply `approved`
3. Verifies: test email delivered to `krishnan@planneryapp.com`, Attio note created on test record, `pending_approvals.json` entry removed
4. Tests the `edit:` flow: posts another request, you reply `edit: [text]`, verifies edited text was sent
5. Tests the `cold` flow: posts another request, you reply `cold`, verifies Attio stage updated, no email sent
6. Prints PASS/FAIL for each sub-test

### Layer 4: Nightly Smoke Test

Runs at the start of every nightly batch run before any pipeline analysis. If any check fails, the run aborts and Krish receives a Slack DM.

```python
async def smoke_test() -> bool:
    checks = []

    try:
        result = await attio_client.get_pipeline_entries("hospital_pipeline_healthstream")
        checks.append(("Attio API", True, f"{len(result)} entries returned"))
    except Exception as e:
        checks.append(("Attio API", False, str(e)))

    try:
        result = await claude_client.complete("Reply with the word OK only.")
        checks.append(("Claude API", "OK" in result, result[:50]))
    except Exception as e:
        checks.append(("Claude API", False, str(e)))

    try:
        result = await slack_client.post_to_test_channel("Smoke test ping")
        checks.append(("Slack API", result.ok, "message posted"))
    except Exception as e:
        checks.append(("Slack API", False, str(e)))

    try:
        val = get_secret("plannery/attio-api-key")
        checks.append(("Secret Manager", len(val) > 0, "secret accessible"))
    except Exception as e:
        checks.append(("Secret Manager", False, str(e)))

    try:
        read_state_file("krish_email_skill.md")
        checks.append(("Cloud Storage", True, "bucket accessible"))
    except Exception as e:
        checks.append(("Cloud Storage", False, str(e)))

    all_passed = all(c[1] for c in checks)

    if not all_passed:
        failed = [c for c in checks if not c[1]]
        msg = "⚠️ Pipeline agent smoke test FAILED\n"
        for name, _, error in failed:
            msg += f"• {name}: {error}\n"
        msg += "Nightly run aborted. Check Cloud Logging."
        await slack_client.send_dm(SLACK_DM_USER_ID, msg)
        return False

    return True
```

### CI/CD: GitHub Actions

Unit tests run automatically on every push and pull request. No real credentials required — all external APIs are mocked.

```yaml
# .github/workflows/test.yml
name: Unit Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit/ -v --tb=short --cov=. --cov-report=term-missing
      - name: Enforce 80% coverage
        run: pytest tests/unit/ --cov=. --cov-fail-under=80
```

### Test Environment Checklist

Before running any test against real APIs, confirm:
- `#plannery-pipeline-test` Slack channel exists and bot is invited
- `TEST HOSPITAL — DO NOT CONTACT` Attio record exists with last contact 20+ days ago
- `krishnan@planneryapp.com` is the only Gmail recipient used in test mode
- GCS bucket has a `test/` prefix for test state files — never overwrite production state during testing

---

## BUILD ORDER

Build and verify in this exact sequence. Do not proceed to the next step until the current one passes its tests.

1. `config.py` — Secret Manager integration, verify all secrets load from GCP
2. `attio_client.py` — read pipeline entries and company records, test against real Attio with a single known account
3. `cadence_engine.py` — full unit test suite passing before moving on
4. `web_researcher.py` — test with 3 real hospital names, verify search results and rate limiting
5. `skill_manager.py` — test read/write from GCS, update logic, and summarization with a padded test file
6. `email_drafter.py` — test with mock account context, verify output JSON format and word count enforcement
7. `slack_listener.py` — FastAPI app for Slack events, test locally with ngrok before deploying to Cloud Run
8. `slack_client.py` — test message posting and reply parsing against `#plannery-pipeline-test`
9. `gmail_client.py` — test send to `krishnan@planneryapp.com` only, verify token refresh from Secret Manager
10. `main.py` orchestrator — full `--test-mode` run against the test Attio record
11. Layer 3 approval flow test — manual end-to-end verification
12. Deploy Cloud Run Service (Slack listener) — set Slack webhook URL
13. Deploy Cloud Run Job + Cloud Scheduler — verify cron fires at correct PT time in Cloud Logging
14. Layer 4 smoke test — verify passes on first real scheduled run
15. First production run — monitor Cloud Logging in real time, verify no unintended Attio writes or Gmail sends
