# Plannery — Attio Pipeline Setup Instructions
## Feed this file into the Attio cleanup Cowork thread

---

## Context

Plannery has two distinct sales motions that must be tracked as **separate pipelines** in Attio. Do not merge them into a single pipeline — the stages, stakeholders, timelines, and exit criteria are fundamentally different. Mixing them produces misleading pipeline data and fires automation at the wrong time.

**Pipeline A: HealthStream Channel** — shorter cycle, verbal close, no IT/legal step
**Pipeline B: Direct Channel** — longer cycle, signed contract required, IT and legal review

Both pipelines share a **Cold** holding stage with channel-specific escalation thresholds.

---

## Lead Sources

Every deal must be tagged with its source on creation. The three sources are:

| Source Tag | Description |
|---|---|
| `HS-Webinar` | Hospital responded to the HealthStream rollout webinar (2 weeks ago, 1,400 hospitals reached) |
| `HS-AE` | HealthStream AE proactively referred or introduced the hospital |
| `David-Jones` | Referral from David Jones, CHRO advisor network |
| `Conference` | Met at a conference — specify conference name in notes |

---

## Pipeline A: HealthStream Channel

### Background
- HealthStream is both a distribution channel and a major Plannery investor
- Plannery is embedded in hStream Benefits — no IT or legal step required to activate
- The first HealthStream contact is the **clinical education lead** — not HR/benefits
- The clinical education lead must bridge to the **benefits or HR leader** for approval
- A closed deal in this pipeline is a **verbal agreement to turn Plannery on**
- Activation is a switch flip — same week as verbal in most cases

### Stages

| Stage ID | Stage Name | Definition | Exit Criteria to Advance |
|---|---|---|---|
| `HS-1` | **HS Flagged** | Clinical education lead has expressed interest or been identified from webinar or AE outreach. No Plannery conversation yet. | Plannery call scheduled with HS clinical education lead |
| `HS-2` | **Demo Done** | Plannery demo completed with HS clinical education lead. Krish has walked through the deck and product. | HS stakeholder commits to introducing or connecting benefits/HR leader |
| `HS-3` | **Benefits Engaged** | Benefits or HR leader is now in the conversation — either joined a meeting or looped in offline | Benefits leader has seen the demo or received the outcomes brief |
| `HS-4` | **Verbal Commit** | Hospital has verbally agreed to turn Plannery on | Plannery link activated in hStream — hospital is live |
| `HS-5` | **Live** | Plannery is active for this hospital's employees | First employee sign-up recorded AND launch communications sent to employees |
| `HS-6` | **Enrolled** | Hospital is producing active enrollment — ongoing relationship | Quarterly check-in cadence established |
| `HS-Cold` | **Cold** | No response after stage-specific threshold (see below) | Re-engagement received — move back to last active stage |

### Cold Escalation Thresholds — HS Pipeline

| From Stage | Threshold | Trigger |
|---|---|---|
| `HS-2` | 14 days no response from HS clinical education lead | Move to Cold |
| `HS-3` | 21 days benefits leader engaged but no movement | Move to Cold |
| `HS-4` | 21 days or 3 follow-ups with no verbal received | Move to Cold |

### Key Contacts to Track Per HS Deal

| Contact Role | Field Name in Attio | Notes |
|---|---|---|
| HealthStream Clinical Education Lead | `HS Clinical Lead` | First contact, internal HealthStream champion |
| Hospital Benefits / HR Leader | `Benefits Decision Maker` | Approver — deal cannot close without this person |
| Hospital HR Director or VP Benefits | `HR Contact` | May be same as Benefits Decision Maker |

---

## Pipeline B: Direct Channel

### Background
- Primary contacts: HR Benefits leader, VP Benefits, or CHRO (if David Jones referral)
- First call is a qualifying call — intro, needs discovery, and demo all in one meeting (Krish-led)
- Second meeting brings in additional stakeholders (clinical, finance, operations)
- After second meeting, hospital goes internal to make a decision
- If moving forward: **IT review and legal review are required** before contract
- A closed deal in this pipeline is a **signed Employee Services Agreement**

### Stages

| Stage ID | Stage Name | Definition | Exit Criteria to Advance |
|---|---|---|---|
| `D-1` | **Qualified Lead** | Initial contact established — CHRO referral or conference connection. Enough context to confirm worth pursuing. | Discovery and demo call scheduled |
| `D-2` | **Discovery & Demo** | First call completed. Krish has done intro, needs assessment, and demo. Qualifying determination made. | Confirmed worth pursuing AND second meeting scheduled with additional stakeholders identified |
| `D-3` | **Multi-Stakeholder** | Second meeting held with broader hospital team — may include clinical, finance, or operational leaders | Hospital confirms they are taking it internal to evaluate and make a decision |
| `D-4` | **Internal Review** | Hospital is evaluating internally. IT and legal review underway if moving forward. | IT sign-off AND legal sign-off both received — OR deal explicitly killed |
| `D-5` | **Contract** | IT and legal cleared. Contract sent, in review, or being negotiated. | Signed Employee Services Agreement received |
| `D-6` | **Live** | Contract signed. Plannery activated for this hospital's employees. | First employee sign-up recorded AND launch communications sent |
| `D-7` | **Enrolled** | Hospital producing active enrollment — ongoing relationship | Quarterly check-in cadence established |
| `D-Cold` | **Cold** | No movement after stage-specific threshold (see below) | Re-engagement received — move back to last active stage |

### Cold Escalation Thresholds — Direct Pipeline

| From Stage | Threshold | Trigger |
|---|---|---|
| `D-2` | 14 days no response to schedule follow-up meeting | Move to Cold |
| `D-3` | 28 days second meeting done but no internal movement signal | Move to Cold |
| `D-4` | 35 days in internal review with no update | Move to Cold — note: this stage legitimately takes time, do not trigger too early |
| `D-5` | 21 days contract in review with no response | Move to Cold |

### Key Contacts to Track Per Direct Deal

| Contact Role | Field Name in Attio | Notes |
|---|---|---|
| Primary Contact | `Primary Contact` | Who we met first — CHRO, HR Director, conference connection |
| Benefits Decision Maker | `Benefits Decision Maker` | The approver — may or may not be same as primary contact |
| IT Contact | `IT Contact` | Only relevant at Stage D-4 and beyond |
| Legal Contact | `Legal Contact` | Only relevant at Stage D-4 and beyond |

---

## Deal-Level Fields — Required on Every Record (Both Pipelines)

These fields must exist on every deal record regardless of pipeline. Build them as custom fields in Attio.

| Field Name | Type | Values / Notes |
|---|---|---|
| `Pipeline` | Single select | `HealthStream` / `Direct` |
| `Lead Source` | Single select | `HS-Webinar` / `HS-AE` / `David-Jones` / `Conference` |
| `Conference Name` | Text | Only populated if Lead Source = Conference |
| `C-Suite Visibility` | Checkbox / Boolean | Has CNO or CFO been made aware of this initiative? Deals without this at Stage 3+ rarely close. |
| `C-Suite Contact` | Contact link | CNO, CFO, or CHRO who has visibility |
| `Hospital Bed Count` | Number | For dollar model calculation |
| `Estimated RN Count` | Number | For NSI turnover cost calculation |
| `Current Attrition Rate` | Percentage | If known — sourced from hospital or estimated |
| `Competing Benefits` | Multi-select | `Kashable` / `Salary Finance` / `Fidelity EAP` / `Lyra` / `Magellan` / `Other EAP` / `Other Financial Wellness` / `None Known` |
| `Last Contact Date` | Date | Updated automatically via Attio email integration |
| `Last Contact Type` | Single select | `Email Sent` / `Email Replied` / `Meeting Held` / `Verbal Received` / `Contract Sent` |
| `Cold Reason` | Single select | `No Response` / `Budget` / `Timing` / `Wrong Stakeholder` / `Lost to Competitor` / `Deprioritized` |
| `Dollar Impact Estimate` | Currency | Calculated: RN Count × 20% attrition × $60,090 × estimated Plannery lift % |
| `HealthStream AE Owner` | Contact link | The HS AE responsible for this account (HS pipeline only) |
| `Notes` | Long text | Running log of key conversation points, objections raised, internal champion status |

---

## Immediate Data Entry — Two Hospitals Already Committed

Two hospitals verbally agreed to turn on Plannery following the HealthStream rollout webinar two weeks ago. These deals must be entered immediately if not already in Attio.

For each of the two hospitals:
- Pipeline: `HealthStream`
- Lead Source: `HS-Webinar`
- Stage: `HS-4` (Verbal Commit) if not yet live, or `HS-5` (Live) if Plannery link has already been activated
- Verify: has the Plannery link actually been turned on in hStream for each hospital? If yes → `HS-5`. If pending → `HS-4`.
- Add last contact date, hospital name, and benefits decision maker contact if known

Do not let these two deals sit without a stage assignment. They are the first data points in the pipeline and the first test of whether the rescue sequences will fire correctly.

---

## The Two Weekly Metrics to Surface in Attio

Configure Attio views or reports to surface these two numbers every week:

**1. Committed Pipeline Count**
Deals at stage `HS-4` or higher (HS pipeline) and `D-5` or higher (Direct pipeline). This is the real number toward the 26-hospital goal.

**2. Stage 3 Age — Average Days**
Average number of days deals have been sitting at `HS-3` (Benefits Engaged) or `D-3` (Multi-Stakeholder) without movement. If this average exceeds 21 days, the C-suite visibility gap is happening at scale and needs immediate attention.

---

## Notes for the Attio Cleanup Thread

1. **Build Pipeline A (HealthStream) and Pipeline B (Direct) as two separate pipeline objects in Attio** — not two views of the same pipeline. Stage names, field requirements, and automation triggers differ enough that merging them will cause confusion.

2. **The Cold stage should exist in both pipelines** with the same name (`Cold`) for consistency. Automation that monitors for Cold deals can then watch both pipelines with a single rule.

3. **Attio email tracking** — ensure email integration is active so that `Last Contact Date` and `Last Contact Type` update automatically when emails are sent or received. This is the data that drives the cold escalation logic in Agent 3 (Pipeline Rescue Agent). If email tracking is not active, the rescue automation cannot function.

4. **Contact deduplication** — a single hospital contact (e.g., a Benefits Director) may appear in both the People list and as a deal contact. Ensure the People cleanup resolves duplicates before pipeline contacts are linked, otherwise deal records will have orphaned or duplicate contact associations.

5. **The `Competing Benefits` field is critical for Agent 1** (Hospital Research Agent) — this field should be populated either manually from early conversations or automatically from Agent 1's research output. Specifically flag `Kashable` and `Salary Finance` — both are direct Plannery competitors with similar payroll-deduction mechanics and require a different objection-handling approach.
