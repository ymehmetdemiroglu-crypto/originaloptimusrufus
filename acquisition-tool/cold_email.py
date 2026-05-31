"""Cold-email generator — fully AI-generated, unique per recipient.

Two LLM calls per brand:
  1. Subject — short, curiosity-driven, tied to worst Rufus axis
  2. Body — 3-4 dashed lines + a short opener + soft CTA, grounded in the
     anchor ASIN's per-axis Rufus weaknesses, with at least 2 explicit
     "when a shopper asks Rufus 'X'..." constructions

Both are stored on the brand (custom_subject, custom_body) and pushed into
Apollo as custom fields so the sequence template is just `{{custom_subject}}`
and `{{custom_body}}` — no shared phrasing across recipients.

Anti-template guards:
  - Banned-phrase regex on subject and body
  - 5-gram shingle overlap check against the last 50 generated bodies (max
    25% overlap, otherwise regenerate up to 2 times)
"""
import asyncio
import json as _json
import logging
import random
import re
import threading
from typing import Optional

import httpx
from openai import OpenAI

import config
import db
from models import Prospect, Brand
import resilience



OPENROUTER_CHAT_URL = f"{config.OPENROUTER_BASE_URL}/chat/completions"


def _openrouter_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


_client = None
_client_lock = threading.Lock()

AXIS_LABEL = {
    "intent_alignment_score": "intent",
    "attribute_density_score": "attribute",
    "conversational_readability_score": "conversational",
    "qa_coverage_score": "qa",
    "visual_structured_content_score": "visual",
    "competitive_relativity_score": "competitive",
}

# ---------------------------------------------------------------------------
# Anti-template guards — loaded from external JSON so they can be updated
# without code redeploy.  See rules/banned_phrases.json
# ---------------------------------------------------------------------------
import dynamic_rule_engine as _rules


def _subject_banned() -> list[str]:
    return _rules.subject_banned_phrases()


def _body_banned() -> list[str]:
    return _rules.body_banned_phrases()

SHOPPER_QUERY_RE = re.compile(r"asks?\s+rufus\s+['\"]", re.IGNORECASE)


# Per-step intent — drives both the system prompt and the user prompt suffix.
STEP_SPECS = {
    1: {
        "label": "teardown anchor",
        "min_words": 90, "max_words": 140,
        "needs_shopper_query": 2,
        "intent": (
            "First-touch teardown of the worst ASIN. Open with one concrete observation "
            "from this specific listing, then 3-4 dashed lines that name the gap and "
            "translate it into a Rufus consequence. End with a curiosity-driven reference "
            "to the Rufus Visibility Calculator — the URL will be appended after generation, "
            "so the body should end with one sentence that sets up the link naturally."
        ),
    },
    2: {
        "label": "tactical insight",
        "min_words": 60, "max_words": 90,
        "needs_shopper_query": 1,
        "intent": (
            "Day-3 follow-up. Do NOT recap step 1. Drop ONE specific listing fix the "
            "founder could ship today (a Q&A to seed, a bullet to rewrite, an attribute "
            "to add) tied to the worst Rufus axis. Two short paragraphs. Soft nudge at end."
        ),
    },
    3: {
        "label": "competitor proof",
        "min_words": 70, "max_words": 110,
        "needs_shopper_query": 1,
        "intent": (
            "Day-7 follow-up. Use the ACTUAL competitor data provided to show what a specific "
            "competitor (name them by brand) does on the worst axis that this brand doesn't. "
            "Quote their bullet count, Q&A count, or a phrase from their bullets when relevant. "
            "Frame as observation, not threat. End by offering to send the side-by-side."
        ),
    },
    4: {
        "label": "pattern interrupt",
        "min_words": 25, "max_words": 45,
        "needs_shopper_query": 0,
        "intent": (
            "Day-12 follow-up. THREE sentences max. One blunt question that earns a yes/no. "
            "No dashed lines. No recap. No CTA softener."
        ),
    },
    5: {
        "label": "break-up",
        "min_words": 50, "max_words": 80,
        "needs_shopper_query": 0,
        "intent": (
            "Day-18 break-up. Close the loop without guilt. Acknowledge timing might be "
            "off, leave the teardown offer standing, do not ask for a reply. Warm, brief, done."
        ),
    },
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)
    return _client


def _worst_axis(anchor: Prospect) -> str:
    """Return the axis label of the lowest Rufus axis score."""
    scores = {
        k: getattr(anchor, k)
        for k in AXIS_LABEL
        if getattr(anchor, k) is not None
    }
    if not scores:
        return "intent"
    worst = min(scores, key=scores.get)
    return AXIS_LABEL[worst]


def _shingles(text: str, n: int = 5) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def max_overlap(candidate: str, corpus: list[str]) -> float:
    """Highest jaccard-ish overlap (intersect / candidate size) vs any corpus item."""
    cand = _shingles(candidate)
    if not cand:
        return 0.0
    best = 0.0
    for prior in corpus:
        prior_sh = _shingles(prior)
        if not prior_sh:
            continue
        overlap = len(cand & prior_sh) / len(cand)
        if overlap > best:
            best = overlap
    return best


def _contains_banned(text: str, banned: list[str]) -> Optional[str]:
    low = (text or "").lower()
    for phrase in banned:
        if re.search(r'\b' + re.escape(phrase) + r'\b', low):
            return phrase
    return None


# ---------------------------------------------------------------------------
# Subject generation
# ---------------------------------------------------------------------------

SUBJECT_SYSTEM = """You write cold-email subject lines for emails sent to Amazon brand founders.

Each subject must be totally unique — no shared template across recipients.

Rules:
- 4 to 9 words. Lowercase is fine. No emojis, brackets, or punctuation other than ? and ,
- One concrete, curiosity-driven hook tied to a SPECIFIC weakness on their listing
- Forbidden: "quick note", "quick question", "checking in", "audit", the word "free", the brand name, the founder's name
- Do not start with "re:" or "fwd:"
- Sound like a peer who pulled up the listing 5 minutes ago, not a sequence

Output: exactly 3 candidate subject lines, one per line, no numbering, no quotes."""


def _build_subject_prompt(brand: Brand, anchor: Prospect, worst_axis: str) -> str:
    axis_blurb = {
        "intent": "the title/bullet copy doesn't match how shoppers actually phrase queries",
        "attribute": "the listing is missing structured attributes (mg, cert badges, dietary flags) Rufus needs to cite",
        "conversational": "the copy is marketing-speak, not quotable sentences Rufus can pull",
        "qa": "the Q&A section doesn't cover the questions Rufus would be asked",
        "visual": "the listing lacks visual content and structured A+ modules Rufus can reference",
        "competitive": "the listing falls behind competitors on Rufus-extractable content",
    }[worst_axis]
    return f"""Brand: {brand.brand_name}
Category: {anchor.category or brand.category or 'consumer product'}
ASIN: {anchor.asin}
Worst Rufus axis: {worst_axis} — {axis_blurb}
Rufus summary: {anchor.rufus_summary or '(none)'}

Write 3 candidate subject lines."""


def generate_subject(brand: Brand, anchor: Prospect, worst_axis: str) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=config.OPENROUTER_DRAFT_MODEL,
        max_tokens=120,
        temperature=0.9,
        messages=[
            {"role": "system", "content": SUBJECT_SYSTEM},
            {"role": "user", "content": _build_subject_prompt(brand, anchor, worst_axis)},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    candidates = [
        re.sub(r"^[\"'\-\*\d\.\)]+\s*", "", line).strip().strip('"').strip("'")
        for line in raw.splitlines()
        if line.strip()
    ]
    candidates = [c for c in candidates if c and not _contains_banned(c, _subject_banned())]
    if not candidates:
        # Fallback: synth a minimal subject from the axis (still not a fixed template)
        return {
            "intent": f"the wording gap on {anchor.asin}",
            "attribute": f"what {anchor.asin} doesn't tell rufus",
            "conversational": f"why rufus skips {anchor.asin}",
            "qa": f"the question rufus can't answer about {anchor.asin}",
            "visual": f"the visual gap on {anchor.asin}",
            "competitive": f"why competitors beat {anchor.asin} in rufus",
        }[worst_axis]
    return random.choice(candidates)


# ---------------------------------------------------------------------------
# Body generation
# ---------------------------------------------------------------------------

BODY_SYSTEM_TEMPLATE = """You are an elite B2B cold-email copywriter ghost-writing a 5-step outbound sequence for Yahya, an Amazon listing-optimization consultant. Every recipient is the founder/owner of a small consumer-goods brand selling on Amazon. You have just audited their worst-performing ASIN for how it surfaces in Amazon's Rufus AI shopping chat (the AI that answers "best magnesium for sleep?" / "is this dog treat safe for puppies?" style questions and recommends specific products).

You are writing STEP {step_num} of 5 — "{step_label}".
STEP INTENT: {intent}

==================================================================
THE TWO THINGS YOU MUST GET RIGHT
==================================================================

(1) THE EMAIL MUST FEEL HAND-WRITTEN FOR THIS SPECIFIC FOUNDER.
Across thousands of sends, NO TWO EMAILS at this step number may share more than incidental phrasing. Treat every draft as if it will be diff-checked against the previous fifty. If your opener could plausibly fit any other supplement / skincare / pet brand on Amazon, it's wrong — rewrite until it could only have been written about THIS listing.

(2) THE EMAIL MUST EARN A REPLY, NOT JUST AVOID THE SPAM FOLDER.
The recipient is a busy founder with a full inbox of bad cold outreach. They reply only when an email proves the sender (a) actually opened the listing, (b) saw something specific, and (c) is offering a useful fact, not a meeting request. Every line should pass the "would I forward this to my co-founder?" test.

==================================================================
VOICE (non-negotiable)
==================================================================
- Peer-to-peer. Smart operator messaging another smart operator. Never salesy, never sycophantic.
- Lowercase sentence-starts are fine and often preferable. Do NOT Title Case anything except the brand name and the ASIN.
- Short sentences. Most under 14 words. Never two adverbs in one sentence. Never two prepositional phrases stacked end-to-end.
- Concrete > clever. A line that names the actual missing Q&A entry beats a clever metaphor every time.
- Sound like the email was written 60 seconds after pulling up the listing — because it was.
- One emotion only: clear-eyed observation. No enthusiasm, no urgency, no flattery, no apology.

==================================================================
HARD RULES — any single violation triggers regeneration
==================================================================

1. LENGTH: {min_words} to {max_words} words total. Count before you submit.

2. FORBIDDEN OPENERS (or any paraphrase). The first sentence of the body must not match the meaning of any of these:
   "I noticed your...", "I came across your brand", "I hope this finds you",
   "I hope you're well", "Hope you're doing well", "I wanted to reach out",
   "I've been following...", "Congrats on...", "Just following up",
   "Bumping this", "Quick question", "Quick note", "Hope you don't mind".

3. FORBIDDEN PHRASES anywhere in the body (these are spam-classifier fingerprints AND template-fingerprints):
   revolutionize, leverage, synergy, unlock, transform, seamlessly,
   reach out, just checking in, excited to, happy to share, valuable insights,
   take your business to the next level, game-changer, move the needle,
   I'd love to, circle back, touch base, partner with you, at your earliest convenience,
   make sense, sounds good, low-hanging fruit, no-brainer, exciting opportunity.

4. NO GREETING. NO SIGN-OFF. The Apollo template already handles "hey {{first_name}}," and "— Yahya". Output ONLY the body. If you write a greeting or signature, the entire draft is discarded.

5. NO MARKDOWN. No bold, no italics, no headings, no numbered lists, no asterisks for emphasis. Plain text only. Dashes for list lines if and only if the step intent calls for them.

6. SHOPPER-QUERY CONSTRUCTIONS: include AT LEAST {needs_shopper_query} construction(s) of this form somewhere in the body:
       when a shopper asks Rufus "<plausible category-specific query>", <consequence>
   where <consequence> names which competitor gets recommended, which question goes unanswered, or which attribute Rufus can't cite. If {needs_shopper_query} is 0, do NOT force one in — that's the step's choice.
   The query must be one a real shopper of THIS category would actually type. "best magnesium for sleep" — yes. "what is the best supplement for my health needs" — no.

7. NO META-LANGUAGE. Never reference "this email", "this sequence", "my last message", "step 2", "follow-up", or the fact that an email is being sent. The reader should feel addressed, not processed.

8. NO TRACKING-PIXEL POETRY. No "P.S." line. No "if this isn't relevant, no worries". No "feel free to ignore". No closing hedge. End on the line that earns the reply.

==================================================================
GROUNDING RULES
==================================================================
- Use ONLY data given in the user prompt (axis scores, weakness signals, raw bullets, category, ASIN, ratings, counts). Do NOT invent facts about the listing, the brand's history, the founder, the company size, or competitors.
- If numbers are given (bullet count, image count, Q&A count, character count, rating, review count), reference AT LEAST ONE of them by its actual value. Quoting their number is the strongest "I actually looked" signal.
- Quote a phrase from the listing title or bullets when natural. A 4-6 word direct quote in the opener is the single highest-leverage move you can make.
- The "worst Rufus axis" given is the spine of the entire 5-step sequence. Every step you write must circle the same axis from a different angle. Do not pivot to a different axis even if it would be easier copy.

==================================================================
PRIOR STEPS IN THIS SEQUENCE
==================================================================
If prior step bodies are shown in the user prompt, they were sent to THIS SAME founder before this step. You must NOT:
- repeat any opener phrase or sentence shape from a prior step
- repeat the same CTA framing (if step 1 offered a "1-page teardown", step 3 cannot offer a "1-page teardown" — offer a side-by-side, a checklist, a 5-minute Loom, etc.)
- reference the prior emails directly ("as I mentioned", "following up on my last") — the recipient knows
- summarize what step 1 said
You may, and should, advance the same underlying argument. Different angle, different surface, same axis.

==================================================================
OUTPUT
==================================================================
Plain text. Body only. No subject. No greeting. No signature. No commentary. No preamble like "Here's the body:" or "Sure, here you go:". Begin directly with the first word of the first sentence."""


# Kept for any legacy importers expecting BODY_SYSTEM (single-step alias = step 1).
BODY_SYSTEM = """You write cold-email bodies sent to Amazon brand founders. The sender audited the founder's listing for how it performs in Amazon's Rufus AI shopping chat.

Every email must read as if hand-written for this specific founder and ASIN. NO shared template across recipients.

Voice:
- Peer-to-peer. Lowercase is fine. Short sentences.
- Sound like someone who opened the listing 60 seconds ago and is being straight with the founder.

Hard rules:
- DO NOT start with: "Hi {first_name}, I noticed", "Hope you're well", "I came across your brand", "I hope this finds you", "I wanted to reach out"
- Each email must use a DIFFERENT opener. Vary structure across drafts.
- Body length: 90 to 140 words total
- Banned: revolutionize, leverage, synergy, unlock, transform, seamlessly, reach out, just checking in, excited to, happy to share

Structure (in this order, no headings):
1. One short opener (1 sentence) referencing something concrete about their ASIN — a number, a phrase from the listing, a specific gap. Never a generic compliment.
2. 3 to 4 dashed lines, each naming ONE concrete weakness AND translating it to a Rufus consequence. AT LEAST 2 of the dashed lines must include an explicit "when a shopper asks Rufus '<actual query>'..." construction. Use plausible category-specific shopper queries.
3. One short closing line offering to send a free 1-page teardown. No "let me know if interested" — make it a direct, low-friction ask.

Format: plain text only. No markdown, no signature (the Apollo sequence appends that). No subject line in the output."""


def _build_body_prompt(brand: Brand, anchor: Prospect, worst_axis: str,
                       step_num: int = 1, prior_steps: list[str] | None = None) -> str:
    signals = brand.weakness_signals or anchor.weakness_signals or ""

    competitors = db.get_competitors(brand.brand_key)
    competitor_block = ""
    if competitors:
        competitor_block = "\n\nTOP COMPETITORS:\n"
        for i, c in enumerate(competitors[:3], 1):
            competitor_block += (
                f"\n{i}. {c.get('competitor_brand', 'Unknown')} — {c.get('title', '')[:80]}\n"
                f"   Bullets: {c.get('bullet_count', 0)} | Images: {c.get('image_count', 0)} | "
                f"Q&A: {c.get('qa_count', 0)} | A+: {'yes' if c.get('has_a_plus') else 'no'}\n"
                f"   Bullet text: {c.get('bullets', '')[:400]}\n"
            )

    rufus_block = ""
    if anchor.rufus_score is not None:
        rufus_block = (
            f"\nRufus Optimization Score: {anchor.rufus_score}/100 "
            f"(citation probability: {anchor.rufus_citation_probability or '?'})\n"
            f"  Intent Alignment:           {anchor.intent_alignment_score}/25\n"
            f"  Attribute Density:          {anchor.attribute_density_score}/25\n"
            f"  Conversational Readability: {anchor.conversational_readability_score}/25\n"
            f"  Q&A Coverage:               {anchor.qa_coverage_score}/25\n"
            f"Rufus Summary: {anchor.rufus_summary}"
        )
        if anchor.rufus_top_weaknesses:
            try:
                weaknesses = _json.loads(anchor.rufus_top_weaknesses)
                if weaknesses:
                    rufus_block += "\nRufus Top Weaknesses:"
                    for w in weaknesses:
                        rufus_block += f"\n  [{w.get('axis','?')}] {w.get('issue','')} → {w.get('fix','')}"
            except Exception:
                pass

    multi_asin_note = ""
    if brand.asin_count and brand.asin_count > 1:
        multi_asin_note = (
            f"\nNote: this brand has {brand.asin_count} weak listings; the ASIN "
            f"below is the worst one — use it as the case study."
        )

    spec = STEP_SPECS[step_num]
    prior_block = ""
    if prior_steps:
        prior_block = "\n\nPRIOR STEPS IN THIS SEQUENCE (do not repeat their phrasing):\n"
        for i, prev in enumerate(prior_steps, start=1):
            prior_block += f"\n--- step {i} ---\n{prev}\n"

    return f"""Write the body for STEP {step_num} of 5 ({spec['label']}) of a cold-email sequence to this Amazon brand founder. The worst Rufus axis is "{worst_axis}" — keep it the spine of the whole sequence.

Founder first name: {brand.contact_first_name or 'there'}
Brand: {brand.brand_name}
Category: {anchor.category or brand.category or 'consumer product'}
Anchor ASIN: {anchor.asin}
Title ({len(anchor.post_title or '')} chars): {anchor.post_title}
Bullet count: {anchor.bullet_count}
Image count: {anchor.image_count}
Has A+ content: {anchor.has_a_plus}
Q&A count: {anchor.qa_count}
Rating: {anchor.listing_rating}
Review count: {anchor.listing_review_count}
Rule-based weakness signals: {signals}
{rufus_block}{multi_asin_note}

Bullets (raw, truncated):
{(anchor.post_body or '')[:1200]}{prior_block}

CALCULATOR LINK (step 1 only — append after generation, do NOT include raw URL in body): {config.CALCULATOR_BASE_URL}/?asin={anchor.asin}&ref=cold&utm_source=cold_email&utm_campaign=rufus_audit

Write the full body now. Length: {spec['min_words']}-{spec['max_words']} words. Required shopper-query constructions: {spec['needs_shopper_query']}."""


def _step_system_prompt(step_num: int) -> str:
    spec = STEP_SPECS[step_num]
    return BODY_SYSTEM_TEMPLATE.format(
        step_num=step_num,
        step_label=spec["label"],
        intent=spec["intent"],
        min_words=spec["min_words"],
        max_words=spec["max_words"],
        needs_shopper_query=spec["needs_shopper_query"],
    )


def _generate_body_once(brand: Brand, anchor: Prospect, worst_axis: str,
                        step_num: int, prior_steps: list[str]) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=config.OPENROUTER_DRAFT_MODEL,
        max_tokens=700,
        temperature=0.85,
        messages=[
            {"role": "system", "content": _step_system_prompt(step_num)},
            {"role": "user", "content": _build_body_prompt(
                brand, anchor, worst_axis, step_num=step_num, prior_steps=prior_steps
            )},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def generate_body(brand: Brand, anchor: Prospect, worst_axis: str,
                  corpus: list[str], step_num: int = 1,
                  prior_steps: list[str] | None = None,
                  max_retries: int = 2) -> tuple[str, float]:
    """Generate one step's body, validating banned phrases, shopper-query count,
    word-count band, and 5-gram overlap vs the same-step corpus."""
    spec = STEP_SPECS[step_num]
    prior_steps = prior_steps or []
    best_body = ""
    best_overlap = 1.0
    for _ in range(max_retries + 1):
        body = _generate_body_once(brand, anchor, worst_axis, step_num, prior_steps)
        if not body:
            continue
        if _contains_banned(body, _body_banned()):
            continue
        if len(SHOPPER_QUERY_RE.findall(body)) < spec["needs_shopper_query"]:
            continue
        wc = _word_count(body)
        # band tolerance loaded from rules so it can be tuned without redeploy
        tol = _rules.word_count_tolerance()
        if wc < int(spec["min_words"] * (1 - tol)) or wc > int(spec["max_words"] * (1 + tol)):
            continue
        overlap = max_overlap(body, corpus)
        if overlap < best_overlap:
            best_body, best_overlap = body, overlap
        if overlap <= _rules.max_5gram_overlap():
            return body, overlap
    return best_body, best_overlap


# ---------------------------------------------------------------------------
# Subject per step
# ---------------------------------------------------------------------------

STEP_SUBJECT_HINTS = {
    1: "Curiosity hook on the worst Rufus axis. Concrete.",
    2: "Frame as a fix or a finding. Different angle than step 1.",
    3: "Frame as a competitor observation. Naming the category, not the rival.",
    4: "Three to six words. A question, ideally. Pattern-interrupt energy.",
    5: "Closing-the-loop tone. Soft. No urgency words.",
}


def generate_step_subject(brand: Brand, anchor: Prospect, worst_axis: str,
                          step_num: int, prior_subjects: list[str]) -> str:
    client = _get_client()
    hint = STEP_SUBJECT_HINTS[step_num]
    prior_block = ""
    if prior_subjects:
        prior_block = "\n\nPRIOR SUBJECTS IN THIS SEQUENCE (do not echo their wording):\n- " + "\n- ".join(prior_subjects)
    user_prompt = (
        f"Brand: {brand.brand_name}\n"
        f"Category: {anchor.category or brand.category or 'consumer product'}\n"
        f"ASIN: {anchor.asin}\n"
        f"Worst Rufus axis: {worst_axis}\n"
        f"Rufus summary: {anchor.rufus_summary or '(none)'}\n"
        f"Step {step_num} of 5 — angle: {hint}{prior_block}\n\n"
        f"Write 3 candidate subject lines for STEP {step_num}."
    )
    resp = client.chat.completions.create(
        model=config.OPENROUTER_DRAFT_MODEL,
        max_tokens=120,
        temperature=0.95,
        messages=[
            {"role": "system", "content": SUBJECT_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    candidates = [
        re.sub(r"^[\"'\-\*\d\.\)]+\s*", "", line).strip().strip('"').strip("'")
        for line in raw.splitlines() if line.strip()
    ]
    candidates = [c for c in candidates
                  if c and not _contains_banned(c, _subject_banned())
                  and c.lower() not in {p.lower() for p in prior_subjects}]
    if not candidates:
        return f"the {worst_axis} gap on {anchor.asin}"
    return random.choice(candidates)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Single-call sequence drafter — all 5 (subject, body) pairs in one JSON LLM call
# ---------------------------------------------------------------------------

SEQUENCE_SYSTEM_PROMPT = """You are an elite B2B cold-email copywriter ghost-writing a 5-step outbound sequence for Yahya, an Amazon listing-optimization consultant. Every recipient is the founder/owner of a small consumer-goods brand selling on Amazon. You have audited their worst-performing ASIN for how it surfaces in Amazon's Rufus AI shopping chat.

You write in the high-converting, direct, punchy, and clear copywriting style of Alex Hormozi.

You will draft ALL FIVE STEPS in this single response, returned as one JSON object.

==================================================================
THE ALEX HORMOZI COPYWRITING PRINCIPLES (Non-Negotiable)
==================================================================
- **Clarity Over Cleverness:** Never write a fancy or poetic sentence. Use simple, direct, one-syllable words where possible. Do not try to impress; try to explain.
- **Short Sentence As A Weapon:** Use extremely short sentences. Sentence fragments are highly encouraged. (e.g., "No badges. No attributes. Rufus sees nothing. Competitors win. Easily.")
- **Blunt Honesty:** Tell them the hard truth about their listing without softening or fluff. They are losing traffic and money. State the math. 
- **The "No-Brainer" Offer:** Frame their Personalized Rufus Visibility Audit Page (a custom diagnostic trace page of their own listing gaps) as a zero-cost, high-value gift with zero friction.
- **Peer-to-Peer Tone:** Sound like a peer operator who pulled up their listing 5 minutes ago and wrote them a direct note. No formal greetings, no "I wanted to's," no passive voice.

==================================================================
STEP INTENTS
==================================================================
Step 1 — teardown anchor: open with one concrete observation from this listing, then 3-4 dashed lines naming the gap → Rufus consequence. End with a curiosity-driven setup for their Personalized Rufus Visibility Audit Page (the private audit URL is appended after generation; write one natural sentence that references it without including a raw URL). 90-140 words, ≥2 shopper-query constructions.
Step 2 — tactical insight: day-3 follow-up. Do NOT recap step 1. ONE specific listing fix the founder could ship today, tied to the worst Rufus axis. Two short paragraphs. Soft nudge at end. 60-90 words, ≥1 shopper-query construction.
Step 3 — competitor proof: day-7 follow-up. Show what a typical competitor does on the worst axis that this brand doesn't. Frame as observation, not threat. Offer to send the side-by-side. 70-110 words, ≥1 shopper-query construction.
Step 4 — pattern interrupt: day-12 follow-up. THREE sentences max. One blunt question that earns a yes/no. No dashed lines. No CTA softener. 25-45 words, 0 shopper-query constructions.
Step 5 — break-up: day-18 close-the-loop. Acknowledge timing might be off, leave their personalized audit page link standing, do not ask for a reply. Warm, brief. 50-80 words, 0 shopper-query constructions.

==================================================================
CRAFT TACTICS — apply these actively to every step
==================================================================

CONSEQUENCE CHAIN: Every observation must chain to a real consequence.
  listing gap → Rufus can't extract the answer → shopper gets competitor cited → lost impression.
  Never stop at the observation. Readers skim past problems without stakes.

SPECIFICITY OVER ASSERTION: One concrete number or direct quote beats three vague observations.
  "4 of your 5 bullets open with 'Our product'" crushes "your bullets are product-focused."
  Use the actual values given — bullet count, image count, Q&A count, rating, char count.

SHORT SENTENCE AS A WEAPON: After 2–3 lines of setup, land a 4–8 word sentence. It stops the reader.
  Examples: "That's what Rufus sees." / "Competitors don't have this gap."
  Use it once per step — overuse kills the effect.

THE YOU RATIO: Every sentence must be about THEM — their listing, their shopper, their category.
  Sentences starting with "I" or "Yahya" total ≤ 1 per email. If it's not about them, cut it.

NO SETUP SENTENCES: Cut any sentence that announces what you're about to say.
  "I wanted to share an observation about your listing" → delete. Start with the observation itself.

DASHED LINES (Step 1 only) — each dash is a complete [gap] → [Rufus consequence] pair.
  No explanations inside the dash. No sub-bullets. 2–3 dashes max — more looks rushed.

STEP 4 IS A BINARY CLOSE: One precise observation + one yes/no question. No softeners.
  The question must be answerable with one word — not "does this resonate?" but a specific yes/no.

SUBJECT LINE SPECIFICITY: Name the axis or the exact gap — never the brand or the founder.
  "why rufus skips your magnesium" outperforms "your amazon listing" every time.
  Specificity signals homework done; vagueness signals mass send.

==================================================================
HARD RULES — apply to EVERY step
==================================================================

1. NO TWO STEPS may share opener phrasing or sentence shape across this sequence. The recipient will read all 5; each must read as freshly written.

2. FORBIDDEN OPENERS (or any paraphrase): "I noticed your...", "I came across your brand", "I hope this finds you", "I hope you're well", "I wanted to reach out", "I've been following...", "Congrats on...", "Just following up", "Quick question", "Quick note", "Hope you don't mind".

3. FORBIDDEN PHRASES anywhere in any body: revolutionize, leverage, synergy, unlock, transform, seamlessly, reach out, just checking in, excited to, happy to share, valuable insights, take your business to the next level, game-changer, move the needle, I'd love to, circle back, touch base, partner with you, at your earliest convenience, make sense, sounds good, low-hanging fruit, no-brainer, exciting opportunity.

4. NO greeting, NO sign-off, NO markdown, NO meta-language ("this email", "step 2", "follow-up"), NO P.S., NO closing hedge ("if this isn't relevant, no worries"). Apollo's template handles greetings and signature.

5. SHOPPER-QUERY CONSTRUCTION format when required:
   when a shopper asks Rufus "<plausible category-specific query>", <consequence>
   <consequence> = which competitor gets recommended, which question goes unanswered, or which attribute Rufus can't cite. Real shopper queries only ("best magnesium for sleep" — yes; "what is the best supplement for my health needs" — no).

6. GROUNDING: use ONLY data given in the user prompt. If numbers are given (bullet count, image count, Q&A count, char count, rating, review count), reference AT LEAST ONE by its actual value somewhere in the sequence. Quote a 4-6 word direct phrase from the listing title or bullets when natural.

7. AXIS DISCIPLINE: the "worst Rufus axis" is the spine of the entire 5-step sequence. Every step circles the same axis from a different angle.

8. SUBJECTS: 4-9 words. Lowercase fine. No emojis, brackets, or punctuation other than ? and ,. Forbidden: "quick note", "quick question", "checking in", "audit", the word "free", the brand name, the founder's name. Different angle per step.

9. DYNAMIC LOOM OVERRIDE: If the user prompt states a personalized Loom has been recorded, you MUST weave it into Step 1 or Step 4 as the primary Call to Action (CTA). In Step 1, instead of a soft audit teardown offer, use the Loom CTA. In Step 4, position the Loom as a direct yes/no hook (e.g. "Did you get the 90-second video breakdown I made of your magnesium listing's search gaps?"). When writing this, use the exact merge token {{loom_url}} in the body text (e.g. "I recorded a 90-second Loom showing your listing's Rufus visibility score here: {{loom_url}}"). Phrase the CTA naturally, sounding like a direct personal message.

==================================================================
OUTPUT — single JSON object, no markdown, no commentary
==================================================================
{
  "worst_axis": "<intent|attribute|conversational|qa|visual|competitive>",
  "steps": [
    {"step": 1, "subject": "<...>", "body": "<...>"},
    {"step": 2, "subject": "<...>", "body": "<...>"},
    {"step": 3, "subject": "<...>", "body": "<...>"},
    {"step": 4, "subject": "<...>", "body": "<...>"},
    {"step": 5, "subject": "<...>", "body": "<...>"}
  ]
}
Begin the JSON object directly. No preamble like "Here's the sequence:"."""

SEQUENCE_SYSTEM_PROMPT_BATCH = SEQUENCE_SYSTEM_PROMPT.replace(
    """==================================================================
OUTPUT — single JSON object, no markdown, no commentary
==================================================================
{
  "worst_axis": "<intent|attribute|conversational|qa|visual|competitive>",
  "steps": [
    {"step": 1, "subject": "<...>", "body": "<...>"},
    {"step": 2, "subject": "<...>", "body": "<...>"},
    {"step": 3, "subject": "<...>", "body": "<...>"},
    {"step": 4, "subject": "<...>", "body": "<...>"},
    {"step": 5, "subject": "<...>", "body": "<...>"}
  ]
}
Begin the JSON object directly. No preamble like "Here's the sequence:".""",
    """==================================================================
OUTPUT — JSON ARRAY (one object per brand, same order as brands in the user prompt)
==================================================================
[
  {"brand_key": "<key>", "worst_axis": "<intent|attribute|conversational|qa|visual|competitive>", "steps": [
    {"step": 1, "subject": "<...>", "body": "<...>"},
    {"step": 2, "subject": "<...>", "body": "<...>"},
    {"step": 3, "subject": "<...>", "body": "<...>"},
    {"step": 4, "subject": "<...>", "body": "<...>"},
    {"step": 5, "subject": "<...>", "body": "<...>"}
  ]},
  ...
]
Begin the JSON array directly. No preamble.""",
)


def _build_sequence_user_prompt(brand: Brand, anchor: Prospect, worst_axis: str,
                                corpus_by_step: dict[int, list[str]]) -> str:
    signals = brand.weakness_signals or anchor.weakness_signals or ""

    # Load competitor intel if available
    competitors = db.get_competitors(brand.brand_key)
    competitor_block = ""
    if competitors:
        competitor_block = "\n\nTOP COMPETITORS (ranked by search position for this keyword):\n"
        for i, c in enumerate(competitors[:3], 1):
            competitor_block += (
                f"\n{i}. {c.get('competitor_brand', 'Unknown')} — {c.get('title', '')[:80]}\n"
                f"   Bullets: {c.get('bullet_count', 0)} | Images: {c.get('image_count', 0)} | "
                f"Q&A: {c.get('qa_count', 0)} | A+: {'yes' if c.get('has_a_plus') else 'no'} | "
                f"Rating: {c.get('rating', '—')} ({c.get('review_count', 0)} reviews)\n"
                f"   Bullet text (truncated): {c.get('bullets', '')[:400]}\n"
            )

    rufus_block = ""
    if anchor.rufus_score is not None:
        rufus_block = (
            f"\nRufus Optimization Score: {anchor.rufus_score}/100 "
            f"(citation probability: {anchor.rufus_citation_probability or '?'})\n"
            f"  Intent Alignment:           {anchor.intent_alignment_score}/25\n"
            f"  Attribute Density:          {anchor.attribute_density_score}/25\n"
            f"  Conversational Readability: {anchor.conversational_readability_score}/25\n"
            f"  Q&A Coverage:               {anchor.qa_coverage_score}/25\n"
            f"Rufus Summary: {anchor.rufus_summary}"
        )
        if anchor.rufus_top_weaknesses:
            try:
                weaknesses = _json.loads(anchor.rufus_top_weaknesses)
                if weaknesses:
                    rufus_block += "\nRufus Top Weaknesses:"
                    for w in weaknesses:
                        rufus_block += f"\n  [{w.get('axis','?')}] {w.get('issue','')} → {w.get('fix','')}"
            except Exception:
                pass

    multi_asin_note = ""
    if brand.asin_count and brand.asin_count > 1:
        multi_asin_note = (
            f"\nNote: this brand has {brand.asin_count} weak listings; the ASIN "
            f"below is the worst one — use it as the case study."
        )

    # Opener collision is the only real uniqueness risk for step 1; steps 2-5 diverge by intent.
    # Send 3 short step-1 openers only — saves ~1,700 tokens vs the old 25-snippet full corpus.
    corpus_block = ""
    step1_snippets = corpus_by_step.get(1, [])[:3]
    if step1_snippets:
        corpus_block = "\n\nRECENT STEP-1 OPENERS (vary yours): " + " | ".join(s[:80] for s in step1_snippets)

    # For well-scored brands, Rufus summary + weaknesses already encode the key gaps.
    # Omit raw bullets to cut ~300 tokens; keep them only for unscored/low-scored brands.
    bullets_section = ""
    if not anchor.rufus_score or anchor.rufus_score < 50:
        raw = (anchor.post_body or "")[:800]
        if raw:
            bullets_section = f"\n\nBullets (raw):\n{raw}"

    landing_page_url = f"{config.PITCH_PAGE_BASE_URL}/p/{brand.brand_key}"

    loom_instruction = ""
    if getattr(brand, "loom_url", None):
        loom_instruction = (
            f"\n\nCRITICAL: A personalized Loom video has been recorded for this prospect at: {brand.loom_url}\n"
            "You MUST weave this Loom video in as the primary CTA in Step 1 or Step 4. Use the exact token {{loom_url}} "
            "to represent the URL in your generated body (e.g. \"I recorded a 90-second Loom showing your listing's Rufus visibility score here: {{loom_url}}\")."
        )

    return f"""Draft the full 5-step sequence to this Amazon brand founder. Worst Rufus axis: "{worst_axis}" — keep it the spine of all 5 steps.

Founder first name: {brand.contact_first_name or 'there'}
Brand: {brand.brand_name}
Category: {anchor.category or brand.category or 'consumer product'}
Anchor ASIN: {anchor.asin}{competitor_block}
Title ({len(anchor.post_title or '')} chars): {anchor.post_title}
Bullet count: {anchor.bullet_count}
Image count: {anchor.image_count}
Has A+ content: {anchor.has_a_plus}
Q&A count: {anchor.qa_count}
Rating: {anchor.listing_rating}
Review count: {anchor.listing_review_count}
Rule-based weakness signals: {signals}
{rufus_block}{multi_asin_note}{bullets_section}{corpus_block}{loom_instruction}

AUDIT LANDING PAGE LINK (appended to step 1 after generation — DO NOT include raw URL in body): {landing_page_url}

Return the JSON object now. All 5 steps. Length bands per step: s1 90-140w, s2 60-90w, s3 70-110w, s4 25-45w, s5 50-80w."""


def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return _json.loads(text)
    except _json.JSONDecodeError:
        repaired = _repair_json(text)
        try:
            return _json.loads(repaired)
        except _json.JSONDecodeError:
            logging.getLogger("acquisition_tool.email").warning("JSON repair failed", extra={"raw": raw[:200]})
            return {}


def _repair_json(text: str) -> str:
    """Close unclosed JSON string/array/object caused by LLM truncation."""
    # Count unclosed quotes inside string values (odd count = unterminated string)
    # Simple heuristic: close any open string, then close arrays/objects.
    open_brackets = []
    in_string = False
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"' and not in_string:
            in_string = True
        elif ch == '"' and in_string:
            in_string = False
        elif not in_string:
            if ch in "{[":
                open_brackets.append(ch)
            elif ch == "}" and open_brackets and open_brackets[-1] == "{":
                open_brackets.pop()
            elif ch == "]" and open_brackets and open_brackets[-1] == "[":
                open_brackets.pop()
    suffix = ""
    if in_string:
        suffix += '"'
    for ch in reversed(open_brackets):
        suffix += "}" if ch == "{" else "]"
    return text + suffix


def _validate_step(step_num: int, subject: str, body: str) -> tuple[bool, str]:
    spec = STEP_SPECS[step_num]
    if not subject or not body:
        return False, "empty"
    if _contains_banned(subject, _subject_banned()):
        return False, "banned_subject"
    if _contains_banned(body, _body_banned()):
        return False, "banned_body"
    if len(SHOPPER_QUERY_RE.findall(body)) < spec["needs_shopper_query"]:
        return False, "shopper_query"
    wc = _word_count(body)
    tol = _rules.word_count_tolerance()
    if wc < int(spec["min_words"] * (1 - tol)) or wc > int(spec["max_words"] * (1 + tol)):
        return False, f"word_count={wc}"
    return True, ""


def _draft_sequence_single_call(brand: Brand, anchor: Prospect, worst_axis: str,
                                corpus_by_step: dict[int, list[str]]) -> dict:
    """Synchronous single-call drafter. Returns parsed sequence dict."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=config.OPENROUTER_DRAFT_MODEL,
        max_tokens=2400,
        temperature=0.85,
        messages=[
            {"role": "system", "content": SEQUENCE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_sequence_user_prompt(brand, anchor, worst_axis, corpus_by_step)},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _extract_json(raw)


@resilience.async_retry_call(max_attempts=5, backoff_seconds=3.0, exceptions=(httpx.HTTPStatusError, httpx.RequestError, Exception))
async def _draft_sequence_single_call_async(
    brand: Brand, anchor: Prospect, worst_axis: str,
    corpus_by_step: dict[int, list[str]],
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore,
) -> dict:
    user_prompt = _build_sequence_user_prompt(brand, anchor, worst_axis, corpus_by_step)
    async with semaphore:
        resp = await client.post(
            OPENROUTER_CHAT_URL,
            headers=_openrouter_headers(),
            json={
                "model": config.OPENROUTER_DRAFT_MODEL,
                "max_tokens": 2400,
                "temperature": 0.85,
                "messages": [
                    {"role": "system", "content": SEQUENCE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
    raw = (data["choices"][0]["message"]["content"] or "").strip()
    return _extract_json(raw)


def _finalize_sequence(brand: Brand, anchor: Prospect, parsed: dict, save: bool) -> dict:
    """Validate per-step output, run uniqueness check, persist. Returns the
    legacy-shape result {worst_axis, steps: {n: {subject, body, overlap}}}.
    Falls back to the per-step legacy generator only for steps that fail validation."""
    worst_axis = (parsed.get("worst_axis") or "intent").strip().lower()
    if worst_axis not in {"intent", "attribute", "conversational", "qa", "visual", "competitive"}:
        worst_axis = _worst_axis(anchor)

    out = {"worst_axis": worst_axis, "steps": {}}
    prior_bodies: list[str] = []

    by_step = {s.get("step"): s for s in parsed.get("steps", []) if s.get("step")}

    landing_page_url = f"{config.PITCH_PAGE_BASE_URL}/p/{brand.brand_key}"

    for step_num in (1, 2, 3, 4, 5):
        s = by_step.get(step_num) or {}
        subject = (s.get("subject") or "").strip().strip('"').strip("'")
        body = (s.get("body") or "").strip()

        ok, reason = _validate_step(step_num, subject, body)
        if not ok:
            # Per-step regen fallback — preserves the prior multi-call uniqueness guards
            corpus = db.get_recent_brand_bodies(limit=50, step_num=step_num)
            try:
                new_subject = generate_step_subject(
                    brand, anchor, worst_axis, step_num,
                    [out["steps"][n]["subject"] for n in out["steps"]],
                )
                new_body, _ = generate_body(
                    brand, anchor, worst_axis, corpus,
                    step_num=step_num, prior_steps=prior_bodies,
                )
                if new_subject and new_body:
                    subject, body = new_subject, new_body
            except Exception as exc:
                logging.getLogger("acquisition_tool.email").warning(
                    "Per-step fallback failed for %s step %s: %s", brand.brand_key, step_num, exc
                )

        # Append landing page URL to step 1 body after all generation/fallback
        if step_num == 1 and body:
            if landing_page_url not in body:
                body = body.rstrip() + f"\n\n{landing_page_url}"

        # Replace Loom token if present in subject or body
        if getattr(brand, "loom_url", None):
            if subject:
                subject = subject.replace("{{loom_url}}", brand.loom_url)
            if body:
                body = body.replace("{{loom_url}}", brand.loom_url)

        corpus = db.get_recent_brand_bodies(limit=50, step_num=step_num)
        overlap = max_overlap(body, corpus)
        if overlap > _rules.max_5gram_overlap():
            logging.getLogger("acquisition_tool.email").warning(
                "Overlap too high for %s step %s: %.2f", brand.brand_key, step_num, overlap
            )
            body = ""
        out["steps"][step_num] = {"subject": subject, "body": body, "overlap": overlap}
        prior_bodies.append(body)

        if save:
            db.save_brand_step_email(brand.brand_key, step_num, subject, body, overlap)

    if save and 1 in out["steps"]:
        s1 = out["steps"][1]
        db.save_brand_custom_copy(
            brand_key=brand.brand_key,
            subject=s1["subject"],
            body=s1["body"],
            worst_axis=worst_axis,
            teardown=s1["body"],
        )
        # Track that landing page CTA was embedded (reusing calculator_url field for database compatibility)
        db.set_brand_calculator_url(brand.brand_key, landing_page_url)
    return out


def draft_sequence(brand: Brand, anchor: Prospect, save: bool = True,
                   steps: tuple[int, ...] = (1, 2, 3, 4, 5)) -> dict:
    """Generate all 5 steps for one brand in a SINGLE LLM call. Falls back to
    per-step regeneration only if individual steps fail validation."""
    worst_axis = _worst_axis(anchor)
    corpus_by_step = {1: db.get_recent_brand_bodies(limit=10, step_num=1)}
    try:
        parsed = _draft_sequence_single_call(brand, anchor, worst_axis, corpus_by_step)
    except Exception as e:
        # Catastrophic LLM/JSON failure — fall through to legacy per-step path
        logging.getLogger("acquisition_tool.email").warning("single-call failure — falling back to per-step", extra={"brand_key": brand.brand_key, "error": str(e)})
        return _draft_sequence_legacy(brand, anchor, worst_axis, save=save, steps=steps)
    return _finalize_sequence(brand, anchor, parsed, save=save)


async def draft_sequence_async(brand: Brand, anchor: Prospect,
                               client: httpx.AsyncClient,
                               semaphore: asyncio.Semaphore,
                               save: bool = True) -> dict:
    """Async equivalent of draft_sequence — used by the streaming pipeline."""
    worst_axis = _worst_axis(anchor)
    corpus_by_step = {1: db.get_recent_brand_bodies(limit=10, step_num=1)}
    try:
        parsed = await _draft_sequence_single_call_async(
            brand, anchor, worst_axis, corpus_by_step, client, semaphore,
        )
    except Exception as e:
        logging.getLogger("acquisition_tool.email").warning("async single-call failure — falling back sync legacy", extra={"brand_key": brand.brand_key, "error": str(e)})
        return await asyncio.to_thread(
            _draft_sequence_legacy, brand, anchor, worst_axis, save, (1, 2, 3, 4, 5),
        )
    return await asyncio.to_thread(_finalize_sequence, brand, anchor, parsed, save)


def _extract_json_list(raw: str) -> list:
    """Parse a JSON array response from a mini-batch call."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    parsed = _json.loads(text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                return v
    raise ValueError(f"Expected JSON array from batch, got {type(parsed)}")


def _build_mini_batch_prompt(
    batch: list[tuple[Brand, Prospect, str, dict[int, list[str]]]]
) -> str:
    """Combine multiple per-brand prompts into one user message for a mini-batch call."""
    n = len(batch)
    parts = [
        f"Draft sequences for {n} brand{'s' if n != 1 else ''} below. "
        f"Return a JSON array with {n} object{'s' if n != 1 else ''}, one per brand, in the same order.\n"
    ]
    for i, (brand, anchor, worst_axis, corpus_by_step) in enumerate(batch):
        header = f"\n=== BRAND {i + 1}/{n}: {brand.brand_key} ==="
        body = _build_sequence_user_prompt(brand, anchor, worst_axis, corpus_by_step)
        parts.append(header + "\n" + body)
    return "\n".join(parts)


async def draft_batch_async(
    batch: list[tuple[Brand, Prospect]],
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    save: bool = True,
) -> dict[str, dict]:
    """Draft all 5 steps for a mini-batch of brands in one API call.

    Returns dict mapping brand_key → sequence result (same shape as draft_sequence_async).
    Falls back to individual per-brand calls if the batch request fails.
    """
    prepared = [
        (brand, anchor, _worst_axis(anchor), {1: db.get_recent_brand_bodies(limit=10, step_num=1)})
        for brand, anchor in batch
    ]
    user_prompt = _build_mini_batch_prompt(prepared)
    max_output = min(2400 * len(batch), 8000)

    try:
        async with semaphore:
            resp = await client.post(
                OPENROUTER_CHAT_URL,
                headers=_openrouter_headers(),
                json={
                    "model": config.OPENROUTER_DRAFT_MODEL,
                    "max_tokens": max_output,
                    "temperature": 0.85,
                    "messages": [
                        {"role": "system", "content": SEQUENCE_SYSTEM_PROMPT_BATCH},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        raw = (data["choices"][0]["message"]["content"] or "").strip()
        results = _extract_json_list(raw)
    except Exception as exc:
        keys = [b.brand_key for b, _ in batch]
        logging.getLogger("acquisition_tool.email").warning("batch failure — falling back to per-brand", extra={"brand_keys": keys, "error": str(exc)})
        out: dict[str, dict] = {}
        for brand, anchor in batch:
            worst_axis = _worst_axis(anchor)
            corpus_by_step = {1: db.get_recent_brand_bodies(limit=10, step_num=1)}
            try:
                parsed = await _draft_sequence_single_call_async(
                    brand, anchor, worst_axis, corpus_by_step, client, semaphore
                )
                out[brand.brand_key] = await asyncio.to_thread(
                    _finalize_sequence, brand, anchor, parsed, save
                )
            except Exception as exc2:
                logging.getLogger("acquisition_tool.email").warning("fallback failed for brand", extra={"brand_key": brand.brand_key, "error": str(exc2)})
        return out

    brand_map = {brand.brand_key: (brand, anchor) for brand, anchor in batch}
    out = {}
    for item in results:
        bk = item.get("brand_key", "")
        if bk not in brand_map:
            continue
        brand, anchor = brand_map[bk]
        out[bk] = await asyncio.to_thread(_finalize_sequence, brand, anchor, item, save)
    return out


def _draft_sequence_legacy(brand: Brand, anchor: Prospect, worst_axis: str | None = None,
                           save: bool = True,
                           steps: tuple[int, ...] = (1, 2, 3, 4, 5)) -> dict:
    """Original 10-call drafter. Kept as a safety fallback when the single-call
    JSON path fails (rare). Do not call directly — use draft_sequence."""
    worst_axis = worst_axis or _worst_axis(anchor)
    out = {"worst_axis": worst_axis, "steps": {}}
    prior_bodies: list[str] = []
    prior_subjects: list[str] = []

    landing_page_url = f"{config.PITCH_PAGE_BASE_URL}/p/{brand.brand_key}"

    for step_num in steps:
        corpus = db.get_recent_brand_bodies(limit=50, step_num=step_num)
        subject = generate_step_subject(brand, anchor, worst_axis, step_num, prior_subjects)
        body, overlap = generate_body(
            brand, anchor, worst_axis, corpus,
            step_num=step_num, prior_steps=prior_bodies,
        )
        # Append landing page URL to step 1 body
        if step_num == 1 and body and landing_page_url not in body:
            body = body.rstrip() + f"\n\n{landing_page_url}"

        # Replace Loom token if present in subject or body
        if getattr(brand, "loom_url", None):
            if subject:
                subject = subject.replace("{{loom_url}}", brand.loom_url)
            if body:
                body = body.replace("{{loom_url}}", brand.loom_url)

        if overlap > _rules.max_5gram_overlap():
            logging.getLogger("acquisition_tool.email").warning(
                "Legacy fallback overlap too high for %s step %s: %.2f", brand.brand_key, step_num, overlap
            )
            body = ""

        out["steps"][step_num] = {"subject": subject, "body": body, "overlap": overlap}
        prior_bodies.append(body)
        prior_subjects.append(subject)
        if save:
            db.save_brand_step_email(brand.brand_key, step_num, subject, body, overlap)

    if save and 1 in out["steps"]:
        s1 = out["steps"][1]
        db.save_brand_custom_copy(
            brand_key=brand.brand_key,
            subject=s1["subject"],
            body=s1["body"],
            worst_axis=worst_axis,
            teardown=s1["body"],
        )
        db.set_brand_calculator_url(brand.brand_key, landing_page_url)
    return out


def draft_teardown(brand: Brand, anchor: Prospect, save: bool = True) -> dict:
    """Back-compat wrapper — generates the full 5-step sequence and returns
    step 1 in the legacy shape."""
    seq = draft_sequence(brand, anchor, save=save)
    s1 = seq["steps"][1]
    return {
        "subject": s1["subject"],
        "body": s1["body"],
        "worst_axis": seq["worst_axis"],
        "overlap": s1["overlap"],
    }
