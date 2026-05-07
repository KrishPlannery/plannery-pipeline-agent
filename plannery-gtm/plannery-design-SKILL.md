# Plannery Design System — SKILL.md
## Invoke this skill for any Plannery document, slide, or visual output

---

## How to Use This Skill

When this skill is invoked, apply every rule in this file before producing any output. Do not improvise colors, fonts, or layout patterns. Do not substitute similar-looking alternatives. If a required asset (logo file, image) is not available in the working directory, state what is missing before proceeding.

This skill covers: PowerPoint decks, Word documents, PDFs, one-pagers, HTML artifacts, React components, and any other visual output created on behalf of Plannery.

---

## 1. Brand Colors

These are the only approved colors. Use exact hex values — no approximations.

### Primary Palette

| Token | Hex | Usage |
|---|---|---|
| `purple-main` | `#795AF7` | Primary brand color. CTAs, key headlines, icon fills, gradient starts, highlight borders, logo icon. |
| `green-main` | `#35BA3A` | Success states, positive data callouts, checkmarks, "approved" indicators. |
| `blue-main` | `#0AA1FF` | Links, secondary accents, data visualization, informational callouts. |

### Extended Palette (derived from slides and UI)

| Token | Hex | Usage |
|---|---|---|
| `purple-dark` | `#3D2C8D` | Dark text on light backgrounds, deep section headers, navy-adjacent roles. |
| `purple-light` | `#C4B5FD` | Subtle tints, background fills, hover states, tag backgrounds. |
| `purple-bg` | `#EDE9FE` | Card backgrounds, callout box fills, light section washes. |
| `purple-gradient-start` | `#795AF7` | Gradient covers: left/top |
| `purple-gradient-end` | `#5B21B6` | Gradient covers: right/bottom |
| `gray-text` | `#4B5563` | Body copy on white backgrounds. |
| `gray-dark` | `#1F2937` | Primary heading text on white. Never pure black. |
| `gray-light` | `#F3F4F6` | Alternate row fills, subtle section backgrounds. |
| `white` | `#FFFFFF` | Page backgrounds, card fills, text on dark/purple backgrounds. |
| `black-bg` | `#1A1A1A` | Dark mode logo presentation only. |

### Gradient Specification

The primary Plannery gradient (used on cover slides, hero sections, full-bleed backgrounds):
```
Linear gradient: 135deg
Start: #795AF7 (purple-main)
End: #5B21B6 (purple-dark)
```
This gradient reads as a rich, confident purple. It is the single most recognizable Plannery visual element. Use it for slide covers, section dividers, and hero banners. Do not use it for body content areas.

### Color Rules

- **Never use pure black (`#000000`)** for text. Use `gray-dark` (`#1F2937`).
- **Never use competing gradients** — teal-to-green, blue-to-purple, etc. One gradient system only.
- **Never use red** except for error states in UI. It reads as danger/loss in a financial context.
- **Green is success only** — do not use `green-main` for general accent or decorative purposes.
- **Purple is the hero** — when in doubt about which color to use, use purple.

---

## 2. Typography

### Font Family

**Primary font: Poppins** (Google Fonts, free)

Poppins is geometric, rounded, and warm — it matches the Plannery brand voice of being approachable but credible. Use it for all text in all documents.

Fallback stack: `Poppins, Inter, -apple-system, sans-serif`

**Never substitute:** Arial, Helvetica, Calibri, or Times New Roman. If Poppins is unavailable in the output environment (e.g., Word DOCX on a machine without Poppins installed), flag this to the user before proceeding.

### Type Scale

| Level | Size | Weight | Color | Usage |
|---|---|---|---|---|
| Display / Hero | 52–60pt | Bold (700) | White or purple-dark | Cover slide headlines only |
| H1 | 36–40pt | Bold (700) | gray-dark or white | Section title, document title |
| H2 | 26–28pt | SemiBold (600) | purple-main | Subsection headers |
| H3 | 20–22pt | SemiBold (600) | gray-dark | Card headers, callout labels |
| Body Large | 18–20pt | Regular (400) | gray-text | Lead paragraphs, key stats |
| Body | 14–16pt | Regular (400) | gray-text | Standard body copy |
| Caption / Label | 10–12pt | Medium (500) | gray-text or purple-main | Footnotes, source citations, tags |
| CTA / Button | 14–16pt | Bold (700) | White (on purple button) | Action labels |

### Typography Rules

- **Headlines are sentence case**, not ALL CAPS (exception: tagline "WE ♥ HEALTHCARE WORKERS" stays in caps as a brand lockup)
- **Never use italic for emphasis** in headlines — use weight instead (Regular → Bold)
- **Italic is acceptable** for quotes, testimonials, and source citations only
- **Line height:** 1.4× for body, 1.2× for headlines
- **Letter spacing:** Normal for body, slight tracking (+0.02em) for all-caps labels and tags

---

## 3. Logo Usage

### Logo Variants

Plannery has three logo variants. Use the correct one for each context.

| Variant | When to Use |
|---|---|
| **Full logo — light background** | White or light-colored slide backgrounds, documents on white, one-pagers. The "p" icon is purple, the wordmark "plannery" is dark gray (`#4B5563`). |
| **Full logo — dark/purple background** | Gradient slide covers, dark section backgrounds, purple headers. Both icon and wordmark render in white. |
| **Icon only (P mark)** | Slide footers, app icons, favicon contexts, space-constrained corners. The P-mark is the speech-bubble-P shape in purple. |

### Logo Placement Rules

- **Cover slides:** Full logo centered or upper-center, always white version on gradient background
- **Interior slides:** Icon-only in bottom-left footer, approximately 32–40px height
- **Documents:** Full logo top-left on cover page; icon-only in footer of subsequent pages
- **Minimum clear space:** Equal to the height of the circular part of the "p" icon on all sides
- **Minimum size:** Full logo never smaller than 120px wide; icon never smaller than 32px
- **Never stretch, rotate, recolor, or add drop shadows to the logo**
- **Never place the dark-background logo on a light surface or vice versa**
- **Never place the logo on a busy photographic background** without a semi-transparent overlay (purple at 60–70% opacity) behind it

### Tagline

"WE ♥ HEALTHCARE WORKERS" — this is the official Plannery tagline. The ♥ is a literal heart character, not the word "love." Use it:
- Below the full logo on cover slides
- In email headers and campaign materials
- Never in body copy or as a standalone without the logo

---

## 4. Slide Design System (PowerPoint / Presentations)

These rules apply to all Plannery presentation decks. Study the Pinnacle Hospital deck as the canonical reference.

### Slide Dimensions

Standard widescreen: **1920 × 1080px** (16:9)

### Slide Types and Templates

**Type 1: Cover Slide**
- Full-bleed gradient background (purple-main → purple-dark, 135deg)
- Optional: healthcare photography at 30–40% opacity beneath gradient
- Partner logo centered top-third
- Large "+" separator between partner logo and Plannery logo
- Plannery full logo (white version) centered
- Tagline "WE ♥ HEALTHCARE WORKERS" below logo in white, 16pt, letter-spaced
- Main headline below in white, 48–52pt Bold
- Subtitle in white at 60% opacity, 24pt Regular

**Type 2: Two-Column Content Slide**
- White background
- Bold headline in gray-dark, 36pt
- Optional subtitle in purple-main, 24pt SemiBold (see "The twin challenge in healthcare" slide)
- Left column: purple-bg card with rounded corners (12px radius), content in gray-dark
- Right column: gray-light card with rounded corners, content in gray-dark
- Card padding: 32px all sides
- Icons: 3D emoji-style or flat purple icon above card title

**Type 3: Stat/Data Slide**
- White background
- Bold centered headline in gray-dark, 40pt
- Stats displayed as donut charts or large numerals
- Donut chart: purple-main fill color, gray-light track, percentage in center Bold 32pt
- Stat labels in gray-text 16pt below each chart
- Four-column layout for four stats, three-column for three

**Type 4: Feature/Product Slide**
- White background
- Centered headline + purple subtitle
- Three equal-width feature cards with purple-bg fill, rounded corners
- Card header in gray-dark Bold 20pt
- Bullet points in gray-text 16pt Regular
- Bottom banner: full-width purple-main gradient strip with white bold text for key proof points (e.g., "No cost for hospitals | No IT integration | No liability for hospitals")

**Type 5: Operational/Checklist Slide**
- White background
- Left-aligned headline in gray-dark, 36pt Bold
- Left accent bar: 4px vertical line in purple-main flush to left margin
- Bullet points in gray-dark 18pt Regular
- Clean, minimal — no cards, no color fills

**Type 6: Three-Column Timeline/Phases Slide**
- White background
- Bold left-aligned headline
- Three cards with purple-main header bar (white text Bold), purple-bg body fill
- Body bullet points with purple-main text for action items, gray-dark for context
- Equal column widths with 16px gaps

**Type 7: Closing/Thank You Slide**
- White background
- Large stylized "Thank you" script (can use a script font or handwriting asset)
- Contact card: centered, thin purple border, white fill
  - Name in gray-dark Bold 24pt
  - Title in purple-main Bold 14pt all-caps
  - Email in gray-text 16pt Regular

### Slide Rules

- **One primary message per slide** — readable in 5 seconds
- **Never exceed 3 bullet points per card or column**
- **Bullet points max 12 words each** — if it needs more words, it needs its own slide
- **No slide transitions or animations** in export-facing decks (they break in PDF and cause distraction in live presentations)
- **Rounded corners on all cards:** 12px radius consistently
- **Drop shadows:** use sparingly, only on cards that need lift from background. Soft shadow: `0 4px 16px rgba(0,0,0,0.08)`
- **No clip art.** Use 3D emoji-style icons (as in the existing slides) or Heroicons-style flat icons in purple-main

---

## 5. Document Design System (Word / PDF / One-Pagers)

### Page Setup

- **US Letter:** 8.5 × 11 inches, 1-inch margins all sides
- **Font:** Poppins throughout
- **Body text:** 11pt Regular, gray-text
- **Line spacing:** 1.4

### Document Color Application

- Section headers: H1 in gray-dark, H2 in purple-main
- Callout boxes: purple-bg fill (`#EDE9FE`), 3pt top border in purple-main, label in purple-main Bold
- Tables: header row in purple-dark with white Bold text; alternating rows gray-light / white; all borders `#D1D5DB` 1pt
- Pull quotes or key statistics: 28–32pt Bold, purple-main, centered with subtle purple-bg background strip

### One-Pager Specific Rules

- Maximum one page, front only
- Headline in purple-main or gray-dark, 28–32pt Bold
- Three-column feature layout or two-column comparison — never single-column wall of text
- One prominent dollar figure or statistic in 48pt Bold as the visual anchor
- Footer: Plannery icon + website + "Confidential" in 9pt gray-text

---

## 6. UI / Product Design Reference

The Plannery app UI (sign-up flow) establishes the product aesthetic. When building web components, HTML artifacts, or React mockups that represent Plannery's product:

### App Design Patterns

- **Backgrounds:** White cards on white or very light gray (`#F9FAFB`) page background
- **Primary CTA button:** Full-width, purple-main fill, white Bold text, 8px border radius, 48px height
- **Secondary button:** White fill, purple-main border 2px, purple-main text
- **Input fields:** Light gray border (`#D1D5DB`), 8px radius, 14px Poppins Regular placeholder text
- **Step indicators:** Numbered circles, purple-main fill for completed/active, gray-light for upcoming
- **Progress bar:** purple-main fill on gray-light track
- **Header:** White background, Plannery full logo left, tagline right or centered
- **Form layout:** Single column, generous padding (24px), questions in gray-dark Bold 20pt, helper text in gray-text 14pt
- **FAQ accordions:** Chevron icon in purple-main, answer text in gray-text 16pt
- **Legal/disclosure text:** gray-text 11pt, bottom of screen, never prominent

### App Voice in UI Copy

- Friendly, direct, never clinical or bureaucratic
- Progress labels: "Nice to meet you!", "Almost there!", "You're doing great" — warm, encouraging
- Error messages: never blame the user; always suggest the solution
- CTA labels: "Continue", "Apply Now", "Next Step" — active verbs, never passive

---

## 7. Brand Voice and Tone

This is as important as the visual system. Plannery's design is not just how things look — it is how they sound.

### The Core Tension

Plannery is a financial services company serving nurses and healthcare workers. This creates a specific tension to navigate:

- **Too casual:** loses credibility as a financial product handling people's money and debt
- **Too formal/corporate:** alienates nurses who are skeptical of financial institutions and overwhelmed by jargon

The target: **friendly, funny, and credible** — like the smartest friend who works in finance and actually cares about you.

### Voice Characteristics

**Speaks like a human, not a company**
- ✅ "Your nurses are already one click away from financial relief"
- ❌ "Plannery's platform provides healthcare employees with access to financial wellness resources"

**Uses the clinical world's language**
- Reference shifts, not schedules
- Reference nurses, MAs, travel nurses — not "healthcare workers" generically unless addressing a broad audience
- Acknowledge the reality: "We know you didn't go to nursing school to worry about debt"

**Confident about data, humble about complexity**
- Lead with the number: "$60,090. That's what it costs to replace one nurse."
- Acknowledge the hard stuff: "Financial stress doesn't show up in exit interviews. But it's there."

**Warm without being saccharine**
- "WE ♥ HEALTHCARE WORKERS" is the north star — genuine, not performative
- Avoid: "We're passionate about empowering nurses to achieve financial wellness" (corporate-speak)
- Use: "We built Plannery because healthcare workers deserve better than payday loans and empty budgeting apps"

**Humor is allowed, carefully**
- Light, self-aware, never at the expense of the audience
- ✅ "No, we're not another financial app that tells you to stop buying coffee"
- ❌ Jokes about debt, medical errors, or anything that could feel dismissive of the real stress nurses carry

### Voice by Audience

| Audience | Tone Adjustment |
|---|---|
| Hospital HR / Benefits Leaders | More formal, data-forward, ROI-focused. Credibility first, warmth second. |
| Hospital C-Suite (CFO/CNO) | Direct, financial, no fluff. Dollar figures and outcomes. |
| Nurses / Clinical Staff | Warm, human, peer-level. Acknowledge their reality before pitching anything. |
| HealthStream AEs | Collegial, practical, tool-oriented. Give them the hook and get out of the way. |
| Investors | Precise, market-aware, growth-oriented. The warm brand voice takes a back seat to the business case. |

---

## 8. What Plannery Design Never Does

These are hard rules. No exceptions.

- **No clip art or stock illustration** — photography (real people, preferably healthcare workers) or 3D icons only
- **No competing gradients** — only the purple gradient system
- **No rainbow color usage** — the palette is disciplined. Introducing orange, red, or yellow as design elements breaks the system.
- **No all-caps body text** — all-caps is reserved for short labels and the tagline only
- **No Comic Sans, Papyrus, or decorative script fonts** — Poppins everywhere
- **No drop shadows on text** — ever
- **No busy, patterned backgrounds** for content slides — gradients yes, patterns no
- **No logos on colored backgrounds without testing contrast** — always verify the logo is legible
- **No walls of text on slides** — if the content requires more than 60 words on a slide, it needs to be split or moved to a document
- **No financial fear language** — never use words like "debt trap," "drowning in debt," or "financial ruin" in Plannery materials. The brand positions Plannery as the solution, not a reminder of the problem's severity.

---

## 9. Asset Reference

The following assets exist and should be used when available in the working directory:

| Asset | Filename | Usage |
|---|---|---|
| Full logo, dark background (white version) | `Logo_Light.png` | Cover slides, dark backgrounds |
| Icon only, purple | `PurpleIcon.png` | Footers, favicons, space-constrained |
| Logo usage reference sheet | `CleanShot_2026-05-05...png` | Reference for correct logo application |
| Product UI reference | `Sign_Up.png` | When building product mockups or app-facing designs |
| Pinnacle Hospital deck | `Plannery_AIFC_Overview_for_Pinnacle_Hospital.pdf` | Canonical slide style reference |

When producing a new deck or document, check the working directory for these files before starting. If they are not present, ask the user to provide the logo files before generating output.

---

## 10. Quick Checklist Before Any Output

Before delivering any Plannery design output, verify:

- [ ] Colors: only hex values from Section 1 used
- [ ] Font: Poppins specified (or flagged as unavailable)
- [ ] Logo: correct variant for the background (light vs. dark)
- [ ] Gradient: purple-main to purple-dark only, never competing gradients
- [ ] Voice: friendly, credible, human — not corporate-speak
- [ ] Headlines: sentence case, not ALL CAPS (except tagline)
- [ ] Slides: one message per slide, max 3 bullets per card
- [ ] Data: every statistic sourced (NSI 2026, Nursegrid/Plannery 2024 survey, etc.)
- [ ] No clip art, no patterned backgrounds, no decorative script fonts
- [ ] Logo files present in working directory or flagged as missing
