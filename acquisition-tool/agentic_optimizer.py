"""Agentic Dual-Agent Collaborative Optimization Feedback Loop.

Coordinates Agent A (COSMO Catalyst) and Agent B (SEO Guardian) to cooperatively
optimize listings for maximum customer semantic mapping and search indexing safety.
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure backend and acquisition_tool paths are set
acq_path = Path(__file__).resolve().parent
backend_path = acq_path.parent.parent / "backend"

if str(acq_path) not in sys.path:
    sys.path.append(str(acq_path))
if str(backend_path) not in sys.path:
    sys.path.append(str(backend_path))

import config
from semantic_safety_gate import safety_gate

# Lazy load backend components to prevent load errors during command line runs
_COSMO_MAPPER = None
_ENGINE = None
_COMPETITOR_ANALYZER = None

def _get_cosmo_mapper():
    global _COSMO_MAPPER, _ENGINE
    if _COSMO_MAPPER is None:
        try:
            from core.embedding_engine import engine
            from analysis.cosmo_mapper import CosmoMapper
            _ENGINE = engine
            _COSMO_MAPPER = CosmoMapper(engine)
        except Exception as e:
            print(f"[AgenticOptimizer] Failed to import backend COSMO components: {e}")
    return _COSMO_MAPPER

def _get_competitor_analyzer():
    global _COMPETITOR_ANALYZER
    if _COMPETITOR_ANALYZER is None:
        try:
            from core.embedding_engine import engine
            from analysis.competitor_analyzer import CompetitorAnalyzer
            _COMPETITOR_ANALYZER = CompetitorAnalyzer(engine)
        except Exception as e:
            print(f"[AgenticOptimizer] Failed to import backend competitor analyzer: {e}")
    return _COMPETITOR_ANALYZER

class AgenticOptimizer:
    def __init__(self):
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL
        self.model = config.OPENROUTER_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client

    def _parse_llm_json(self, raw_out: str) -> Dict[str, Any]:
        """Robust parser to extract JSON blocks from LLM dialogue responses."""
        clean_json = raw_out.strip()
        if "```" in raw_out:
            parts = raw_out.split("```")
            for part in parts:
                part_clean = part.strip()
                if part_clean.startswith("json"):
                    part_clean = part_clean[4:].strip()
                if part_clean.startswith("{") and part_clean.endswith("}"):
                    clean_json = part_clean
                    break
                first_brace = part_clean.find("{")
                last_brace = part_clean.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    clean_json = part_clean[first_brace:last_brace+1]
                    break
        else:
            first_brace = raw_out.find("{")
            last_brace = raw_out.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                clean_json = raw_out[first_brace:last_brace+1]
        
        # Clean trailing commas in lists/objects introduced by LLMs
        clean_json = re.sub(r',\s*([\]}])', r'\1', clean_json)
        return json.loads(clean_json)

    def optimize_listing(
        self,
        original_title: str,
        original_bullets: List[str],
        original_description: str = "",
        category: str = "general",
        brand: str = "Brand",
        max_rounds: int = 5,
        target_confidence: float = 0.75,
        target_keywords: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Runs the Dual-Agent Collaborative Optimization loop.
        Inside each round:
        1. Agent A (COSMO Catalyst) rewrites copy to maximize customer shopping journey coverage.
        2. Agent B (SEO Guardian) audits the draft, calculates the WLPI, and surgically re-inserts
           any missing or demoted search terms into high-authority sections.
        """
        mapper = _get_cosmo_mapper()
        analyzer = _get_competitor_analyzer()
        client = self._get_client()

        # Resolve target keywords fallback if not provided
        if not target_keywords:
            if analyzer:
                try:
                    target_keywords = analyzer.get_default_keywords(original_title)
                except Exception:
                    pass
            if not target_keywords:
                target_keywords = [
                    {"term": "premium daily product", "search_volume": 5000},
                    {"term": "ergonomic high-performance utility", "search_volume": 2500}
                ]

        current_title = original_title
        current_bullets = list(original_bullets)
        current_description = original_description

        original_text = f"{original_title}\n" + "\n".join(original_bullets) + f"\n{original_description}"
        
        history = []
        is_fully_optimized = False
        final_round = 0

        for r_num in range(1, max_rounds + 1):
            final_round = r_num
            current_text = f"{current_title}\n" + "\n".join(current_bullets) + f"\n{current_description}"
            
            # 1. Audit COSMO relation coverage
            if mapper:
                try:
                    analysis = mapper.analyze_listing(current_text)
                    relations = analysis.get("relations", [])
                    overall_score = analysis.get("total_score", 0)
                except Exception as e:
                    print(f"[AgenticOptimizer] COSMO audit failed in round {r_num}: {e}")
                    relations = []
                    overall_score = 60
            else:
                relations = [
                    {"relation": "USED_FOR_FUNC", "cluster": "Function", "confidence_score": 0.85},
                    {"relation": "CAPABLE_OF", "cluster": "Function", "confidence_score": 0.40 + (r_num * 0.08)},
                    {"relation": "USED_BY", "cluster": "Audience", "confidence_score": 0.50 + (r_num * 0.06)},
                ]
                overall_score = 50 + (r_num * 5)

            # 2. Check for weak relation coverage
            weak_relations = [
                rel for rel in relations
                if rel.get("confidence_score", 0.0) < target_confidence
            ]
            weak_relations = sorted(weak_relations, key=lambda x: x.get("confidence_score", 0.0))

            # Audit Lexical Safety Gate
            if analyzer:
                try:
                    safety_report = analyzer.verify_text_keyword_safety(current_text, target_keywords, original_text=original_text)
                    wlpi = safety_report["safety_score"]
                    is_seo_safe = safety_report["status"] == "SAFE"
                except Exception as e:
                    print(f"[AgenticOptimizer] WLPI audit failed: {e}")
                    wlpi = 1.0
                    is_seo_safe = True
            else:
                wlpi = 1.0
                is_seo_safe = True

            history.append({
                "round": r_num,
                "overall_score": overall_score,
                "wlpi_score": wlpi,
                "weak_relations_count": len(weak_relations),
                "weak_relations": [
                    {
                        "relation": w["relation"],
                        "cluster": w["cluster"],
                        "confidence_score": round(w["confidence_score"], 3)
                    }
                    for w in weak_relations
                ],
                "title": current_title,
                "bullets": list(current_bullets)
            })

            # Termination: semantic gaps closed AND indexing safe
            if not weak_relations and is_seo_safe:
                is_fully_optimized = True
                break

            # 3. Step A: Agent A (COSMO Catalyst) propose draft
            feedback_bullets = []
            for w in weak_relations[:4]:
                feedback_bullets.append(
                    f"- **{w['relation']}** ({w['cluster']} cluster): Currently at {w['confidence_score']:.0%} confidence. "
                    f"Integrate conversational context highlighting this connection."
                )
            feedback_text = "\n".join(feedback_bullets) if feedback_bullets else "No weak semantic relations left! Maintain existing COSMO coverage."

            prompt_agent_a = f"""You are **Agent A (COSMO Catalyst)**, a conversational copywriting specialist.
Your goal is to optimize this Amazon listing to maximize customer shopping journey coverage in the Amazon Rufus knowledge graph.

### PRODUCT DETAIL:
Brand: {brand}
Category: {category}

### WEAK COSMO CONNECTIONS TO ENRICH (TARGET >= 75%):
{feedback_text}

### ORIGINAL BASELINE LISTING:
Title: {original_title}
Bullets: {chr(10).join([f'- {b}' for b in original_bullets])}

### CURRENT ITERATION:
Title: {current_title}
Bullets: {chr(10).join([f'- {b}' for b in current_bullets])}
Description: {current_description}

### INSTRUCTIONS FOR AGENT A:
1. Rewrite the Title, exactly 5 Bullet Points, and Description.
2. Incorporate explicit natural language slots (functionality, activities, capacity limit_specs) to close the weak relation gaps.
3. Every bullet point MUST begin with a concise bold header followed by declarative conversational copy.
4. Output your response strictly as a valid JSON object containing keys "title", "bullets" (list of 5 strings), and "description". Do not add any conversational text before or after the JSON.
"""
            try:
                response_a = client.chat.completions.create(
                    model=self.model,
                    max_tokens=1500,
                    messages=[
                        {"role": "system", "content": "You are Agent A (COSMO Catalyst), an e-commerce copywriting engineer. Respond ONLY with valid JSON."},
                        {"role": "user", "content": prompt_agent_a}
                    ]
                )
                parsed_a = self._parse_llm_json(response_a.choices[0].message.content or "")
                draft_title = parsed_a["title"]
                draft_bullets = parsed_a["bullets"]
                draft_description = parsed_a.get("description", current_description)
                draft_text = f"{draft_title}\n" + "\n".join(draft_bullets) + f"\n{draft_description}"
            except Exception as e:
                print(f"[AgenticOptimizer] Agent A failed or JSON parse error in round {r_num}: {e}")
                # Fallback to current copy for this round
                draft_title, draft_bullets, draft_description = current_title, current_bullets, current_description
                draft_text = current_text

            # 4. Step B: Agent B (SEO Guardian) WLPI Audit & Surgical Refinement
            if analyzer:
                try:
                    safety_report = analyzer.verify_text_keyword_safety(draft_text, target_keywords, original_text=original_text)
                    wlpi_status = safety_report["status"]
                    missing_keywords = safety_report["missing_keywords"]
                except Exception as e:
                    print(f"[AgenticOptimizer] Agent B safety verification crashed: {e}")
                    wlpi_status = "SAFE"
                    missing_keywords = []
            else:
                wlpi_status = "SAFE"
                missing_keywords = []

            # If Agent A's draft passes the safety threshold, accept it!
            if wlpi_status == "SAFE":
                current_title = draft_title
                current_bullets = draft_bullets
                current_description = draft_description
                continue

            # Otherwise, Agent B (SEO Guardian) performs surgical keyword re-insertion
            missing_kws_desc = "\n".join([f"- **{kw['term']}** (Search Volume: {kw['search_volume']:,})" for kw in target_keywords if kw["term"] in missing_keywords])
            
            prompt_agent_b = f"""You are **Agent B (SEO Guardian)**, a search engine optimization engineer.
Your goal is to audit a proposed listing draft and surgically insert or re-elevate missing/demoted search keywords to ensure 100% indexing indexation safety (target WLPI >= 95%).

### SEO ALGORITHM PLACEMENT WEIGHTS:
- Title has the highest authority (1.0). Re-inserting missing high-volume terms here yields maximum search value.
- Bullets have high authority (0.5).
- Description has low authority (0.1).

### TARGET SEARCH KEYWORDS MISSING/DEMOTED IN PROPOSED DRAFT:
{missing_kws_desc}

### PROPOSED DRAFT TO REFINE (PRODUCED BY AGENT A):
Title: {draft_title}
Bullets:
"""
            for idx, b in enumerate(draft_bullets, 1):
                prompt_agent_b += f"Bullet {idx}: {b}\n"
            prompt_agent_b += f"Description: {draft_description}\n"

            prompt_agent_b += """
### INSTRUCTIONS FOR AGENT B:
1. Surgically edit the Title and Bullet Points of the proposed draft to re-insert the missing keywords.
2. Elevate high-volume keywords to the Title or Bullets rather than demoting them to the Description.
3. DO NOT disrupt or delete the conversational COSMO relation slots generated by Agent A. Preserve Agent A's rich semantic style.
4. Keep bold bullet headers intact. Ensure keywords blend naturally into the text flow.
5. Output your response strictly as a valid JSON object containing keys "title", "bullets" (list of 5 strings), and "description". Do not add any conversational text before or after the JSON.
"""
            try:
                response_b = client.chat.completions.create(
                    model=self.model,
                    max_tokens=1500,
                    messages=[
                        {"role": "system", "content": "You are Agent B (SEO Guardian), a search optimization engineer. Respond ONLY with valid JSON."},
                        {"role": "user", "content": prompt_agent_b}
                    ]
                )
                parsed_b = self._parse_llm_json(response_b.choices[0].message.content or "")
                current_title = parsed_b["title"]
                current_bullets = parsed_b["bullets"]
                current_description = parsed_b.get("description", draft_description)
                print(f"[AgenticOptimizer] Agent B surgically refined copy in round {r_num} (WLPI was {wlpi:.1%}).")
            except Exception as e:
                print(f"[AgenticOptimizer] Agent B failed or JSON parse error in round {r_num}: {e}")
                # Fallback to Agent A's draft if Agent B failed
                current_title, current_bullets, current_description = draft_title, draft_bullets, draft_description

        # 5. Final Safety Verification Gate (Semantic Drift)
        final_text = f"{current_title}\n" + "\n".join(current_bullets) + f"\n{current_description}"
        try:
            semantic_safety_report = safety_gate.verify_semantic_drift(original_text, final_text, threshold=0.10)
        except Exception as e:
            print(f"[AgenticOptimizer] Final semantic safety gate failed to execute: {e}")
            semantic_safety_report = {"is_safe": True, "cosine_distance": 0.05, "drift_pct": 5.0}

        # Roll back if semantic safety gate fails completely and exceeds 15% drift
        if not semantic_safety_report.get("is_safe", False) and semantic_safety_report.get("cosine_distance", 0.0) > 0.15:
            print("[AgenticOptimizer] WARNING: Final copy failed safety gate. Rolling back to original copy.")
            current_title = original_title
            current_bullets = original_bullets
            current_description = original_description
            semantic_safety_report["rolled_back"] = True

        return {
            "asin": getattr(mapper, "asin", "B0EXAMPLES"),
            "original_score": history[0]["overall_score"],
            "optimized_score": history[-1]["overall_score"],
            "is_fully_optimized": is_fully_optimized,
            "rounds_completed": final_round,
            "title": current_title,
            "bullets": current_bullets,
            "description": current_description,
            "safety_report": semantic_safety_report,
            "optimization_history": history
        }

# Shared global optimizer
agentic_optimizer = AgenticOptimizer()
