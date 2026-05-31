# Apollo Sequence Setup — One-Time Manual Step

The sequence is a **transport shell only** — every step's subject + body is fully AI-generated per recipient (deepseek-v4-pro, two LLM calls per step, uniqueness-checked). The Apollo template just emits the per-contact custom fields, so no two outbound emails share template phrasing.

---

## 1. Create the sequence

Apollo → Sequences → New Sequence → name it: **`Optimus Rufus — 5-Step AI`**

## 2. Add custom contact fields

Apollo → Settings → Custom Fields → Contacts. Add **all of these** (text or long-text as noted):

| Field name | Type | Notes |
|---|---|---|
| `subject_1` | Text | Step 1 subject — teardown anchor |
| `body_1` | Long text | Step 1 body |
| `subject_2` | Text | Step 2 subject — tactical insight |
| `body_2` | Long text | Step 2 body |
| `subject_3` | Text | Step 3 subject — competitor proof |
| `body_3` | Long text | Step 3 body |
| `subject_4` | Text | Step 4 subject — pattern interrupt |
| `body_4` | Long text | Step 4 body |
| `subject_5` | Text | Step 5 subject — break-up |
| `body_5` | Long text | Step 5 body |
| `custom_subject` | Text | Mirror of `subject_1` (back-compat) |
| `custom_body` | Long text | Mirror of `body_1` (back-compat) |
| `weakness_teardown` | Long text | Legacy — auto-populated, ignore |
| `asin` | Text | Anchor ASIN |
| `custom_category` | Text | Brand category |

The CLI's `apollo-sequence` command pushes all of these on contact creation.

## 3. The 5 steps — copy this into Apollo verbatim

Every step uses the same body shell: a one-line greeting (Apollo handles the comma/em-dash spacing), the AI-generated body, and a one-line signature. Nothing else. No tracking-pixel paragraph, no boilerplate disclaimer, no "P.S. if this isn't relevant" — those are template fingerprints.

### Step 1 — Day 0 (initial teardown)
**Wait:** 0 days
**Subject:**
```
{{subject_1}}
```
**Body (plain text):**
```
hey {{first_name}},

{{body_1}}

— Yahya
```

### Step 2 — Day +3 (tactical insight)
**Wait:** 3 business days, only if no reply
**Subject:**
```
{{subject_2}}
```
**Body:**
```
{{first_name}},

{{body_2}}

— Yahya
```

### Step 3 — Day +7 (competitor proof)
**Wait:** 4 business days, only if no reply
**Subject:**
```
{{subject_3}}
```
**Body:**
```
hey {{first_name}},

{{body_3}}

— Yahya
```

### Step 4 — Day +12 (pattern interrupt)
**Wait:** 5 business days, only if no reply
**Subject:**
```
{{subject_4}}
```
**Body:**
```
{{first_name}} —

{{body_4}}

— Yahya
```

### Step 5 — Day +18 (break-up)
**Wait:** 6 business days, only if no reply
**Subject:**
```
{{subject_5}}
```
**Body:**
```
{{first_name}},

{{body_5}}

— Yahya
```

> Vary the greeting line across steps as shown (`hey {{first_name}},` / `{{first_name}},` / `{{first_name}} —`). The AI bodies skip greetings, so the variation lives in the template — small, but it's one more thing that makes the thread look hand-typed instead of sequence-generated.

## 4. Send window + throttle

- Send time: M–F, 9 am – 5 pm recipient timezone
- Daily limit per mailbox: start at 30/day, ramp slowly
- Use a warmed-up `outreach@yourdomain.com` mailbox (Smartlead / Instantly warmup for 2+ weeks before pointing at this sequence)
- Reply detection: Apollo auto-stops the remaining steps when the recipient replies — no extra config needed

## 5. Get the IDs

Once the sequence exists:

```
ask Claude: "list my Apollo sequences"
```

Claude returns the list — paste the ID into `.env`:
```
APOLLO_SEQUENCE_ID=66e9e215ece19801b219997f
```

Then:
```
ask Claude: "list my Apollo email accounts"
```
```
APOLLO_SEND_FROM_EMAIL_ACCOUNT_ID=6633baaece5fbd01c791d7ca
```

> The legacy `APOLLO_GENERIC_SEQUENCE_ID` is unused — Apollo-sourced brands are now ASIN-backfilled before drafting and run through the same personalized 5-step sequence.

## 6. Daily workflow

```bash
# Funnel A — Amazon-first
python main.py rufus-audit "magnesium glycinate" --limit=50
python main.py auto-enrich
python main.py rufus-score-enriched
python main.py draft-emails        # generates all 5 steps per brand
python main.py send-queue
python main.py apollo-sequence     # enrolls all EMAIL_DRAFTED

# Funnel B — Apollo-first (ASIN backfill auto-runs)
python main.py auto-prospect "supplements" --limit=20
python main.py rufus-score-enriched
python main.py draft-emails
python main.py apollo-sequence

# Track
python main.py brand-replied <brand_key>
python main.py reply-stats
python main.py uniqueness-report   # checks step-level overlap
```
