# Pre-Mortem: GTM Failure Modes
## Plannery GTM Reference — What Kills This Strategy and How to Detect It Early

---

## How to Use This Document

Assume it is 18 months from now and the strategy failed. What killed it?

This document identifies every credible failure mode, its probability and severity, the earliest detectable warning sign, and the fix. Read this before the Nashville HealthStream meeting. Return to it at every monthly pipeline review.

The two failure modes that should change what you build first: **AE channel never activates** and **retention data stays uncleaned.** Everything else in the strategy is sound but depends on those two foundations being real, not assumed.

---

## Failure Mode Summary Table

| # | Failure Mode | Probability | Severity | Earliest Warning Sign |
|---|---|---|---|---|
| 1 | AE channel never activates | High | Fatal | Fewer than 2 Plannery introductions per AE per month after 60 days |
| 2 | Retention data stays uncleaned | Moderate-High | Fatal | Still saying "meaningful improvement in retention" without a matched number |
| 3 | LinkedIn content goes inconsistent | High | Serious | Any gap of more than 10 days between posts |
| 4 | CRM data too dirty for automation | Moderate | Serious | Cannot answer which deals have had zero contact in 14+ days |
| 5 | No internal champion beyond HR | Moderate | Serious | Deals feel warm but never reach a second stakeholder |
| 6 | HealthStream incentives drift | Low-Moderate | Fatal | AE introduction rates drop without explanation over a quarter |
| 7 | Financial stress framing backfires | Low-Moderate | Moderate | Low email open rates despite good list quality |

---

## Failure Mode Detail

---

### 1. AE Channel Never Activates

**Probability: High. This is the most likely failure mode by far.**

The strategy is entirely predicated on HealthStream AEs consistently introducing Plannery in their conversations. The assumption that is probably wrong: that a partnership agreement and good enablement materials translate into AE behavior change.

HealthStream AEs have quota on HealthStream products. Plannery is a favor they do, not a number they make. The specific failure chain: AEs receive the enablement kit, say it's great, use it twice. The first two conversations don't close quickly. AE deprioritizes. No one is tracking AE-level Plannery conversation rates. Six months pass. Plannery is functionally invisible in AE conversations. Krish has no visibility into this until pipeline is already dry.

**Earliest warning sign:** Fewer than 2 Plannery introductions per AE per month after 60 days from partnership launch.

**The fix:**
- The Nashville meeting with HealthStream CEO, COO, and key leaders must produce a written operational plan — not goodwill. Specifically: agreed AE introduction rate metrics, a tracking mechanism, and named AE champions.
- Identify 3–5 AEs who are genuinely enthusiastic early adopters. Build the entire program around making them successful first. Proof of concept within the channel before trying to scale across it.
- Negotiate the AE introduction rate metric into the partnership before building anything else. Without this metric, the channel cannot be managed.

---

### 2. Retention Data Stays Uncleaned

**Probability: Moderate-High.**

The entire messaging architecture rests on a credible, specific retention claim. The raw enrollment-vs-non-enrollment comparison is not usable with analytically literate hospital administrators — it is immediately dismissible as selection bias. The propensity-matched, dose-response analysis is the credible version.

The failure chain: the analysis stays on the to-do list. We operate with vague retention language — "hospitals see meaningful improvement in retention" — which every competing vendor also says. Nothing differentiates. HR contacts feel no urgency because there is no specific, credible number that makes their current inaction feel costly.

**Earliest warning sign:** Any sales material or outreach that says "meaningful improvement" or "significant retention lift" without a specific matched percentage and confidence interval.

**The fix:**
- The outcomes analysis (Agent 2) is not a marketing project. It is the precondition for marketing. It must be complete before outreach sequences launch, not concurrently.
- Data required: T0 roster, loan application file (applied / qualified / received loan), T1 roster. If this data is not clean and accessible, clean it before building anything else.
- Output required: matched retention lift percentage with 95% confidence interval, three-group dose-response finding, dollar model by hospital size using NSI 2026 figures.

---

### 3. LinkedIn Content Goes Inconsistent

**Probability: High.**

Founder-led LinkedIn content looks manageable until week 6, when there are three more urgent things to do and the post doesn't go up. Then week 7. Then it's been a month. LinkedIn's algorithm punishes inconsistency sharply — momentum built over weeks is lost after one gap. The awareness pre-sell effect disappears. HealthStream AEs continue starting every conversation from zero.

**Earliest warning sign:** Any gap of more than 10 days between posts.

**The fix:**
- Commit to a specific production system before starting: Agent 4 batch-drafts 8 posts monthly, Krish edits, 20 minutes per week. That is sustainable.
- Winging it weekly is not sustainable. If that system cannot be committed to, exclude this channel from the strategy entirely. Starting and stopping is worse than not starting because it signals unreliability to the algorithm and to followers.

---

### 4. CRM Data Too Dirty for Automation

**Probability: Moderate.**

The pipeline rescue sequences require that deals are logged in Attio with consistent stage tagging, contact information, and last-activity tracking. The failure pre-condition: pipeline tracking is informal or inconsistent, and there is no reliable way to know which deals have gone quiet.

The failure chain: Agent 3 is built to monitor stage changes and trigger rescue sequences, but the underlying data is missing or inconsistent. The system fires at the wrong time, misses stalled deals, or sends follow-ups to the wrong contact. Automation built on bad data does not fix the pipeline problem — it automates the chaos.

**Earliest warning sign:** Cannot answer, in under 10 minutes, which deals have had zero contact in 14+ days.

**The fix:**
- Before building the rescue sequence, conduct a full pipeline audit in Attio. For every active deal: when was it last touched? Who is the contact? What stage is it actually in?
- Attio cleanup (already in progress in a separate Cowork thread) must be complete before Agent 3 is built. The agent is only as good as the data it reads.

---

### 5. No Internal Champion Beyond HR

**Probability: Moderate.**

Outreach successfully generates responses from HR Directors and VP Benefits. Conversations happen. Interest is genuine. And then nothing closes because the HR contact cannot get internal approval without C-suite visibility. HR goes quiet not because they lost interest but because they hit an internal wall they don't know how to get over.

The failure chain: marketing generates activity at the HR level, which feels like progress. But the actual decision requires CFO or CNO buy-in on a retention initiative, and neither has been touched. The wrong conversion metric is being optimized.

**Earliest warning sign:** Deals that feel warm from the HR contact's engagement but never progress to a second stakeholder meeting within 4 weeks.

**The fix:**
- Build a CFO/CNO-facing version of the outcomes brief — dollar-denominated, no product language, pure retention ROI argument — that HR can forward upward without modification. One page. The $295,000 per 1% RN turnover figure (NSI 2026) is the anchor.
- Train HealthStream AEs to ask, before tagging a deal as progressing: "Does your CNO or CFO have visibility into this retention initiative?" If the answer is no, the deal is not actually progressing.

---

### 6. HealthStream Incentives Drift

**Probability: Low-Moderate. Severity: Fatal.**

HealthStream launches a competing financial wellness product, deprioritizes Plannery in favor of a higher-margin partnership, or undergoes leadership change that resets the relationship. None of these are controllable and any of them effectively zeroes out the primary channel.

**Earliest warning sign:** AE introduction rates drop without explanation for two consecutive months, or a HealthStream product announcement in the financial wellness category.

**The fix:**
- The Nashville meeting must produce a written operational plan, not just goodwill. Verbal alignment does not survive leadership transitions.
- Begin planting direct channel seeds now — the LinkedIn presence, outcomes data, and content assets being built should be designed to eventually support a direct sales motion even if that is not the immediate goal. Build assets to be channel-agnostic even while deploying them primarily through HealthStream.
- This is a business architecture fix, not a marketing fix. It belongs in the investor and board conversation, not just the GTM plan.

---

### 7. Financial Stress Framing Backfires

**Probability: Low-Moderate.**

The awareness strategy relies on HR leaders being willing to engage with a framing that implies their workforce has a financial problem. Some HR leaders will not engage publicly with this framing because doing so is an implicit admission that their compensation and benefits design is inadequate — which reflects on them.

**Earliest warning sign:** Low email open rates (below 25%) on outreach sequences despite strong list quality and compelling subject lines. Silence rather than negative responses — they are not objecting, they are not opening.

**The fix:**
- Attribute financial stress to systemic causes — student debt loads, healthcare salary structures, cost of living — not to the hospital's benefit design. Giving HR a systemic explanation for the problem gives them permission to engage without feeling implicated.
- Test two subject line variants: one that leads with the financial stress angle ("The hidden driver of nurse turnover") and one that leads with the retention cost angle ("What one percent of RN turnover costs your hospital"). If the financial stress variant underperforms, shift to the retention cost frame universally.
