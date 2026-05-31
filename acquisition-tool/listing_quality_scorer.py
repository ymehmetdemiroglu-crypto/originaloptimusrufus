"""Enhanced listing-quality scorer — weighted, predictive, category-aware, and linguistically sophisticated.

Replaces the crude binary weakness scorer with a multi-factor model that
better predicts actual Rufus vulnerability. Scores 0–100 where higher =
more severe gaps = higher need for Rufus optimization.

Key improvements over legacy weakness_scorer:
- Severity-weighted penalties (title with 20 chars hurts more than 75 chars)
- Regex-based attribute detection per category (no LLM cost)
- Bullet-quality analysis (length, caps spam, question-answering structure)
- Competitive context (BSR tier, review velocity if available)
- Better correlation with downstream Rufus LLM scores
- Computational Linguistics Audits:
  * Flesch-Kincaid Readability Ease Index
  * Lexical Diversity (Type-Token Ratio - TTR)
  * COSMO Common-Sense Relational Linkage Density
"""
import re
import math
from typing import Optional

import config
import db
from models import Prospect

# Optional backend integration for semantic scoring
if config.USE_BACKEND_SCORING:
    import backend_client as _backend
else:
    _backend = None  # type: ignore


# ---------------------------------------------------------------------------
# Category-specific attribute dictionaries
# ---------------------------------------------------------------------------

CATEGORY_ATTRIBUTES = {
    "supplement": {
        "quantities": [r"\b\d+\s*(mg|mcg|iu|g|oz|ml|cc)\b"],
        "count": [r"\b\d+\s*(capsules?|softgels?|tablets?|gummies?|servings?|count|packs?)\b"],
        "certifications": [r"\b(non-gmo|nsf|usp|gmp|kosher|halal|informed sport|third.party tested|lab tested)\b"],
        "dietary": [r"\b(vegan|vegetarian|gluten.free|dairy.free|soy.free|allergen.free|sugar.free|keto|paleo)\b"],
        "form": [r"\b(softgel|capsule|gummy|powder|liquid|tablet|chewable|enteric coated)\b"],
        "transparency": [r"\b\d+\s*(mg|mcg|iu|g)\b.*\bper\b"],
    },
    "skincare": {
        "quantities": [r"\b\d+\s*(oz|fl oz|ml|g|%)\b"],
        "ingredients": [r"\b(vitamin c|retinol|niacinamide|hyaluronic acid|salicylic acid|glycolic|peptide|ceramide|collagen)\b"],
        "certifications": [r"\b(dermatologist tested|clinically tested|cruelty.free|leaping bunny|ecocert|usda organic)\b"],
        "skin_type": [r"\b(sensitive|oily|dry|combination|acne.prone|all skin types)\b"],
        "free_from": [r"\b(paraben.free|fragrance.free|sulfate.free|phthalate.free|dye.free)\b"],
        "usage": [r"\b(am|pm|morning|night|daily|twice daily|weekly)\b"],
    },
    "pet": {
        "ingredients": [r"\b(chicken|beef|salmon|turkey|duck|lamb|whitefish)\b"],
        "health_goal": [r"\b(joint|hip|calming|anxiety|dental|skin|coat|digestive|immune|allergy)\b"],
        "free_from": [r"\b(grain.free|corn.free|soy.free|wheat.free|filler.free)\b"],
        "form": [r"\b(soft chew|tablet|liquid|powder|treat|capsule)\b"],
        "certifications": [r"\b(vet recommended|nas|c|fda|made in usa|organic)\b"],
        "pet_type": [r"\b(dog|cat|puppy|kitten|small breed|large breed|senior)\b"],
    },
    "kitchen": {
        "material": [r"\b(stainless steel|silicone|bpa.free|cast iron|ceramic|glass|bamboo)\b"],
        "care": [r"\b(dishwasher safe|hand wash|oven safe|microwave safe|freezer safe)\b"],
        "dimensions": [r"\b(\d+\.?\d*\s*(inch|in|cm|mm|ft|quart|qt|cup|gallon)\b|\d+\s*x\s*\d+)"],
        "features": [r"\b(non.stick|heat resistant|ergonomic|non.slip|adjustable|collapsible)\b"],
        "warranty": [r"\b(lifetime warranty|\d+.year warranty|money.back|satisfaction guarantee)\b"],
    },
    "fitness": {
        "material": [r"\b(latex.free|eco.friendly|non.toxic|foam|rubber|fabric)\b"],
        "specs": [r"\b(\d+\s*(lb|lbs|kg|pounds)|\d+\s*(inch|ft|cm)\b|\d+\s*x\s*\d+)"],
        "features": [r"\b(adjustable|portable|non.slip|waterproof|breathable|lightweight)\b"],
        "use_case": [r"\b(yoga|pilates|strength training|rehab|physical therapy|home gym)\b"],
    },
    "home_office": {
        "material": [r"\b(aluminum|steel|bamboo|abs|plastic|wood)\b"],
        "features": [r"\b(adjustable|ergonomic|non.slip|cable management|space.saving|foldable)\b"],
        "dimensions": [r"\b(\d+\.?\d*\s*(inch|in|cm|mm)\b|\d+\s*x\s*\d+)"],
        "compatibility": [r"\b(universal|fits\s+\d+.\d+\s*inch|macbook|laptop|monitor|ipad)\b"],
    },
    "baby": {
        "safety": [r"\b(bpa.free|phthalate.free|lead.free|fda approved|cpsc|cpsia)\b"],
        "age": [r"\b(\d+.\d+\s*months?|newborn|infant|toddler|0.\d+\s*months?)\b"],
        "material": [r"\b(organic cotton|bamboo|silicone|hypoallergenic|food.grade)\b"],
        "care": [r"\b(machine washable|dishwasher safe|easy clean|wipeable)\b"],
    },
    "automotive": {
        "fitment": [r"\b(universal|fits\s+\d+.|compatible with)\b"],
        "material": [r"\b(abs|pc|aluminum|steel|rubber|silicone|leather)\b"],
        "features": [r"\b(easy install|tool.free|adjustable|360.\s*degree|hd|night vision)\b"],
        "warranty": [r"\b(lifetime warranty|\d+.year warranty|money.back)\b"],
    },
}

FALLBACK_CATEGORY = "general"

GENERAL_ATTRIBUTES = {
    "quantities": [r"\b\d+\s*(mg|mcg|iu|g|oz|ml|fl oz|lbs?|kg|cm|inch|in|%)\b"],
    "count": [r"\b\d+\s*(count|pack|pieces?|units?|servings?|capsules?|tablets?)\b"],
    "certifications": [r"\b(fda|ce|ul|nsf|usp|gmp|iso|organic|non.gmo|certified)\b"],
    "origin": [r"\b(made in usa|made in china|made in japan|imported|domestic)\b"],
    "warranty": [r"\b(warranty|guarantee|return policy|money back)\b"],
}


def _detect_category(text: str, category_hint: Optional[str] = None) -> str:
    """Map listing text + category hint to an attribute family."""
    text_lower = (text or "").lower()
    hint = (category_hint or "").lower()

    combined = f"{hint} {text_lower}"
    checks = [
        ("supplement", ["supplement", "vitamin", "capsule", "softgel", "powder", "mg ", "iu ", "protein", "prebiotic", "probiotic"]),
        ("skincare", ["serum", "cream", "moisturizer", "cleanser", "toner", "spf", "retinol", "niacinamide", "hyaluronic"]),
        ("pet", ["dog", "cat", "pet ", "puppy", "kitten", "canine", "feline", "treats", "chew"]),
        ("kitchen", ["kitchen", "cookware", "utensil", "appliance", "pan", "pot", "knife", "blender", "skillet"]),
        ("fitness", ["fitness", "yoga", "gym", "exercise", "workout", "resistance", "foam roller", "weights"]),
        ("home_office", ["desk", "office", "monitor", "laptop", "cable", "ergonomic", "stand", "organizer"]),
        ("baby", ["baby", "toddler", "infant", "nursery", "diaper", "stroller", "bottle", "pacifier"]),
        ("automotive", ["car ", "auto ", "vehicle", "dash cam", "seat cover", "organizer", "motorcycle"]),
    ]
    for cat, keywords in checks:
        if any(kw in combined for kw in keywords):
            return cat
    return FALLBACK_CATEGORY


def _get_attribute_family(category: str) -> dict:
    return CATEGORY_ATTRIBUTES.get(category, GENERAL_ATTRIBUTES)


def _count_attribute_types(text: str, family: dict) -> tuple[int, list[str]]:
    """Return (number of attribute types found, list of which ones)."""
    text_lower = (text or "").lower()
    found = []
    for attr_type, patterns in family.items():
        matched = False
        for pat in patterns:
            if re.search(pat, text_lower):
                matched = True
                break
        if matched:
            found.append(attr_type)
    return len(found), found


# ---------------------------------------------------------------------------
# Computational Linguistics (FK Readability, TTR, COSMO Prepositions)
# ---------------------------------------------------------------------------

def _count_syllables_word(word: str) -> int:
    """Simple phonetic syllable counting heuristic for English."""
    w = word.lower().strip(".:;,!?\"'()[]")
    if not w:
        return 0
    vowels = "aeiouy"
    count = 0
    if w[0] in vowels:
        count += 1
    for index in range(1, len(w)):
        if w[index] in vowels and w[index - 1] not in vowels:
            count += 1
    if w.endswith("e"):
        count -= 1
    if w.endswith("le") and len(w) > 2 and w[-3] not in vowels:
        count += 1
    if count == 0:
        count = 1
    return count


def _calculate_flesch_kincaid(text: str) -> float:
    """Calculates Flesch Reading Ease Score. Range: ~0 (hard) to ~100 (easy)."""
    clean_text = re.sub(r"[^\w\s\.\!\?]", "", text)
    sentences = [s.strip() for s in re.split(r"[\.\!\?]", clean_text) if s.strip()]
    words = [w.strip() for w in clean_text.split() if w.strip()]
    
    total_sentences = max(1, len(sentences))
    total_words = max(1, len(words))
    total_syllables = sum(_count_syllables_word(w) for w in words)

    asl = total_words / total_sentences
    asw = total_syllables / total_words

    # Standard Flesch Reading Ease Formula
    score = 206.835 - (1.015 * asl) - (84.6 * asw)
    return max(0.0, min(100.0, score))


def _calculate_fk_grade_level(text: str) -> float:
    """Calculates Flesch-Kincaid Grade Level.
    Formula: 0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59
    """
    clean_text = re.sub(r"[^\w\s\.\!\?]", "", text)
    sentences = [s.strip() for s in re.split(r"[\.\!\?]", clean_text) if s.strip()]
    words = [w.strip() for w in clean_text.split() if w.strip()]
    
    total_sentences = max(1, len(sentences))
    total_words = max(1, len(words))
    total_syllables = sum(_count_syllables_word(w) for w in words)
    
    asl = total_words / total_sentences
    asw = total_syllables / total_words
    
    score = 0.39 * asl + 11.8 * asw - 15.59
    return max(0.0, min(20.0, score))


def _calculate_gunning_fog(text: str) -> float:
    """Calculates Gunning Fog Index.
    Formula: 0.4 * ((total_words / total_sentences) + 100 * (complex_words / total_words))
    where complex words have >= 3 syllables.
    """
    clean_text = re.sub(r"[^\w\s\.\!\?]", "", text)
    sentences = [s.strip() for s in re.split(r"[\.\!\?]", clean_text) if s.strip()]
    words = [w.strip() for w in clean_text.split() if w.strip()]
    
    total_sentences = max(1, len(sentences))
    total_words = max(1, len(words))
    
    complex_words = sum(1 for w in words if _count_syllables_word(w) >= 3)
    
    asl = total_words / total_sentences
    pct_complex = (complex_words / total_words) * 100
    
    score = 0.4 * (asl + pct_complex)
    return max(0.0, min(25.0, score))


def _calculate_lexical_diversity(text: str) -> float:
    """Calculates Type-Token Ratio (TTR) as a measure of lexical density vs keyword stuffing."""
    words = [w.lower().strip(".:;,!?\"'()[]") for w in text.split() if w.strip()]
    if not words:
        return 1.0
    unique_words = set(words)
    return len(unique_words) / len(words)


def _stem_word(word: str) -> str:
    """A simplified deterministic Porter-like stemmer for e-commerce suffixes."""
    w = word.lower().strip(".:;,!?\"'()[]")
    if len(w) <= 3:
        return w
    # Strip common plural/tense endings
    if w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("ies"):
        w = w[:-3] + "y"
    elif w.endswith("ss"):
        pass
    elif w.endswith("s") and not w.endswith("us") and not w.endswith("is") and not w.endswith("as"):
        w = w[:-1]
    
    if w.endswith("eed"):
        if w.endswith("eet"):
            pass
        else:
            w = w[:-1]
    elif w.endswith("ing"):
        w = w[:-3]
        if w.endswith("at") or w.endswith("bl") or w.endswith("iz"):
            w += "e"
    elif w.endswith("ed"):
        w = w[:-2]
        if w.endswith("at") or w.endswith("bl") or w.endswith("iz"):
            w += "e"
    elif w.endswith("ly"):
        w = w[:-2]
    return w


def _calculate_stemmed_ttr(text: str) -> float:
    """Calculates Type-Token Ratio after simplified stemming to avoid duplicates."""
    words = [w.lower().strip(".:;,!?\"'()[]") for w in text.split() if w.strip()]
    if not words:
        return 1.0
    stemmed_words = [_stem_word(w) for w in words]
    unique_stems = set(stemmed_words)
    return len(unique_stems) / len(words)


def _detect_keyword_stuffing(text: str) -> tuple[float, list[str]]:
    """Detects repeated exact bigrams or trigrams (e.g. repeated 3+ times).
    Returns (stuffing_score, [stuffed_phrases]).
    """
    words = [w.lower().strip(".:;,!?\"'()[]") for w in text.split() if w.strip()]
    if len(words) < 4:
        return 0.0, []
        
    bigrams = []
    for i in range(len(words) - 1):
        bigrams.append((words[i], words[i+1]))
        
    trigrams = []
    for i in range(len(words) - 2):
        trigrams.append((words[i], words[i+1], words[i+2]))
        
    bigram_counts = {}
    for bg in bigrams:
        if bg[0] in ("in", "for", "with", "of", "to", "on", "and", "the", "a", "is", "it") or bg[1] in ("in", "for", "with", "of", "to", "on", "and", "the", "a", "is", "it"):
            continue
        bigram_counts[bg] = bigram_counts.get(bg, 0) + 1
        
    trigram_counts = {}
    for tg in trigrams:
        stopwords = ("in", "for", "with", "of", "to", "on", "and", "the", "a", "is", "it", "this", "that", "you")
        if all(w in stopwords for w in tg):
            continue
        trigram_counts[tg] = trigram_counts.get(tg, 0) + 1
        
    stuffed_phrases = []
    max_count = 0
    
    for tg, count in trigram_counts.items():
        if count >= 3:
            phrase = " ".join(tg)
            stuffed_phrases.append(f"trigram:'{phrase}' (x{count})")
            max_count = max(max_count, count)
            
    for bg, count in bigram_counts.items():
        if count >= 4:
            phrase = " ".join(bg)
            if not any(phrase in sp for sp in stuffed_phrases):
                stuffed_phrases.append(f"bigram:'{phrase}' (x{count})")
                max_count = max(max_count, count)
                
    if max_count >= 5:
        return 8.0, stuffed_phrases
    elif max_count >= 3:
        return 4.0, stuffed_phrases
    return 0.0, stuffed_phrases


def _detect_cosmo_relations(text: str) -> tuple[int, float, list[str], dict[str, list[str]]]:
    """Scans for ontological links (User, Occasion, Benefit, Complement, Substitute).
    Returns (num_categories_found, relation_density, list[active_signals], matches_dict).
    """
    t_lower = text.lower()
    
    user_patterns = [
        r"(\b(?:designed|safe|perfect|ideal|great|made|suitable|recommended)\s+for\s+(?:\w+\s+){0,2}(?:kids|toddlers|babies|men|women|seniors|adults|dogs|cats|pets|athletes|runners|beginners|families|sensitive\s+skin|dry\s+skin|oily\s+skin)\b)",
        r"(\b(?:dog|cat|parent|toddler|baby|family)\s+(?:friendly|approved)\b)",
        r"(\bfor\s+(?:all\s+skin\s+types|dry\s+skin|sensitive\s+skin)\b)"
    ]
    
    occasion_patterns = [
        r"(\b(?:use|wear|take|apply)\s+(?:during|before|after|at|in|on)\s+(?:\w+\s+){0,2}(?:workouts?|exercises?|sleep|bedtime|travel|flights?|daily|morning|night|evening|summer|winter|camping|hiking|work|running)\b)",
        r"(\b(?:during|before|after|at|in|on)\s+(?:\w+\s+){0,2}(?:workouts?|exercises?|sleep|bedtime|travel|flights?|daily|morning|night|evening|summer|winter|camping|hiking|work|running)\b)",
        r"(\b(?:perfect|ideal|great|suitable)\s+for\s+(?:\w+\s+){0,2}(?:travel|bedtime|morning\s+routines?|daily\s+use|outdoor\s+activities|gifts?|christmas|holidays?|parties|traveling)\b)"
    ]
    
    benefit_patterns = [
        r"(\b(?:promotes?|supports?|helps?|boosts?|enhances?|relieves?|improves?|reduces?|prevents?|soothes?|restores?)\s+(?:\w+\s+){0,3}(?:sleep|digestion|immune|energy|focus|skin|hair|joints?|pain|anxiety|stress|hydration|strength|growth|gut\s+health)\b)",
        r"(\b(?:helps?\s+with|provides?\s+relief\s+from|good\s+for)\s+(?:\w+\s+){0,2}(?:pain|anxiety|stress|insomnia|dryness|bloating|cramps|fatigue)\b)",
        r"(\b(?:clinically\s+proven\s+to|designed\s+to)\s+(?:\w+\s+){0,2}(?:reduce|boost|promote|support|enhance|relieve)\b)"
    ]
    
    complement_patterns = [
        r"(\b(?:compatible|works?|use)\s+with\s+(?:\w+\s+){0,2}(?:iphone|ipad|android|alexa|google\s+home|standard\s+cup\s+holders?|any\s+charger|most\s+laptops?|all\s+strollers?|vacuum\s+sealers?|shaker\s+cups?|water\s+bottles?)\b)",
        r"(\b(?:fits|designed\s+to\s+fit)\s+(?:\w+\s+){0,2}(?:standard|most|iphone|laptops?|car\s+seats?|strollers?)\b)",
        r"(\bperfect\s+companion\s+for\b)"
    ]
    
    substitute_patterns = [
        r"(\b(?:alternative|substitute)\s+to\s+(?:\w+\s+){0,2}(?:sugar|coffee|plastic|paper\s+towels|traditional|standard|tablets?|pills?|capsules?)\b)",
        r"(\b(?:replaces?|replace)\s+(?:\w+\s+){0,2}(?:plastic|paper\s+towels|sugar|chemical|disposable|tablets?|pills?|capsules?)\b)",
        r"(\binstead\s+of\s+(?:\w+\s+){0,2}(?:sugar|coffee|plastic|paper|chemicals|tablets?|pills?|capsules?)\b)",
        r"(\b(?:better\s+than|upgrade\s+from)\s+(?:\w+\s+){0,2}(?:traditional|disposable|plastic)\b)"
    ]
    
    found_matches = {
        "user": [],
        "occasion": [],
        "benefit": [],
        "complement": [],
        "substitute": []
    }
    
    for pat in user_patterns:
        m = re.findall(pat, t_lower)
        if m:
            found_matches["user"].extend(m)
            
    for pat in occasion_patterns:
        m = re.findall(pat, t_lower)
        if m:
            found_matches["occasion"].extend(m)
            
    for pat in benefit_patterns:
        m = re.findall(pat, t_lower)
        if m:
            found_matches["benefit"].extend(m)
            
    for pat in complement_patterns:
        m = re.findall(pat, t_lower)
        if m:
            found_matches["complement"].extend(m)
            
    for pat in substitute_patterns:
        m = re.findall(pat, t_lower)
        if m:
            found_matches["substitute"].extend(m)
            
    for cat in found_matches:
        found_matches[cat] = [str(x).strip() for x in found_matches[cat] if x]
        
    categories_filled = sum(1 for cat in found_matches if len(found_matches[cat]) > 0)
    
    words = text.split()
    total_words = max(1, len(words))
    total_matches = sum(len(found_matches[cat]) for cat in found_matches)
    density = (total_matches / total_words) * 100
    
    signals = []
    if categories_filled <= 1:
        signals.append("COSMO_LOW_RELATION_VARIETY")
    elif categories_filled >= 4:
        signals.append("COSMO_EXCELLENT_RELATION_VARIETY")
        
    if density < 1.0:
        signals.append("COSMO_SPARSE_RELATION_DENSITY")
    elif density >= 3.0:
        signals.append("COSMO_HIGH_RELATION_DENSITY")
        
    return categories_filled, density, signals, found_matches


def _calculate_cosmo_relation_density(text: str) -> float:
    """Calculates count of specific relational prepositional links (for, with, in, on, during) per 100 words."""
    words = text.split()
    total_words = max(1, len(words))
    pattern = r"\b(for|with|in|on|during|by|at|under|above|to|capsule|coated|mg|mcg|certified|tested)\b"
    matches = re.findall(pattern, text.lower())
    return (len(matches) / total_words) * 100


# ---------------------------------------------------------------------------
# Sub-scorers (each returns 0–100, higher = worse gap)
# ---------------------------------------------------------------------------

def _score_title(title: Optional[str]) -> tuple[int, list[str]]:
    """Score title quality for Rufus extractability.

    Returns (score 0-20, [signal tags]).
    """
    if not title:
        return 20, ["TITLE_MISSING"]

    t = title.strip()
    length = len(t)
    signals = []
    score = 0

    # Length penalty — non-linear
    if length < 40:
        score += 12
        signals.append("TITLE_VERY_THIN")
    elif length < 60:
        score += 8
        signals.append("TITLE_THIN")
    elif length < 80:
        score += 4
        signals.append("TITLE_SHORT")
    elif length > 200:
        score += 3
        signals.append("TITLE_STUFFED")

    # Structure signals
    words = t.lower().split()
    if len(words) >= 2:
        first_two = " ".join(words[:2])
        if not re.search(r"\b(for|with|without|plus|\d)\b", first_two):
            score += 2
            signals.append("TITLE_BRAND_HEAVY")

    # Missing measurable attributes in title
    has_measurement = bool(re.search(r"\b\d+\s*(mg|mcg|iu|g|oz|ml|fl oz|count|pack|%|inch|cm|lbs?|kg)\b", t.lower()))
    if not has_measurement:
        score += 4
        signals.append("TITLE_NO_MEASUREMENT")

    # ALL CAPS spam in title
    caps_words = re.findall(r"\b[A-Z]{3,}\b", t)
    if len(caps_words) >= 2:
        score += 3
        signals.append("TITLE_CAPS_SPAM")

    return min(20, score), list(dict.fromkeys(signals))


def _score_bullets(bullets_text: Optional[str], bullet_count: Optional[int]) -> tuple[int, list[str]]:
    """Score bullet quality for Rufus extractability.

    Returns (score 0-25, [signal tags]).
    """
    signals = []
    score = 0
    btext = (bullets_text or "").strip()
    bcount = bullet_count or 0

    # Count penalty — severe under 3, moderate 3-4
    if bcount == 0:
        score += 15
        signals.append("BULLETS_NONE")
    elif bcount < 3:
        score += 12
        signals.append("BULLETS_CRITICAL")
    elif bcount < 5:
        score += 6
        signals.append("BULLETS_LOW")
    elif bcount > 7:
        score += 1  # slight penalty, might be spammy
        signals.append("BULLETS_EXCESS")

    if not btext:
        return min(25, score), signals

    # Bullet length analysis
    lines = [l.strip() for l in btext.split("\n") if l.strip()]
    if lines:
        avg_len = sum(len(l) for l in lines) / len(lines)
        if avg_len < 60:
            score += 5
            signals.append("BULLETS_TOO_SHORT")
        elif avg_len > 400:
            score += 3
            signals.append("BULLETS_WALL_OF_TEXT")

    # Readability penalties
    caps_headers = sum(1 for l in lines if l and l.split()[0].isupper() and len(l.split()[0]) > 2)
    if caps_headers >= 3 or (lines and caps_headers == len(lines)):
        score += 5
        signals.append("BULLETS_ALL_CAPS")

    # Check for structured headers (e.g. "[CLINICALLY PROVEN]" or "MAX STRENGTH -")
    structured_headers = 0
    for l in lines:
        if not l:
            continue
        # Matches brackets, parenthesis, or capitalized first 2-5 words ending with colon/dash/pipe
        if re.match(r"^\[[^\]]+\]", l) or re.match(r"^\([^\)]+\)", l) or re.match(r"^[A-Z\s]{4,}(?:\s+[A-Z\s]{4,}){0,3}\s*[\-\:\|]", l):
            structured_headers += 1

    if structured_headers < 3 and bcount >= 3:
        score += 3
        signals.append("BULLETS_UNSTRUCTURED_HEADERS")

    # Conversational QA audit (scans for direct answer/question triggers)
    conversational_patterns = [r"\b(who|what|where|why|how|when|is it|can i|does it|safe for|how to|benefits|features|specifications)\b"]
    has_conv = any(re.search(pat, btext.lower()) for pat in conversational_patterns)
    if not has_conv and bcount >= 3:
        score += 3
        signals.append("BULLETS_NO_CONVERSATIONAL_COPY")

    if re.search(r"[✓✔⭐★✅🔥⚡💪]|\*{2,}", btext):
        score += 3
        signals.append("BULLETS_SYMBOL_SPAM")

    vague_phrases = ["high quality", "premium", "best in class", "top rated", "amazing", "incredible",
                     "our product", "we believe", "designed to", "experience the"]
    vague_count = sum(1 for vp in vague_phrases if vp in btext.lower())
    if vague_count >= 3:
        score += 4
        signals.append("BULLETS_VAGUE_COPY")

    question_words = ["contains", "provides", "supports", "helps", "made with", "free from", "designed for"]
    has_qw = sum(1 for qw in question_words if qw in btext.lower())
    if has_qw < 2 and bcount >= 3:
        score += 3
        signals.append("BULLETS_NO_QA_STRUCTURE")

    return min(25, score), list(dict.fromkeys(signals))


def _score_attribute_density(title: Optional[str], bullets_text: Optional[str], category_hint: Optional[str]) -> tuple[int, list[str]]:
    """Score how many structured attributes Rufus can extract.

    Returns (score 0-20, [signal tags]).
    """
    signals = []
    combined = f"{title or ''} {bullets_text or ''}"
    cat = _detect_category(combined, category_hint)
    family = _get_attribute_family(cat)
    attr_count, found_types = _count_attribute_types(combined, family)

    family_size = len(family)
    if family_size == 0:
        return 0, []

    ratio = attr_count / family_size
    if ratio >= 0.7:
        score = 0
    elif ratio >= 0.5:
        score = 4
        signals.append("ATTRIBUTES_MODERATE")
    elif ratio >= 0.3:
        score = 8
        signals.append("ATTRIBUTES_LOW")
    elif ratio > 0:
        score = 12
        signals.append("ATTRIBUTES_SPARSE")
    else:
        score = 16
        signals.append("ATTRIBUTES_NONE")

    qty_found = bool(re.search(r"\b\d+\s*(mg|mcg|iu|g|oz|ml|fl oz|count|pack|servings?|capsules?|%|inch|cm|lbs?)\b", combined.lower()))
    if not qty_found:
        score += 4
        signals.append("NO_QUANTITY_INFO")

    return min(20, score), list(dict.fromkeys(signals))


def _score_qa(qa_count: Optional[int], bullets_text: Optional[str]) -> tuple[int, list[str]]:
    """Score Q&A coverage.

    Returns (score 0-15, [signal tags]).
    """
    signals = []
    score = 0
    qc = qa_count or 0

    if qc == 0:
        score += 12
        signals.append("QA_ZERO")
    elif qc < 3:
        score += 8
        signals.append("QA_CRITICAL")
    elif qc < 5:
        score += 4
        signals.append("QA_LOW")
    elif qc < 10:
        score += 2
        signals.append("QA_MODERATE")

    if qc == 0 and bullets_text and len(bullets_text) > 200:
        score += 3
        signals.append("QA_MISSING_DESPITE_BULLETS")

    return min(15, score), list(dict.fromkeys(signals))


def _score_visual_structured(image_count: Optional[int], has_a_plus: Optional[bool],
                             bullets_text: Optional[str]) -> tuple[int, list[str]]:
    """Score visual and structured content readiness.

    Returns (score 0-15, [signal tags]).
    """
    signals = []
    score = 0
    imgs = image_count or 0

    if imgs < 3:
        score += 8
        signals.append("IMAGES_CRITICAL")
    elif imgs < 5:
        score += 4
        signals.append("IMAGES_LOW")
    elif imgs < 7:
        score += 2
        signals.append("IMAGES_MODERATE")

    if has_a_plus is False:
        score += 5
        signals.append("NO_A_PLUS")
    elif has_a_plus is None:
        score += 2
        signals.append("A_PLUS_UNKNOWN")

    if has_a_plus is False and bullets_text and len(bullets_text) < 300:
        score += 2
        signals.append("THIN_CONTENT_NO_APLUS")

    return min(15, score), list(dict.fromkeys(signals))


def _score_competitive_position(bsr: Optional[int], review_count: Optional[int],
                                rating: Optional[float], price: Optional[float]) -> tuple[int, list[str]]:
    """Score competitive vulnerability based on traction signals.

    Returns (score 0-10, [signal tags]).
    """
    signals = []
    score = 0
    reviews = review_count or 0

    if reviews < 50:
        score += 2
        signals.append("EARLY_STAGE")
    elif reviews > 1000 and rating and rating < 4.2:
        score += 6
        signals.append("HIGH_VOLUME_LOW_RATING")
    elif reviews > 500 and rating and rating < 4.0:
        score += 5
        signals.append("MODERATE_VOLUME_POOR_RATING")

    if bsr is not None:
        if bsr > 30_000:
            score += 3
            signals.append("BSR_STRUGGLING")
        elif bsr > 15_000:
            score += 1
            signals.append("BSR_MID_TIER")

    if price is not None:
        if price < 15:
            score += 2
            signals.append("LOW_PRICE_NO_BUDGET")

    return min(10, score), list(dict.fromkeys(signals))


def _backend_semantic_score(asin: str) -> tuple[int, list[str], dict] | None:
    if not _backend or not asin:
        return None

    analysis = _backend.analyze_listing(asin)
    if not analysis:
        return None

    relations = analysis.get("relations", [])
    if not relations:
        return None

    score = 0
    signals = []
    breakdown: dict[str, dict] = {}

    cluster_scores: dict[str, list[float]] = {}
    for r in relations:
        cluster = r.get("cluster", "Unknown")
        cluster_scores.setdefault(cluster, []).append(r.get("confidence_score", 0))

    for cluster, confidences in cluster_scores.items():
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        grade = "A" if avg_conf >= 0.8 else "B" if avg_conf >= 0.65 else "C" if avg_conf >= 0.5 else "D" if avg_conf >= 0.35 else "F"
        breakdown[cluster] = {
            "avg_confidence": round(avg_conf, 3),
            "grade": grade,
            "relations_scored": len(confidences),
        }

        if avg_conf < 0.35:
            score += 3
            signals.append(f"COSMO_CRITICAL_{cluster.upper()}")
        elif avg_conf < 0.50:
            score += 2
            signals.append(f"COSMO_LOW_{cluster.upper()}")
        elif avg_conf < 0.65:
            score += 1
            signals.append(f"COSMO_WEAK_{cluster.upper()}")

    keyword_safety = analysis.get("keyword_safety", "")
    if keyword_safety == "UNSAFE":
        score += 3
        signals.append("COSMO_KEYWORD_UNSAFE")
    elif keyword_safety == "CAUTION":
        score += 1
        signals.append("COSMO_KEYWORD_CAUTION")

    overall = analysis.get("overall_score", 0)
    if isinstance(overall, int) and overall < 30:
        score += 2
        signals.append("COSMO_READINESS_CRITICAL")
    elif isinstance(overall, int) and overall < 50:
        score += 1
        signals.append("COSMO_READINESS_LOW")

    return min(15, score), signals, breakdown


# ---------------------------------------------------------------------------
# Dynamic Category Weighting Presets
# ---------------------------------------------------------------------------

CATEGORY_WEIGHTS = {
    "supplement": {
        "title": 0.15,
        "bullets": 0.15,
        "attributes": 0.30,
        "qa": 0.25,
        "visual": 0.10,
        "competitive": 0.05
    },
    "skincare": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.25,
        "qa": 0.15,
        "visual": 0.20,
        "competitive": 0.05
    },
    "pet": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.25,
        "qa": 0.15,
        "visual": 0.20,
        "competitive": 0.05
    },
    "kitchen": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.15,
        "qa": 0.15,
        "visual": 0.30,
        "competitive": 0.05
    },
    "fitness": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.20,
        "qa": 0.15,
        "visual": 0.25,
        "competitive": 0.05
    },
    "home_office": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.15,
        "qa": 0.15,
        "visual": 0.30,
        "competitive": 0.05
    },
    "baby": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.20,
        "qa": 0.15,
        "visual": 0.25,
        "competitive": 0.05
    },
    "automotive": {
        "title": 0.15,
        "bullets": 0.20,
        "attributes": 0.20,
        "qa": 0.15,
        "visual": 0.25,
        "competitive": 0.05
    },
    "general": {
        "title": 0.20,
        "bullets": 0.25,
        "attributes": 0.20,
        "qa": 0.15,
        "visual": 0.10,
        "competitive": 0.10
    }
}

MAX_SCORES = {
    "title": 20,
    "bullets": 25,
    "attributes": 20,
    "qa": 15,
    "visual": 15,
    "competitive": 10
}


def _analyze_bullet_hygiene(bullets_text: Optional[str]) -> tuple[float, list[str], dict]:
    """Analyzes structural/copywriting quality of bullets.
    Checks bolded headers consistency, bullet length standard deviation, and empty jargon ratio.
    """
    signals = []
    btext = (bullets_text or "").strip()
    if not btext:
        return 0.0, [], {}
        
    lines = [l.strip() for l in btext.split("\n") if l.strip()]
    if not lines:
        return 0.0, [], {}
        
    total_bullets = len(lines)
    
    # 1. Bolded / Uppercase Lead-in Hook Consistency
    structured_hooks = 0
    for l in lines:
        if re.match(r"^\[[^\]]+\]", l) or re.match(r"^\([^\)]+\)", l) or re.match(r"^[A-Z0-9\s\&\/\-]{3,}(?:\s+[A-Z0-9\s\&\/\-]{3,}){0,4}\s*[\-\:\|]", l):
            structured_hooks += 1
            
    hook_ratio = structured_hooks / total_bullets
    
    # 2. Length balance (standard deviation)
    lengths = [len(l) for l in lines]
    avg_len = sum(lengths) / total_bullets
    
    variance = sum((x - avg_len) ** 2 for x in lengths) / total_bullets
    std_dev = math.sqrt(variance)
    
    # 3. Fluff / Corporate Jargon ratio
    fluff_terms = [
        r"\b(revolutionary|cutting-edge|state-of-the-art|world-class|unmatched|premium quality|best in class|game-changing|next-generation|ultimate|highly advanced|exceptional quality|incredible results|guaranteed|maximum strength|top rated)\b"
    ]
    
    fluff_count = 0
    for pat in fluff_terms:
        m = re.findall(pat, btext.lower())
        if m:
            fluff_count += len(m)
            
    words = btext.split()
    total_words = max(1, len(words))
    fluff_ratio = (fluff_count / total_words) * 100
    
    score = 0.0
    
    if hook_ratio < 0.6 and total_bullets >= 3:
        score += 3
        signals.append("BULLETS_STRUCTURE_INCONSISTENT")
    elif hook_ratio >= 0.9:
        signals.append("BULLETS_STRUCTURE_EXCELLENT")
        
    if std_dev > 150 and avg_len > 100:
        score += 3
        signals.append("BULLETS_UNEVEN_LENGTHS")
        
    if fluff_ratio > 1.5:
        score += 3
        signals.append("BULLETS_HIGH_FLUFF_RATIO")
        
    weak_beginnings = 0
    for l in lines:
        words_in_line = l.split()
        if not words_in_line:
            continue
        first_word = words_in_line[0].lower().strip(".:;,!?\"'()[]-*✓✔⭐✅")
        if first_word in ("it", "this", "our", "the", "we", "you", "they", "is", "are", "and"):
            weak_beginnings += 1
            
    weak_beginning_ratio = weak_beginnings / total_bullets
    if weak_beginning_ratio > 0.4:
        score += 2
        signals.append("BULLETS_WEAK_HOOKS")
        
    return min(10.0, score), signals, {
        "hook_ratio": round(hook_ratio, 2),
        "length_std_dev": round(std_dev, 1),
        "average_length": round(avg_len, 1),
        "fluff_ratio_pct": round(fluff_ratio, 2),
        "weak_beginning_ratio": round(weak_beginning_ratio, 2)
    }


def _score_liability_and_safety(title: Optional[str], bullets_text: Optional[str], category_hint: Optional[str]) -> tuple[int, list[str], dict]:
    """Scan for compliance issues:
    1. FDA Disease Claims (cure, treat, prevent, eczema, psoriasis, arthritis, anxiety, insomnia)
    2. Greenwashing (chemical-free, toxin-free, 100% natural)
    3. Aggressive promises (results overnight, permanent cure, miracle cure)
    """
    signals = []
    score = 0
    combined = f"{title or ''} {bullets_text or ''}".lower()
    cat = _detect_category(combined, category_hint)
    
    fda_terms = [
        r"\b(cure|cures|curing)\b",
        r"\b(treat|treats|treating|treatment of)\b",
        r"\b(heal|heals|healing)\b",
        r"\b(prevent|prevents|preventing)\b",
        r"\b(diagnose|diagnoses|diagnosing)\b",
        r"\b(therapy|therapeutic)\b",
        r"\b(disease|diseases|illness|illnesses|chronic)\b",
        r"\b(insomnia|anxiety|depression|arthritis|eczema|psoriasis|acne|cancer|tumors?)\b"
    ]
    
    fda_matches = []
    if cat in ("supplement", "skincare"):
        for pat in fda_terms:
            m = re.findall(pat, combined)
            if m:
                fda_matches.extend(m)
                
    greenwash_terms = [
        r"\bchemical.free\b",
        r"\btoxin.free\b",
        r"\b100% natural\b",
        r"\ball.natural\b",
        r"\bcompletely.natural\b",
        r"\beco.friendly\b"
    ]
    greenwash_matches = []
    for pat in greenwash_terms:
        m = re.findall(pat, combined)
        if m:
            greenwash_matches.extend(m)
            
    promise_terms = [
        r"\b(miracle|miraculous)\b",
        r"\bovernight.results\b",
        r"\binstant.results\b",
        r"\bresults.guaranteed\b",
        r"\bpermanent.cure\b",
        r"\b100%.guaranteed\b",
        r"\bguaranteed.to.work\b"
    ]
    promise_matches = []
    for pat in promise_terms:
        m = re.findall(pat, combined)
        if m:
            promise_matches.extend(m)
            
    breakdown_data = {
        "fda_disease_claims": len(fda_matches),
        "greenwashing_claims": len(greenwash_matches),
        "aggressive_promises": len(promise_matches)
    }
    
    if len(fda_matches) >= 2:
        score += 8
        signals.append("LQS_CRITICAL_FDA_LIABILITY")
    elif len(fda_matches) == 1:
        score += 4
        signals.append("LQS_CAUTION_FDA_LIABILITY")
        
    if len(greenwash_matches) >= 2:
        score += 4
        signals.append("LQS_GREENWASHING_CAUTION")
    elif len(greenwash_matches) == 1:
        score += 2
        signals.append("LQS_GREENWASHING_WARNING")
        
    if len(promise_matches) >= 2:
        score += 6
        signals.append("LQS_UNSUBSTANTIATED_PROMISE")
    elif len(promise_matches) == 1:
        score += 3
        signals.append("LQS_UNSUBSTANTIATED_PROMISE_WARNING")
        
    return min(20, score), signals, breakdown_data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_listing(p: Prospect, backend_result: tuple[int, list[str], dict] | None = None) -> tuple[int, list[str], dict]:
    """Return (quality_score 0-100, [signals], breakdown dict).

    Higher score = more gaps = more need for Rufus optimization.
    """
    title_score, title_signals = _score_title(p.post_title)
    bullet_score, bullet_signals = _score_bullets(p.post_body, p.bullet_count)
    attr_score, attr_signals = _score_attribute_density(p.post_title, p.post_body, p.category)
    qa_score, qa_signals = _score_qa(p.qa_count, p.post_body)
    visual_score, visual_signals = _score_visual_structured(p.image_count, p.has_a_plus, p.post_body)
    comp_score, comp_signals = _score_competitive_position(
        getattr(p, "_bsr", None), p.listing_review_count, p.listing_rating, p.listing_price
    )
    liab_score, liab_signals, liab_breakdown = _score_liability_and_safety(p.post_title, p.post_body, p.category)
    bullet_hyg_score, bullet_hyg_signals, bullet_hyg_metrics = _analyze_bullet_hygiene(p.post_body)

    combined_text = f"{p.post_title or ''} {p.post_body or ''}"
    cat = _detect_category(combined_text, p.category)
    weights = CATEGORY_WEIGHTS.get(cat, CATEGORY_WEIGHTS["general"])

    # 1. Run Computational Linguistics Audits
    flesch_score = _calculate_flesch_kincaid(combined_text)
    ttr_score = _calculate_lexical_diversity(combined_text)
    cosmo_density = _calculate_cosmo_relation_density(combined_text)

    # 2. Run new advanced NLP metrics
    fk_grade_level = _calculate_fk_grade_level(combined_text)
    gunning_fog = _calculate_gunning_fog(combined_text)
    stemmed_ttr = _calculate_stemmed_ttr(combined_text)
    
    keyword_stuffing_bonus, keyword_stuffing_phrases = _detect_keyword_stuffing(combined_text)
    cosmo_categories, cosmo_relation_density, cosmo_relation_signals, cosmo_matches = _detect_cosmo_relations(combined_text)

    linguistic_signals = []
    linguistic_bonus = 0

    # Low readability ease increases optimization need
    if flesch_score < 40:
        linguistic_bonus += 4
        linguistic_signals.append("LINGUISTIC_LOW_READABILITY")
    elif flesch_score < 60:
        linguistic_bonus += 2
        linguistic_signals.append("LINGUISTIC_MODERATE_READABILITY")

    # Readability Grade Level
    if fk_grade_level > 12.0:
        linguistic_bonus += 3
        linguistic_signals.append("LINGUISTIC_OVERCOMPLEX_JARGON")
    elif fk_grade_level < 5.0 and len(combined_text) > 100:
        linguistic_bonus += 2
        linguistic_signals.append("LINGUISTIC_TOO_SIMPLE")

    # Gunning Fog
    if gunning_fog > 14.0:
        linguistic_bonus += 2
        linguistic_signals.append("LINGUISTIC_FOGGY_READABILITY")

    # Low TTR = keyword stuffing which conversational search models actively penalize
    if ttr_score < 0.45:
        linguistic_bonus += 4
        linguistic_signals.append("LINGUISTIC_KEYWORD_STUFFING")
    elif ttr_score < 0.60:
        linguistic_bonus += 2
        linguistic_signals.append("LINGUISTIC_LOW_LEXICAL_DIVERSITY")

    # Stemmed TTR
    if stemmed_ttr < 0.40:
        linguistic_bonus += 4
        linguistic_signals.append("LINGUISTIC_STEMMED_TTR_CRITICAL")
    elif stemmed_ttr < 0.50:
        linguistic_bonus += 2
        linguistic_signals.append("LINGUISTIC_STEMMED_TTR_LOW")

    # Keyword stuffing repetitions
    if keyword_stuffing_phrases:
        linguistic_bonus += keyword_stuffing_bonus
        linguistic_signals.append("KEYWORD_STUFFING_DANGER")

    # Low COSMO relational link prepositions = listing does not build clear graph nodes
    if cosmo_density < 2.0:
        linguistic_bonus += 4
        linguistic_signals.append("LINGUISTIC_SPARSE_COSMO_NODES")
    elif cosmo_density < 3.5:
        linguistic_bonus += 2
        linguistic_signals.append("LINGUISTIC_WEAK_COSMO_NODES")

    # COSMO Ontological categories
    if cosmo_categories <= 1:
        linguistic_bonus += 4
        linguistic_signals.append("COSMO_LOW_RELATION_VARIETY")
    elif cosmo_categories == 2:
        linguistic_bonus += 2
        linguistic_signals.append("COSMO_WEAK_RELATION_VARIETY")
    elif cosmo_categories >= 4:
        linguistic_signals.append("COSMO_EXCELLENT_RELATION_VARIETY")

    if cosmo_relation_density < 1.0:
        linguistic_bonus += 3
        linguistic_signals.append("COSMO_SPARSE_RELATION_DENSITY")
    elif cosmo_relation_density >= 3.0:
        linguistic_signals.append("COSMO_HIGH_RELATION_DENSITY")

    # Calculate weighted gap score relative to maximum possible score
    raw_weighted = (
        weights["title"] * title_score +
        weights["bullets"] * bullet_score +
        weights["attributes"] * attr_score +
        weights["qa"] * qa_score +
        weights["visual"] * visual_score +
        weights["competitive"] * comp_score
    )

    max_weighted = (
        weights["title"] * MAX_SCORES["title"] +
        weights["bullets"] * MAX_SCORES["bullets"] +
        weights["attributes"] * MAX_SCORES["attributes"] +
        weights["qa"] * MAX_SCORES["qa"] +
        weights["visual"] * MAX_SCORES["visual"] +
        weights["competitive"] * MAX_SCORES["competitive"]
    )

    total = int((raw_weighted / max_weighted) * 100) if max_weighted > 0 else 0

    # Optional: enrich with backend COSMO semantic analysis if enabled
    backend_bonus = 0
    backend_signals: list[str] = []
    backend_breakdown: dict = {}
    if config.USE_BACKEND_SCORING and p.asin:
        if backend_result is None:
            backend_result = _backend_semantic_score(p.asin)
        if backend_result:
            backend_bonus, backend_signals, backend_breakdown = backend_result

    # Add linguistic sophistication, FDA liability, bullet hygiene, and backend adjustments
    total += int(linguistic_bonus) + int(liab_score) + int(bullet_hyg_score) + backend_bonus
    total = min(100, total)

    all_signals = (title_signals + bullet_signals + attr_signals + qa_signals + 
                   visual_signals + comp_signals + liab_signals + backend_signals + 
                   linguistic_signals + bullet_hyg_signals + cosmo_relation_signals)
    all_signals = list(dict.fromkeys(all_signals))

    breakdown = {
        "title": {"score": title_score, "signals": title_signals},
        "bullets": {"score": bullet_score, "signals": bullet_signals},
        "attributes": {"score": attr_score, "signals": attr_signals},
        "qa": {"score": qa_score, "signals": qa_signals},
        "visual": {"score": visual_score, "signals": visual_signals},
        "competitive": {"score": comp_score, "signals": comp_signals},
        "liability_and_safety": {"score": liab_score, "signals": liab_signals, "details": liab_breakdown},
        "bullet_hygiene": {
            "score": bullet_hyg_score,
            "signals": bullet_hyg_signals,
            "metrics": bullet_hyg_metrics
        },
        "linguistic_integrity": {
            "score": linguistic_bonus,
            "signals": linguistic_signals,
            "flesch_reading_ease": round(flesch_score, 2),
            "fk_grade_level": round(fk_grade_level, 2),
            "gunning_fog_index": round(gunning_fog, 2),
            "type_token_ratio_ttr": round(ttr_score, 3),
            "stemmed_ttr": round(stemmed_ttr, 3),
            "keyword_stuffing_stems": keyword_stuffing_phrases,
            "cosmo_relational_density": round(cosmo_density, 2),
            "cosmo_relation_density_nlp": round(cosmo_relation_density, 2),
            "cosmo_categories_covered": cosmo_categories,
            "cosmo_ontological_matches": cosmo_matches
        }
    }
    if backend_breakdown:
        breakdown["backend_cosmo"] = {"score": backend_bonus, "signals": backend_signals, "clusters": backend_breakdown}

    return total, all_signals, breakdown


def score_all(listings: list[Prospect]) -> int:
    """Score and persist all listings. Returns count flagged as WEAK_LISTING.

    Gate: score >= threshold AND at least one structural signal.
    """
    STRUCTURAL_PREFIXES = ("TITLE_", "BULLETS_", "ATTRIBUTES_", "NO_", "QA_", "IMAGES_", "A_PLUS_", "THIN_CONTENT_", "LINGUISTIC_")
    DEMAND_PREFIXES = ("EARLY_STAGE", "HIGH_VOLUME", "MODERATE_VOLUME", "BSR_", "LOW_PRICE_")

    # Pre-fetch backend semantic scores for unique ASINs to avoid N+1 API calls
    backend_cache: dict[str, tuple[int, list[str], dict] | None] = {}
    if config.USE_BACKEND_SCORING:
        unique_asins = [p.asin for p in listings if p.asin]
        # Parallelize backend calls to avoid sequential N+1 latency
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = executor.map(_backend_semantic_score, unique_asins)
        backend_cache = dict(zip(unique_asins, results))

    weak_count = 0
    for p in listings:
        total, signals, breakdown = score_listing(p, backend_cache.get(p.asin))
        has_structural = any(s.startswith(STRUCTURAL_PREFIXES) for s in signals)
        is_weak = total >= config.LISTING_QUALITY_THRESHOLD and has_structural
        stage = "WEAK_LISTING" if is_weak else "SKIP"

        db.set_listing_quality_score(
            prospect_id=p.id,
            quality_score=total,
            quality_signals=",".join(signals),
            quality_breakdown=breakdown,
            stage=stage,
        )
        if stage == "WEAK_LISTING":
            weak_count += 1
    return weak_count
