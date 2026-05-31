"""Knowledge Base builder for RAG system.

Organizes prospect audit data, competitor benchmarks, and COSMO/Rufus optimization
concepts into clean, structured text chunks for semantic retrieval.
"""
from typing import List, Dict, Any, Optional
import json

class RAGDocument:
    def __init__(self, doc_id: str, content: str, metadata: Dict[str, Any]):
        self.doc_id = doc_id
        self.content = content
        self.metadata = metadata

class KnowledgeBaseBuilder:
    def __init__(self):
        pass

    def build_prospect_documents(self, brand_data: Dict[str, Any], prospect_data: Optional[Dict[str, Any]], competitors: List[Dict[str, Any]]) -> List[RAGDocument]:
        """Convert a prospect's full profile into semantic documents."""
        docs = []
        brand_key = brand_data.get("brand_key", "unknown")
        brand_name = brand_data.get("brand_name", "Unknown Brand")

        # 1. Core Profile & Scores Document
        scores_content = []
        scores_content.append(f"Audit Scores for brand {brand_name} (ASIN: {brand_data.get('anchor_asin', 'N/A')}).")
        if prospect_data:
            rufus_score = prospect_data.get("rufus_score")
            if rufus_score is not None:
                scores_content.append(f"Overall Rufus Optimization Score: {rufus_score}/100")
                scores_content.append(f"Intent Alignment Score: {prospect_data.get('intent_alignment_score', 0)}/25")
                scores_content.append(f"Attribute Density Score: {prospect_data.get('attribute_density_score', 0)}/25")
                scores_content.append(f"Conversational Readability Score: {prospect_data.get('conversational_readability_score', 0)}/25")
                scores_content.append(f"Q&A Coverage Score: {prospect_data.get('qa_coverage_score', 0)}/25")
                scores_content.append(f"Visual & Structured Content Score: {prospect_data.get('visual_structured_content_score', 0)}/25")
                scores_content.append(f"Competitive Relativity Score: {prospect_data.get('competitive_relativity_score', 0)}/25")
                scores_content.append(f"Rufus Citation Probability: {prospect_data.get('rufus_citation_probability', 'N/A')}")
            
            rufus_summary = prospect_data.get("rufus_summary")
            if rufus_summary:
                scores_content.append(f"Rufus Summary: {rufus_summary}")

        docs.append(RAGDocument(
            doc_id=f"{brand_key}_scores",
            content="\n".join(scores_content),
            metadata={"brand_key": brand_key, "type": "scores", "title": f"{brand_name} Audit Scores"}
        ))

        # 2. Critical Weaknesses Document
        if prospect_data and prospect_data.get("rufus_top_weaknesses"):
            weak_content = [f"Critical listing gaps and weaknesses for {brand_name}:"]
            try:
                raw_weaknesses = prospect_data["rufus_top_weaknesses"]
                parsed = json.loads(raw_weaknesses) if isinstance(raw_weaknesses, str) else raw_weaknesses
                for idx, w in enumerate(parsed or [], 1):
                    weak_content.append(
                        f"Gap #{idx} [{w.get('axis', 'Unknown Axis')}]: {w.get('issue', '')}\n"
                        f"Recommended Fix: {w.get('fix', '')}"
                    )
            except Exception:
                pass
            
            docs.append(RAGDocument(
                doc_id=f"{brand_key}_weaknesses",
                content="\n\n".join(weak_content),
                metadata={"brand_key": brand_key, "type": "weaknesses", "title": f"{brand_name} Gaps and Recommended Fixes"}
            ))

        # 3. Product Listing Features Document
        if prospect_data:
            feats_content = [
                f"Listing statistics and A+ content presence for {brand_name}:",
                f"Title: {prospect_data.get('post_title', 'N/A')}",
                f"Bullet Count: {prospect_data.get('bullet_count', 0)} (optimal is 5 or more)",
                f"Image Count: {prospect_data.get('image_count', 0)} (optimal is 7 or more)",
                f"Q&A Pairs: {prospect_data.get('qa_count', 0)} (optimal is 10 or more)",
                f"Has A+ Content: {'Yes' if prospect_data.get('has_a_plus') else 'No'}",
                f"Listing Rating: {prospect_data.get('listing_rating', 'N/A')} with {prospect_data.get('listing_review_count', 0)} reviews."
            ]
            docs.append(RAGDocument(
                doc_id=f"{brand_key}_features",
                content="\n".join(feats_content),
                metadata={"brand_key": brand_key, "type": "features", "title": f"{brand_name} Listing Stats"}
            ))

        # 4. Competitor Benchmarks Document
        if competitors:
            comp_content = [f"Competitor benchmark profiling for {brand_name}:"]
            for idx, c in enumerate(competitors, 1):
                comp_content.append(
                    f"Competitor #{idx}: {c.get('competitor_brand', 'Unknown')}\n"
                    f"  Bullets: {c.get('bullet_count', 0)} | Images: {c.get('image_count', 0)} | "
                    f"Q&A Pairs: {c.get('qa_count', 0)} | A+ Content: {'Yes' if c.get('has_a_plus') else 'No'}\n"
                    f"  Rating: {c.get('rating', 'N/A')} | Review Count: {c.get('review_count', 0)}"
                )
            
            docs.append(RAGDocument(
                doc_id=f"{brand_key}_competitors",
                content="\n\n".join(comp_content),
                metadata={"brand_key": brand_key, "type": "competitors", "title": f"{brand_name} Competitor Analysis"}
            ))

        # 5. General Optimization Concept Docs
        docs.extend(self.get_concept_documents())

        return docs

    def get_concept_documents(self) -> List[RAGDocument]:
        """Return static educational document resources about COSMO and Rufus."""
        return [
            RAGDocument(
                doc_id="concept_cosmo",
                content=(
                    "Amazon COSMO (Customer-Oriented Semantic Model for Optimization) is the semantic backbone "
                    "of Amazon's Rufus AI. COSMO analyzes listings based on client-intent relationships "
                    "rather than exact keyword matching. There are 12 primary semantic relations modeled: "
                    "1. USED_FOR_FUNC (what function the product fulfills)\n"
                    "2. USED_BY (what user group uses it)\n"
                    "3. CAPABLE_OF (what features or capabilities it has)\n"
                    "4. COMPLEMENTARY_TO (what items it works with)\n"
                    "5. DETECTED_SIGNALS (customer reviews highlighting attributes)\n"
                    "By optimizing listings for these relations, products are significantly more likely to be surfaced "
                    "in conversational Rufus shopping sessions."
                ),
                metadata={"type": "education", "title": "Understanding Amazon COSMO Model"}
            ),
            RAGDocument(
                doc_id="concept_rufus_axes",
                content=(
                    "Rufus optimization centers on 4 critical axes:\n"
                    "1. Intent Alignment: How well product description matches natural queries.\n"
                    "2. Attribute Density: Abundance of structured details (specs, materials, uses).\n"
                    "3. Conversational Readability: Natural, clear language optimized for voice/text queries.\n"
                    "4. Q&A Coverage: A robust seed of answered questions resolving common customer friction points.\n"
                    "By boosting these axes, sellers see their citation probability move from 'Low' or 'Medium' to 'High'."
                ),
                metadata={"type": "education", "title": "The Four Axes of Rufus Optimization"}
            ),
            RAGDocument(
                doc_id="concept_pricing_process",
                content=(
                    "Optimus Rufus process consists of a full-funnel optimization:\n"
                    "1. Audit: Assessing listing's present COSMO score and gaps.\n"
                    "2. Semantic Rewrite: Injecting optimal COSMO relationship terms organically.\n"
                    "3. Safety Gate: Multi-level validation to protect rank (lexical safety matching).\n"
                    "4. Performance A/B Testing: Causal attribution modeling measuring true lift.\n"
                    "Pricing is custom-tiered based on total catalog size, MRR requirements, and optimization scale. "
                    "A 15-minute scoping call is highly recommended to receive a quote."
                ),
                metadata={"type": "education", "title": "Optimus Rufus Process & Pricing"}
            )
        ]
