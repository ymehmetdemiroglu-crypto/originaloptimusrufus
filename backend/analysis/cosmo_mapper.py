"""COSMO 15 Relation Type Mapper, Q&A Analyzer, and Seeding Engine."""

import re
from typing import Dict, List
import numpy as np
from core.embedding_engine import GeminiEmbeddingEngine

RELATION_DEFINITIONS = {
    "USED_FOR_FUNC": {
        "cluster": "Function",
        "patterns": [r"provides?\s+\w+", r"offers?\s+\w+", r"delivers?\s+\w+", r"features?\s+\w+", r"equipped\s+with", r"designed\s+to\s+\w+"],
        "weight": 1.0,
        "seed_question": "What is the primary function of this product?",
        "seed_answer_template": "The product is designed to {functionality} and features a premium build offering maximum efficiency.",
        "queries": ["what does this product do", "primary function of product", "main functionality", "what problem it solves", "key features and benefits"]
    },
    "USED_TO": {
        "cluster": "Function",
        "patterns": [r"used?\s+to\s+\w+", r"perfect\s+for\s+\w+ing", r"ideal\s+for\s+\w+ing", r"helps?\s+you\s+\w+"],
        "weight": 1.0,
        "seed_question": "What tasks or activities can I use this for?",
        "seed_answer_template": "It is perfect for {activities} and helps you easily manage daily tasks without extra effort.",
        "queries": ["what tasks can I do with this", "activities this supports", "what actions does this enable", "how to use this product"]
    },
    "CAPABLE_OF": {
        "cluster": "Function",
        "patterns": [r"can\s+\w+", r"able\s+to\s+\w+", r"handles?\s+\w+", r"\d+\s*(hours?|hrs?|days?|lbs?|pounds?)"],
        "weight": 1.0,
        "seed_question": "What are the performance limits and capacities of this product?",
        "seed_answer_template": "It is fully capable of withstanding heavy usage, and can handle up to {limit_specs} easily.",
        "queries": ["what can this product withstand", "durability limit", "measurable performance claim", "capacity specification"]
    },
    "USED_FOR_AUD": {
        "cluster": "Audience",
        "patterns": [r"for\s+\w+\s+(workers?|professionals?|drivers?|nurses?|teachers?)"],
        "weight": 0.9,
        "seed_question": "Is this product suitable for active professionals like nurses or teachers?",
        "seed_answer_template": "Yes, it is designed for professionals and active workers, making it a highly reliable tool during long shifts.",
        "queries": ["what job is this for", "professional users", "work environment suited for this", "nurses construction workers teachers"]
    },
    "USED_BY": {
        "cluster": "Audience",
        "patterns": [r"for\s+\w+\s+(owners?|parents?|enthusiasts?|lovers?)"],
        "weight": 0.9,
        "seed_question": "Who is the primary demographic that uses this product?",
        "seed_answer_template": "It is highly favored and used by active enthusiasts and busy individuals seeking premium daily utility.",
        "queries": ["who uses this product", "demographic lifestyle", "what type of hobbies do users have", "dog owners coffee lovers parents"]
    },
    "IS_A_DEMOGRAPHIC": {
        "cluster": "Audience",
        "patterns": [r"for\s+(seniors?|elderly|kids?|children|pregnant|athletes?)"],
        "weight": 0.9,
        "seed_question": "Is this product safe for children or seniors to use daily?",
        "seed_answer_template": "Absolutely. It is constructed with safe, BPA-free premium materials, making it ideal for both active athletes and children.",
        "queries": ["life stage of users", "seniors elderly kids children pregnant athletes", "physical characteristics of users", "allergy friendly safe for"]
    },
    "USED_FOR_EVE": {
        "cluster": "Context",
        "patterns": [r"for\s+\w+ing\s+(trips?|events?|parties?|camping|hiking)", r"perfect\s+for\s+(weddings?|birthdays?|holidays?)"],
        "weight": 0.8,
        "seed_question": "Can I bring this along for outdoor travel or holiday events?",
        "seed_answer_template": "Yes! It is highly packable and perfect for travel trips, camping adventures, and outdoor events.",
        "queries": ["what event is this for", "birthdays weddings parties", "holidays trips vacations", "special occasion use"]
    },
    "USED_ON": {
        "cluster": "Context",
        "patterns": [r"for\s+(daily|weekly|morning|evening|winter|summer)\s+\w+", r"all\s+(day|night|season)\s+\w+"],
        "weight": 0.7,
        "seed_question": "Is this product intended for daily year-round use?",
        "seed_answer_template": "Designed for all-season use, it is built to withstand both summer heat and winter cold during your daily commute.",
        "queries": ["when to use this product", "time of day or season", "morning evening daily year round", "summer winter all day long"]
    },
    "USED_IN_LOC": {
        "cluster": "Context",
        "patterns": [r"for\s+\w+\s+(home|office|car|gym|kitchen|bedroom|outdoor)", r"in\s+(the\s+)?\w+\s+(drawer|bag|car|shower|desk)"],
        "weight": 0.8,
        "seed_question": "Where is the best location to store or use this product?",
        "seed_answer_template": "It fits standard spaces and is highly versatile, whether used at the gym, in the office, or stored in a backpack drawer.",
        "queries": ["where is this used", "location or setting", "home office gym kitchen outdoor", "fits in bag drawer car cup holder"]
    },
    "USED_IN_BODY": {
        "cluster": "Context",
        "patterns": [r"(back|knee|neck|shoulder|foot|hand)\s+\w+", r"\w+\s+(pain|support|relief|comfort)", r"ergonomic\s+for\s+\w+"],
        "weight": 0.7,
        "seed_question": "Does this product provide any physiological support or ergonomic relief?",
        "seed_answer_template": "Featuring an ergonomic layout, it provides excellent physical relief and support for your hands and body joints.",
        "queries": ["physiological support", "back knee neck shoulder hand body part", "pain relief comfort posture", "ergonomic shape"]
    },
    "USED_AS": {
        "cluster": "Classification",
        "patterns": [r"works?\s+as\s+a\s+\w+", r"doubles?\s+as\s+a\s+\w+", r"functions?\s+as\s+a\s+\w+"],
        "weight": 0.6,
        "seed_question": "Can this product double as a different utility or alternative role?",
        "seed_answer_template": "Yes, it doubles as a convenient travel organizer and functions as a multi-purpose tool.",
        "queries": ["alternative role or role function", "doubles as a", "functions as a", "secondary utility"]
    },
    "IS_A": {
        "cluster": "Classification",
        "patterns": [r"is\s+a\s+\w+", r"type\s+of\s+\w+", r"\w+-style\s+\w+"],
        "weight": 0.5,
        "seed_question": "What product category does this item fall into?",
        "seed_answer_template": "This is a premium, professional-grade product designed specifically for modern high-performance daily requirements.",
        "queries": ["what category of product is this", "what is this product classification", "type of item", "product style"]
    },
    "USED_WITH": {
        "cluster": "Complementary",
        "patterns": [r"pairs?\s+with", r"works?\s+with", r"compatible\s+with", r"use\s+with"],
        "weight": 0.9,
        "seed_question": "What accessories or items is this product best paired with?",
        "seed_answer_template": "It pairs beautifully with standard commuter accessories and works with matching high-performance travel gear.",
        "queries": ["what accessories pair with this", "compatible items", "works with matching gear", "accessory companion"]
    },
    "INTERESTED_IN": {
        "cluster": "Complementary",
        "patterns": [r"for\s+\w+\s+(living|lifestyle|design|decor)", r"eco-friendly|sustainable|organic|vegan|natural|minimalist|modern"],
        "weight": 0.7,
        "seed_question": "Is this product aligned with sustainable or modern minimalist designs?",
        "seed_answer_template": "Designed with a modern, minimalist aesthetic, it is made of eco-friendly, sustainable materials.",
        "queries": ["lifestyle interest", "eco friendly sustainable organic vegan", "minimalist modern design aesthetic", "values and interests"]
    },
    "WANTS": {
        "cluster": "Complementary",
        "patterns": [r"peace\s+of\s+mind|convenience|comfort|savings?", r"save\s+time|save\s+money|hassle-free|worry-free", r"easy\s+to\s+\w+|simple\s+to\s+\w+"],
        "weight": 0.7,
        "seed_question": "What kind of user experience or reassurance does this product aim to deliver?",
        "seed_answer_template": "It offers complete peace of mind, presenting a hassle-free, comfortable experience that is simple and easy to operate.",
        "queries": ["emotional desire or benefit", "peace of mind convenience comfort savings", "save time money hassle free", "easy simple worry free"]
    },
}

CLUSTER_WEIGHTS = {
    "Function": 0.30,
    "Audience": 0.25,
    "Context": 0.25,
    "Classification": 0.10,
    "Complementary": 0.10,
}

class CosmoMapper:
    def __init__(self, embedding_engine: GeminiEmbeddingEngine):
        self.embedder = embedding_engine
        self._precompute_relation_centroids()
        
    def _precompute_relation_centroids(self):
        """Precompute the averaged query embedding centroid for each relation type using native batching."""
        self.centroids = {}
        for relation, config in RELATION_DEFINITIONS.items():
            queries = config.get("queries", [relation])
            # Use embed_batch since it is highly performance-optimized and utilizes single-roundtrip batching
            embeddings = self.embedder.embed_batch(queries, dimensions=768, task_type="RETRIEVAL_QUERY")
            if embeddings:
                # Average vectors
                mean_emb = np.mean(embeddings, axis=0)
                # Re-normalize to unit length for accurate cosine similarity
                norm = np.linalg.norm(mean_emb)
                if norm > 0:
                    mean_emb = mean_emb / norm
                self.centroids[relation] = mean_emb
            else:
                self.centroids[relation] = np.zeros(768, dtype=np.float32)
                
    def _extract_listing_slots(self, text: str) -> Dict:
        """Dynamically extract product functionality, activities, and capacity specs from listing text."""
        slots = {
            "functionality": "high-performance utility and premium operation",
            "activities": "daily routines, office tasks, and outdoor travel",
            "limit_specs": "reliable durability and optimal standard capacity"
        }
        
        if not text or not text.strip():
            return slots
            
        text_lower = text.lower()
        
        # 1. Clean title to extract first phrase for functionality
        title_part = text.split("\n")[0]
        # Remove common e-commerce descriptors
        title_clean = re.sub(r"(keeps|keeps|perfect|ideal|great|insulated|organic|ceremonial|\d+oz|\d+\s*hrs?|BPA-Free).*", "", title_part, flags=re.IGNORECASE)
        title_clean = re.sub(r"[^\w\s\-]", "", title_clean).strip()
        if len(title_clean) > 5:
            slots["functionality"] = f"deliver premium {title_clean.lower()}"
            
        # Try to find specific action phrases in text
        bullets = [line.strip() for line in text.split("\n") if len(line.strip()) > 20]
        if len(bullets) > 1:
            first_bullet = bullets[1]
            func_match = re.search(r"\b(keeps|provides|offers|delivers|helps|supports)\b\s+([^,\.\-;]+)", first_bullet, re.IGNORECASE)
            if func_match:
                slots["functionality"] = func_match.group(0).lower().strip()
                
        # 2. Extract context activities
        activity_terms = []
        possible_activities = [
            "gym", "travel", "office", "commute", "hiking", "cycling", "fitness", "meditation",
            "workout", "yoga", "baking", "smoothies", "lattes", "running", "camping", "kitchen",
            "study", "school", "sports", "commuting", "long shifts", "classroom", "gardening"
        ]
        for act in possible_activities:
            if act in text_lower:
                activity_terms.append(act)
        
        if len(activity_terms) >= 2:
            slots["activities"] = f"{', '.join(activity_terms[:-1])}, and {activity_terms[-1]}"
        elif len(activity_terms) == 1:
            slots["activities"] = f"active routines like {activity_terms[0]}"
            
        # 3. Extract limit / capacity measurements
        measurements = re.findall(r"\b(\d+\s*(?:oz|ounces?|hrs?|hours?|lbs?|pounds?|ml|g|bag|cups?|%))\b", text_lower)
        if measurements:
            seen_meas = []
            for m in measurements:
                if m not in seen_meas:
                    seen_meas.append(m)
            if len(seen_meas) >= 2:
                slots["limit_specs"] = f"{seen_meas[0]} capacity, keeping standards verified for {seen_meas[1]}"
            else:
                slots["limit_specs"] = f"premium grade specification matching {seen_meas[0]}"
                
        return slots
    
    def analyze_listing(self, listing_text: str) -> Dict:
        results = []
        listing_emb = self.embedder.embed_single(listing_text, dimensions=768, task_type="RETRIEVAL_DOCUMENT")
        listing_emb_norm = np.linalg.norm(listing_emb)
        
        for relation, config in RELATION_DEFINITIONS.items():
            signals = self._detect_patterns(listing_text, config["patterns"])
            
            # Semantic score based on averaged relation centroid (fixes technical label mismatch)
            query_emb = self.centroids.get(relation)
            query_emb_norm = np.linalg.norm(query_emb)
            if listing_emb_norm == 0 or query_emb_norm == 0:
                semantic_score = 0.0
            else:
                semantic_score = float(np.dot(listing_emb, query_emb) / (listing_emb_norm * query_emb_norm))
            
            # High-fidelity fallback for offline mock mode to ensure realistic, stable, and category-appropriate scores
            if not self.embedder.client:
                words_listing = set(re.sub(r"[^\w\s]", " ", listing_text.lower()).split())
                query_words = []
                for q in config.get("queries", []):
                    query_words.extend(re.sub(r"[^\w\s]", " ", q.lower()).split())
                words_query = set(query_words)
                
                intersection = words_listing.intersection(words_query)
                union = words_listing.union(words_query)
                jaccard = len(intersection) / len(union) if union else 0.0
                
                # Boost Jaccard to simulate typical cosine embedding ranges (0.30 - 0.80)
                simulated_similarity = min(0.30 + jaccard * 0.50, 0.80)
                semantic_score = max(semantic_score, simulated_similarity)
            
            pattern_score = min(len(signals) * 0.25, 1.0)
            combined_score = (pattern_score ** 0.3) * (semantic_score ** 0.7)
            
            results.append({
                "relation": relation,
                "cluster": config["cluster"],
                "detected_signals": signals[:5],
                "confidence_score": round(combined_score, 3),
                "coverage_grade": self._score_to_grade(combined_score * 100),
            })
        
        total_score = int(self._compute_weighted_score(results))
        return {
            "relations": results,
            "total_score": total_score,
            "grade": self._score_to_grade(total_score),
        }

    def generate_qa_seeds(self, listing_text: str, target_relations: List[str] = None) -> List[Dict]:
        """Generates COSMO-aligned Q&A seeds targeting weak relations or gaps dynamically."""
        analysis = self.analyze_listing(listing_text)
        
        # If no relations specified, identify low confidence ones (< 0.45)
        if not target_relations:
            target_relations = [
                r["relation"] for r in analysis["relations"] 
                if r["confidence_score"] < 0.45
            ]
            
        # Ensure we always return at least 3 seeds
        if not target_relations:
            target_relations = ["USED_FOR_AUD", "USED_IN_LOC", "USED_WITH"]
            
        # Dynamically extract slots from the listing text
        slots = self._extract_listing_slots(listing_text)
            
        seeds = []
        for relation in target_relations:
            config = RELATION_DEFINITIONS.get(relation)
            if not config:
                continue
                
            seeds.append({
                "relation": relation,
                "cluster": config["cluster"],
                "question": config["seed_question"],
                "answer": config["seed_answer_template"].format(
                    functionality=slots["functionality"],
                    activities=slots["activities"],
                    limit_specs=slots["limit_specs"]
                )
            })
        return seeds
    
    def _detect_patterns(self, text: str, patterns: List[str]) -> List[str]:
        signals = []
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                # re.findall returns tuples when pattern has multiple capture groups
                if isinstance(m, tuple):
                    # Keep only non-empty captured groups, joined
                    parts = [p.strip() for p in m if p and p.strip()]
                    if parts:
                        signals.append(" ".join(parts))
                else:
                    signals.append(m.strip())
        return list(set(signals))
    
    def _compute_weighted_score(self, results: List[dict]) -> float:
        cluster_scores = {c: [] for c in CLUSTER_WEIGHTS}
        for r in results:
            cluster_scores[r["cluster"]].append(r["confidence_score"])
        
        weighted = 0
        for cluster, weight in CLUSTER_WEIGHTS.items():
            scores = cluster_scores[cluster]
            cluster_score = min(scores) if scores else 0.0
            weighted += cluster_score * weight * 100
        return weighted
    
    def _score_to_grade(self, score: float) -> str:
        if score >= 80: return "A"
        if score >= 65: return "B"
        if score >= 50: return "C"
        if score >= 35: return "D"
        return "F"
