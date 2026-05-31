"""CSV listing optimizer service.

Processes batch rows through COSMO relationship analysis and the agentic copy optimizer,
generating optimized copy that increases Rufus readiness scores.
"""
import os
import sys
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Setup path to import agentic optimizer
acq_path = Path(__file__).resolve().parent.parent / "acquisition-tool"
if str(acq_path) not in sys.path:
    sys.path.append(str(acq_path))

os.environ.setdefault("RUFUS_PROMPT_PATH", str(acq_path / "prompts" / "rufus_system_prompt.txt"))
os.environ.setdefault("RUFUS_V2_PROMPT_PATH", str(acq_path / "prompts" / "rufus_system_prompt_v2.txt"))

from core.embedding_engine import engine
from analysis.cosmo_mapper import CosmoMapper
from agentic_optimizer import agentic_optimizer

class CSVOptimizerService:
    def __init__(self):
        self.cosmo_mapper = CosmoMapper(engine)

    def score_to_grade(self, score: float) -> str:
        if score >= 80: return "A"
        if score >= 65: return "B"
        if score >= 50: return "C"
        if score >= 35: return "D"
        return "F"

    async def optimize_row(self, row: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Optimize a single CSV listing row."""
        asin = row.get("asin", f"CSV-{index}")
        title = row.get("title", "")
        bullets_raw = row.get("bullets", "")
        description = row.get("description", "")
        
        # Parse bullets (pipe-separated)
        bullets = [b.strip() for b in bullets_raw.split("|") if b.strip()] if bullets_raw else []
        full_text = title + "\n" + "\n".join(bullets) + "\n" + description
        
        # Analyze original
        try:
            analysis = await asyncio.to_thread(self.cosmo_mapper.analyze_listing, full_text)
            before_score = analysis["total_score"]
            before_grade = self.score_to_grade(before_score)
        except Exception:
            before_score = 0
            before_grade = "F"
            
        before_data = {
            "asin": asin,
            "title": title,
            "bullets": bullets_raw,
            "description": description,
            "score": before_score,
            "grade": before_grade,
        }
        
        # Run agentic optimization
        opt_title = title
        opt_bullets_raw = bullets_raw
        opt_description = description
        after_score = before_score
        after_grade = before_grade
        
        try:
            opt_result = await asyncio.to_thread(
                agentic_optimizer.optimize_listing,
                original_title=title,
                original_bullets=bullets,
                original_description=description,
                category=row.get("category", "consumer product"),
                brand=row.get("brand", "Brand"),
                max_rounds=3,
                target_confidence=0.70,
            )
            
            opt_title = opt_result.get("title", title)
            opt_bullets = opt_result.get("bullets", bullets)
            opt_bullets_raw = "|".join(opt_bullets)
            opt_description = opt_result.get("description", description)
            
            opt_text = opt_title + "\n" + "\n".join(opt_bullets) + "\n" + opt_description
            opt_analysis = await asyncio.to_thread(self.cosmo_mapper.analyze_listing, opt_text)
            after_score = opt_analysis["total_score"]
            after_grade = self.score_to_grade(after_score)
            
        except Exception:
            pass
            
        after_data = {
            "asin": asin,
            "title": opt_title,
            "bullets": opt_bullets_raw,
            "description": opt_description,
            "score": after_score,
            "grade": after_grade,
        }
        
        return {
            "before": before_data,
            "after": after_data
        }
