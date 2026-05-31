# Omni-Dashboard MAS — Tool Manifest

**Version:** 1.0  
**Date:** 2026-05-30

---

## 1. Manifest Overview

This document provides the concrete function signatures, implementations, and agent mappings for every tool exposed to the Omni-Dashboard Multi-Agent System. All tools are implemented as Python functions with Pydantic input schemas and are registered in the `UnifiedToolRegistry`.

---

## 2. Analysis Tools

### 2.1 `cosmo_analysis_tool`

**Description:** Analyze an Amazon listing for COSMO semantic relation coverage across 15 relation types.

**Function Signature:**
```python
@tool(args_schema=CosmoAnalysisInput)
async def cosmo_analysis_tool(
    asin: str,
    title: str,
    bullets: list[str],
    description: str = ""
) -> CosmoAnalysisResponse:
    """Analyze an Amazon listing for COSMO semantic relation coverage."""
    mapper = _get_cosmo_mapper()
    
    # Offload CPU-bound embedding work to thread pool
    result = await asyncio.to_thread(
        mapper.analyze,
        asin=asin,
        title=title,
        bullets=bullets,
        description=description
    )
    
    return CosmoAnalysisResponse(
        asin=asin,
        overall_score=result["overall_score"],
        keyword_safety=result["keyword_safety"],
        embedding_dimensions=result["embedding_dimensions"],
        relation_coverage=result["relation_coverage"],
        gap_alerts=result.get("gap_alerts", []),
        safety_checks=result.get("safety_checks", [])
    )
```

**Input Schema (`CosmoAnalysisInput`):**
```python
class CosmoAnalysisInput(BaseModel):
    asin: str = Field(description="Amazon ASIN to analyze")
    title: str = Field(description="Current product title")
    bullets: List[str] = Field(default_factory=list, description="Current bullet points")
    description: str = Field(default="", description="Current product description")
```

**Output Schema (`CosmoAnalysisResponse`):**
```python
class CosmoAnalysisResponse(BaseModel):
    asin: str
    overall_score: float = Field(ge=0, le=100)
    keyword_safety: str = Field(pattern=r"^(SAFE|WARNING|UNSAFE)$")
    embedding_dimensions: int = Field(default=768)
    relation_coverage: Dict[str, float] = Field(
        description="15 relation type scores (0-100)"
    )
    gap_alerts: List[str] = Field(default_factory=list)
    safety_checks: List[Dict] = Field(default_factory=list)
```

**Used By:** `ListingAgent` (Listing Subgraph)

**Latency Target:** 2-5s

**Example Invocation:**
```python
result = await cosmo_analysis_tool.ainvoke({
    "asin": "B08N5WRWNW",
    "title": "HydroMax Insulated Water Bottle 32oz",
    "bullets": [
        "Keeps drinks cold for 24 hours",
        "BPA-free stainless steel",
        "Leak-proof lid with carry handle"
    ],
    "description": "The ultimate hydration companion..."
})
# Returns: { overall_score: 62, keyword_safety: "SAFE", ... }
```

---

### 2.2 `competitor_intel_tool`

**Description:** Generate competitor landscape, embedding similarity scores, and clustered gap opportunities.

**Function Signature:**
```python
@tool(args_schema=CompetitorIntelInput)
async def competitor_intel_tool(
    asin: str,
    competitor_asins: Optional[List[str]] = None
) -> CompetitorAnalysisResponse:
    """Generate competitor landscape and gap opportunities."""
    analyzer = _get_competitor_analyzer()
    
    # Auto-discover competitors if not provided
    if not competitor_asins:
        store = _get_data_store()
        competitor_asins = [
            c["asin"] for c in store.competitors.get(asin, [])
        ][:10]  # Max 10 competitors
    
    result = await asyncio.to_thread(
        analyzer.analyze,
        asin=asin,
        competitor_asins=competitor_asins
    )
    
    return CompetitorAnalysisResponse(**result)
```

**Input Schema (`CompetitorIntelInput`):**
```python
class CompetitorIntelInput(BaseModel):
    asin: str = Field(description="Client ASIN")
    competitor_asins: Optional[List[str]] = Field(
        default=None,
        description="Explicit competitor ASINs; auto-discover if omitted"
    )
```

**Output Schema (`CompetitorAnalysisResponse`):**
```python
class CompetitorAnalysisResponse(BaseModel):
    asin: str
    competitor_profiles: List[CompetitorProfile]
    gap_opportunities: List[GapOpportunity]
    positioning_summary: str
    similarity_matrix: Dict[str, float]
    cluster_labels: Optional[Dict[str, int]] = None

class CompetitorProfile(BaseModel):
    asin: str
    title: str
    similarity_score: float = Field(ge=0, le=1)
    key_strengths: List[str]
    key_weaknesses: List[str]

class GapOpportunity(BaseModel):
    cluster_id: int
    severity: str = Field(pattern=r"^(HIGH|MEDIUM|LOW)$")
    description: str
    affected_competitors: List[str]
    estimated_traffic_impact: Optional[float] = None
```

**Used By:** `CompetitorAgent` (Competitor Subgraph)

**Latency Target:** 3-10s

**Example Invocation:**
```python
result = await competitor_intel_tool.ainvoke({
    "asin": "B08N5WRWNW",
    "competitor_asins": ["B07YF4QK3L", "B09XYZ1234"]
})
```

---

### 2.3 `attribution_tool`

**Description:** Run Difference-in-Differences and Synthetic Control causal analysis.

**Function Signature:**
```python
@tool(args_schema=AttributionInput)
async def attribution_tool(
    asin: str,
    control_asins: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> AttributionResponse:
    """Run DiD/SCM causal analysis and project revenue impact."""
    model = _get_attribution_model()
    store = _get_data_store()
    
    treatment_history = store.traffic_history.get(asin, [])
    control_histories = {
        c: store.traffic_history.get(c, []) 
        for c in control_asins
    }
    
    # Run computations in thread pool
    did_result = await asyncio.to_thread(
        model.calculate_did_lift,
        treatment_history,
        control_histories
    )
    
    scm_result = await asyncio.to_thread(
        model.calculate_synthetic_control_lift,
        treatment_history,
        control_histories
    )
    
    financial = await asyncio.to_thread(
        model.estimate_financial_impact,
        did_result.get("lift_percent", 0),
        treatment_history
    )
    
    return AttributionResponse(
        asin=asin,
        did=DiDResult(**did_result),
        scm=SCMResult(**scm_result),
        financial_projection=FinancialProjection(**financial)
    )
```

**Input Schema (`AttributionInput`):**
```python
class AttributionInput(BaseModel):
    asin: str = Field(description="Treatment ASIN")
    control_asins: List[str] = Field(
        default_factory=list,
        description="Control ASINs for DiD/SCM"
    )
    start_date: Optional[str] = Field(
        default=None,
        description="ISO start date (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        default=None,
        description="ISO end date (YYYY-MM-DD)"
    )
```

**Output Schema (`AttributionResponse`):**
```python
class DiDResult(BaseModel):
    lift_percent: float
    p_value: float
    z_score: float
    confidence_interval: List[float]
    significant: bool
    
class SCMResult(BaseModel):
    synthetic_lift: float
    donor_weights: Dict[str, float]
    mse: float
    pre_treatment_mse: float
    
class FinancialProjection(BaseModel):
    current_monthly_revenue: float
    projected_monthly_revenue: float
    monthly_impact: float
    annual_impact: float
    
class AttributionResponse(BaseModel):
    asin: str
    did: DiDResult
    scm: SCMResult
    financial_projection: FinancialProjection
```

**Used By:** `AttributionAgent` (Attribution Subgraph)

**Latency Target:** 5-10s

**Example Invocation:**
```python
result = await attribution_tool.ainvoke({
    "asin": "B08N5WRWNW",
    "control_asins": ["B07YF4QK3L", "B09XYZ1234", "B08ABC5678"],
    "start_date": "2024-01-01",
    "end_date": "2024-03-31"
})
```

---

## 3. Pipeline Tools

### 3.1 `pipeline_trigger_tool`

**Description:** Manually trigger an acquisition pipeline stage.

**Function Signature:**
```python
@tool(args_schema=PipelineTriggerInput)
async def pipeline_trigger_tool(
    stage: str,
    limit: int = 10,
    brand_key: Optional[str] = None
) -> Dict[str, Any]:
    """Trigger an acquisition pipeline stage manually."""
    from backend.agent.jobs import JobRegistry
    
    VALID_STAGES = ["scrape", "enrich", "score", "draft", "sequence"]
    if stage not in VALID_STAGES:
        return {
            "success": False,
            "error": f"Invalid stage. Must be one of: {VALID_STAGES}"
        }
    
    registry = JobRegistry()
    job_type = f"{stage}_job"
    
    if not hasattr(registry, job_type):
        return {"success": False, "error": f"Job type {job_type} not found"}
    
    runner = getattr(registry, job_type)
    
    try:
        if brand_key:
            # Single brand targeting
            result = await asyncio.to_thread(runner, brand_key=brand_key)
        else:
            # Batch execution
            result = await asyncio.to_thread(runner, limit=limit)
        
        return {
            "success": True,
            "stage": stage,
            "jobs_created": result.get("count", 1),
            "job_ids": result.get("job_ids", [])
        }
    except Exception as exc:
        return {"success": False, "stage": stage, "error": str(exc)}
```

**Input Schema (`PipelineTriggerInput`):**
```python
class PipelineTriggerInput(BaseModel):
    stage: str = Field(
        description="Pipeline stage: scrape | enrich | score | draft | sequence"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max items to process")
    brand_key: Optional[str] = Field(
        default=None,
        description="Optional single brand target"
    )
```

**Output Schema:**
```python
class PipelineTriggerOutput(BaseModel):
    success: bool
    stage: str
    jobs_created: int = 0
    job_ids: List[str] = Field(default_factory=list)
    error: Optional[str] = None
```

**Used By:** `OutreachAgent`, `AdminCopilotAgent`

**HITL Required:** Yes (for `sequence` stage)

**Latency Target:** 2-8s

**Example Invocation:**
```python
# Trigger enrichment for top 20 brands
result = await pipeline_trigger_tool.ainvoke({
    "stage": "enrich",
    "limit": 20
})

# Trigger sequence for single brand (requires HITL approval)
result = await pipeline_trigger_tool.ainvoke({
    "stage": "sequence",
    "brand_key": "hydromax"
})
```

---

### 3.2 `apollo_enrich_tool`

**Description:** Enrich a brand with Apollo contact data.

**Function Signature:**
```python
@tool(args_schema=ApolloEnrichInput)
async def apollo_enrich_tool(
    brand_key: str,
    domain: Optional[str] = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """Enrich brand contact data via Apollo API."""
    from acquisition_tool.apollo_api import ApolloClient
    
    client = ApolloClient()
    store = _get_data_store()
    
    # Check cache if not force refresh
    if not force_refresh:
        brand = store.listings.get(brand_key, {})
        if brand.get("apollo_contact_id"):
            return {
                "success": True,
                "cached": True,
                "contact_email": brand.get("contact_email"),
                "contact_name": f"{brand.get('contact_first_name', '')} {brand.get('contact_last_name', '')}".strip(),
                "apollo_contact_id": brand.get("apollo_contact_id")
            }
    
    try:
        # Search for people at domain
        results = await client.search_people(domain=domain or brand_key)
        
        if not results:
            return {"success": False, "error": "No contacts found"}
        
        # Filter for target titles
        target = _filter_target_title(results)
        
        if not target:
            return {"success": False, "error": "No target titles found"}
        
        # Bulk match for emails
        enriched = await client.bulk_match([target])
        
        return {
            "success": True,
            "cached": False,
            "contact_email": enriched.get("email"),
            "contact_first_name": enriched.get("first_name"),
            "contact_last_name": enriched.get("last_name"),
            "contact_title": enriched.get("title"),
            "apollo_contact_id": enriched.get("id"),
            "apollo_score": enriched.get("score")
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}

def _filter_target_title(results: List[Dict]) -> Optional[Dict]:
    TARGET_TITLES = ["CEO", "Founder", "Owner", "President", "CMO"]
    for person in results:
        title = person.get("title", "").upper()
        if any(t in title for t in TARGET_TITLES):
            return person
    return results[0] if results else None
```

**Input Schema (`ApolloEnrichInput`):**
```python
class ApolloEnrichInput(BaseModel):
    brand_key: str = Field(description="Brand key to enrich")
    domain: Optional[str] = Field(default=None, description="Brand domain override")
    force_refresh: bool = Field(default=False, description="Bypass cache")
```

**Output Schema:**
```python
class ApolloEnrichOutput(BaseModel):
    success: bool
    cached: bool = False
    contact_email: Optional[str] = None
    contact_first_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    contact_title: Optional[str] = None
    apollo_contact_id: Optional[str] = None
    apollo_score: Optional[float] = None
    error: Optional[str] = None
```

**Used By:** `OutreachAgent` (Outreach Subgraph)

**Latency Target:** 3-8s

**Retry Policy:** 5 retries with jitter backoff

**Example Invocation:**
```python
result = await apollo_enrich_tool.ainvoke({
    "brand_key": "hydromax",
    "domain": "hydromax.com",
    "force_refresh": False
})
```

---

### 3.3 `email_draft_tool`

**Description:** Generate a personalized 5-step cold email sequence.

**Function Signature:**
```python
@tool(args_schema=EmailDraftInput)
async def email_draft_tool(
    brand_key: str,
    anchor_asin: Optional[str] = None,
    worst_axis: Optional[str] = None,
    competitor_context: Optional[str] = None
) -> Dict[str, Any]:
    """Generate personalized 5-step cold email sequence."""
    from acquisition_tool.cold_email import ColdEmailGenerator
    from acquisition_tool.rufus_scorer import RufusScorer
    
    generator = ColdEmailGenerator()
    scorer = RufusScorer()
    store = _get_data_store()
    
    # Fetch brand data
    brand = store.listings.get(brand_key, {})
    
    # Determine anchor ASIN
    if not anchor_asin:
        anchor_asin = brand.get("anchor_asin", brand_key)
    
    # Get Rufus scores if not provided
    if not worst_axis:
        scores = await scorer.score_async(anchor_asin)
        worst_axis = _identify_worst_axis(scores)
    
    # Get competitor context if not provided
    if not competitor_context:
        competitors = store.competitors.get(anchor_asin, [])
        competitor_context = _format_competitor_context(competitors)
    
    # Generate sequence
    sequence = await generator.generate(
        brand_key=brand_key,
        anchor_asin=anchor_asin,
        worst_axis=worst_axis,
        competitor_context=competitor_context,
        brand_data=brand
    )
    
    # Validate
    validation = _validate_sequence(sequence)
    
    return {
        "success": validation["status"] != "FAIL",
        "steps": sequence,
        "validation": validation,
        "worst_axis": worst_axis,
        "brand_key": brand_key
    }

def _identify_worst_axis(scores: Dict) -> str:
    AXIS_NAMES = [
        "intent_alignment",
        "attribute_density", 
        "conversational_readability",
        "qa_coverage",
        "visual_structured_content",
        "competitive_relativity"
    ]
    return min(AXIS_NAMES, key=lambda a: scores.get(f"{a}_score", 100))

def _validate_sequence(sequence: List[Dict]) -> Dict:
    from acquisition_tool.dynamic_rule_engine import RuleEngine
    engine = RuleEngine()
    
    checks = []
    for i, step in enumerate(sequence):
        # Check banned phrases
        banned = engine.check_banned_phrases(step["body"])
        if banned:
            checks.append({"step": i+1, "check": "banned_phrases", "status": "FAIL", "details": banned})
        
        # Check word count
        word_count = len(step["body"].split())
        target = [120, 75, 90, 35, 65][i]  # Targets per step
        if abs(word_count - target) / target > 0.2:
            checks.append({"step": i+1, "check": "word_count", "status": "WARNING", "actual": word_count, "target": target})
    
    # Check 5-gram overlap
    overlap = engine.check_5gram_overlap([s["body"] for s in sequence])
    if overlap > 0.25:
        checks.append({"check": "5gram_overlap", "status": "FAIL", "overlap": overlap})
    
    status = "FAIL" if any(c["status"] == "FAIL" for c in checks) else \
             "WARNING" if any(c["status"] == "WARNING" for c in checks) else "PASS"
    
    return {"status": status, "checks": checks}
```

**Input Schema (`EmailDraftInput`):**
```python
class EmailDraftInput(BaseModel):
    brand_key: str = Field(description="Brand key to draft for")
    anchor_asin: Optional[str] = Field(default=None, description="ASIN to base teardown on")
    worst_axis: Optional[str] = Field(
        default=None,
        description="Worst-performing Rufus axis (auto-detected if omitted)"
    )
    competitor_context: Optional[str] = Field(
        default=None,
        description="Competitor data to inject (auto-fetched if omitted)"
    )
```

**Output Schema:**
```python
class EmailStep(BaseModel):
    step: int = Field(ge=1, le=5)
    subject: str
    body: str
    timing: str  # "Day 0", "Day 3", "Day 7", "Day 12", "Day 18"
    word_count: int
    shopper_queries: int

class EmailDraftOutput(BaseModel):
    success: bool
    steps: List[EmailStep]
    validation: Dict  # { status: PASS|WARNING|FAIL, checks: [...] }
    worst_axis: str
    brand_key: str
    error: Optional[str] = None
```

**Used By:** `OutreachAgent` (Outreach Subgraph)

**Latency Target:** 5-10s

**Retry Policy:** 2 retries (regenerate on validation fail)

**Example Invocation:**
```python
result = await email_draft_tool.ainvoke({
    "brand_key": "hydromax",
    "anchor_asin": "B08N5WRWNW",
    "worst_axis": "qa_coverage"
})
```

---

## 4. Data Tools

### 4.1 `store_read_tool`

**Description:** Read entities from the shared in-memory data store.

**Function Signature:**
```python
@tool(args_schema=StoreReadInput)
async def store_read_tool(
    key: str,
    id: Optional[str] = None
) -> Dict[str, Any]:
    """Read entities from the shared in-memory data store."""
    store = _get_data_store()
    
    data: Dict[str, Any] = {}
    if key == "listings":
        data = store.listings.get(id, {}) if id else dict(store.listings)
    elif key == "competitors":
        data = store.competitors.get(id, []) if id else dict(store.competitors)
    elif key == "clients":
        data = [c for c in store.clients if not id or c.get("id") == id]
    elif key == "jobs":
        data = store.jobs
    elif key == "traffic_history":
        data = store.traffic_history.get(id, []) if id else dict(store.traffic_history)
    else:
        return {"key": key, "id": id, "data": None, "error": f"Unknown key: {key}"}
    
    return {"key": key, "id": id, "data": data, "count": len(data) if isinstance(data, (list, dict)) else 1}
```

**Input Schema (`StoreReadInput`):**
```python
class StoreReadInput(BaseModel):
    key: str = Field(
        description="Entity type: listings | competitors | clients | jobs | traffic_history"
    )
    id: Optional[str] = Field(default=None, description="Optional entity ID (e.g., ASIN)")
```

**Output Schema:**
```python
class StoreReadOutput(BaseModel):
    key: str
    id: Optional[str]
    data: Optional[Any]
    count: int = 0
    error: Optional[str] = None
```

**Used By:** All agents (Listing, Competitor, Attribution, Outreach, Email, Admin)

**Latency Target:** <50ms

**Example Invocation:**
```python
# Read single listing
result = await store_read_tool.ainvoke({"key": "listings", "id": "B08N5WRWNW"})

# Read all competitors for ASIN
result = await store_read_tool.ainvoke({"key": "competitors", "id": "B08N5WRWNW"})

# Read all active jobs
result = await store_read_tool.ainvoke({"key": "jobs"})
```

---

### 4.2 `store_write_tool`

**Description:** Write entities to the shared in-memory data store.

**Function Signature:**
```python
@tool(args_schema=StoreWriteInput)
async def store_write_tool(
    key: str,
    id: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Write entities to the shared in-memory data store."""
    store = _get_data_store()
    
    try:
        if key == "listings":
            store.set_listing(id, data)
        elif key == "competitors":
            store.set_competitors(id, data)
        elif key == "clients":
            store.update_client(id, data)
        elif key == "jobs":
            store.add_job(data)
        elif key == "traffic_history":
            store.set_traffic_history(id, data)
        else:
            return {"success": False, "error": f"Unknown key: {key}"}
        
        return {"success": True, "key": key, "id": id}
    except Exception as exc:
        return {"success": False, "key": key, "id": id, "error": str(exc)}
```

**Input Schema (`StoreWriteInput`):**
```python
class StoreWriteInput(BaseModel):
    key: str = Field(description="Entity type: listings | competitors | clients | jobs | traffic_history")
    id: str = Field(description="Entity ID")
    data: Dict[str, Any] = Field(description="Entity data to write")
```

**Output Schema:**
```python
class StoreWriteOutput(BaseModel):
    success: bool
    key: str
    id: str
    error: Optional[str] = None
```

**Used By:** `ListingAgent` (persist optimized copy), `OutreachAgent` (update brand stage), `AdminCopilotAgent`

**Latency Target:** <100ms

**Example Invocation:**
```python
result = await store_write_tool.ainvoke({
    "key": "listings",
    "id": "B08N5WRWNW",
    "data": {
        "optimized_title": "HydroMax 32oz Insulated Bottle...",
        "optimized_bullets": [...],
        "cosmo_score": 78,
        "optimized_at": "2026-05-30T11:35:57Z"
    }
})
```

---

### 4.3 `supabase_query_tool`

**Description:** Execute a read-only Supabase query.

**Function Signature:**
```python
@tool(args_schema=SupabaseQueryInput)
async def supabase_query_tool(
    table: str,
    select: str = "*",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    order_by: Optional[str] = None,
    order: str = "desc"
) -> Dict[str, Any]:
    """Execute read-only Supabase query."""
    from backend.core.supabase import get_supabase
    
    supabase = get_supabase()
    
    # Build query
    query = supabase.table(table).select(select)
    
    if filters:
        for column, value in filters.items():
            if isinstance(value, dict):  # Range filter
                query = query.gte(column, value["gte"]).lte(column, value["lte"])
            elif isinstance(value, list):  # In filter
                query = query.in_(column, value)
            else:  # Equality filter
                query = query.eq(column, value)
    
    if order_by:
        query = query.order(order_by, desc=(order == "desc"))
    
    query = query.limit(limit)
    
    try:
        response = await query.execute()
        return {
            "success": True,
            "table": table,
            "data": response.data,
            "count": len(response.data)
        }
    except Exception as exc:
        return {"success": False, "table": table, "error": str(exc)}
```

**Input Schema (`SupabaseQueryInput`):**
```python
class SupabaseQueryInput(BaseModel):
    table: str = Field(description="Supabase table name")
    select: str = Field(default="*", description="Columns to select")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Column filters")
    limit: int = Field(default=50, ge=1, le=1000)
    order_by: Optional[str] = Field(default=None)
    order: str = Field(default="desc", pattern=r"^(asc|desc)$")
```

**Used By:** `AdminCopilotAgent`, `EmailAgent` (conversation history)

**Latency Target:** <500ms

**Example Invocation:**
```python
# Get all REPLIED brands
result = await supabase_query_tool.ainvoke({
    "table": "brands",
    "select": "brand_key, stage, contact_email, intent_score",
    "filters": {"stage": "REPLIED"},
    "limit": 50,
    "order_by": "updated_at"
})

# Get conversation thread
result = await supabase_query_tool.ainvoke({
    "table": "email_conversations",
    "filters": {"brand_key": "hydromax"},
    "order_by": "created_at",
    "order": "asc"
})
```

---

## 5. Communication Tools

### 5.1 `classify_email_tool`

**Description:** Classify an inbound email reply into one of 8 categories.

**Function Signature:**
```python
@tool(args_schema=ClassifyEmailInput)
async def classify_email_tool(
    reply_body: str,
    subject: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """Classify inbound email reply intent."""
    from backend.email_integration.conversation_classifier import ConversationClassifier
    
    classifier = ConversationClassifier()
    
    result = await classifier.classify(
        reply_body=reply_body,
        subject=subject or "",
        conversation_history=conversation_history or []
    )
    
    return {
        "category": result["category"],
        "confidence": result["confidence"],
        "reason": result["reason"],
        "suggested_action": result["suggested_action"],
        "strategy": _map_category_to_strategy(result["category"])
    }

def _map_category_to_strategy(category: str) -> str:
    MAPPING = {
        "INTERESTED": "qualify_and_demo",
        "OBJECTION": "acknowledge_reframe",
        "NOT_NOW": "nurture_14_day",
        "BOOKING_READY": "send_calendly",
        "UNSUBSCRIBE": "graceful_exit",
        "WRONG_PERSON": "ask_referral",
        "COMPETITOR": "minimal_response",
        "NOISE": "ignore"
    }
    return MAPPING.get(category, "acknowledge_reframe")
```

**Input Schema (`ClassifyEmailInput`):**
```python
class ClassifyEmailInput(BaseModel):
    reply_body: str = Field(description="Inbound email body text")
    subject: Optional[str] = Field(default=None, description="Email subject line")
    conversation_history: Optional[List[Dict]] = Field(
        default=None,
        description="Previous messages in thread"
    )
```

**Output Schema:**
```python
class ClassifyEmailOutput(BaseModel):
    category: str = Field(pattern=r"^(INTERESTED|OBJECTION|NOT_NOW|BOOKING_READY|UNSUBSCRIBE|WRONG_PERSON|COMPETITOR|NOISE)$")
    confidence: float = Field(ge=0, le=1)
    reason: str
    suggested_action: str
    strategy: str = Field(pattern=r"^(qualify_and_demo|acknowledge_reframe|nurture_14_day|send_calendly|graceful_exit|ask_referral|minimal_response|ignore)$")
```

**Used By:** `EmailAgent` (Email Subgraph)

**Latency Target:** 1-3s

**Example Invocation:**
```python
result = await classify_email_tool.ainvoke({
    "reply_body": "This looks interesting. Can we schedule a call next week?",
    "subject": "Re: Your Amazon listing teardown",
    "conversation_history": [
        {"direction": "outbound", "body": "..."}
    ]
})
# Returns: { category: "BOOKING_READY", confidence: 0.92, strategy: "send_calendly" }
```

---

### 5.2 `draft_reply_tool`

**Description:** Draft a contextual reply to an inbound email.

**Function Signature:**
```python
@tool(args_schema=DraftReplyInput)
async def draft_reply_tool(
    brand_key: str,
    classification_category: str,
    strategy: str,
    conversation_history: List[Dict],
    brand_context: Optional[Dict] = None
) -> Dict[str, Any]:
    """Draft contextual email reply using selected strategy."""
    from backend.email_integration.conversation_drafter import ConversationDrafter
    
    drafter = ConversationDrafter()
    
    # Fetch brand context if not provided
    if not brand_context:
        store = _get_data_store()
        brand_context = store.listings.get(brand_key, {})
    
    draft = await drafter.draft(
        brand_key=brand_key,
        classification=classification_category,
        strategy=strategy,
        conversation_history=conversation_history,
        brand_context=brand_context
    )
    
    # Compliance check
    from acquisition_tool.dynamic_rule_engine import RuleEngine
    engine = RuleEngine()
    compliance = engine.check_compliance(draft["body"])
    
    return {
        "subject": draft["subject"],
        "body": draft["body"],
        "strategy": strategy,
        "compliance": compliance,
        "brand_key": brand_key
    }
```

**Input Schema (`DraftReplyInput`):**
```python
class DraftReplyInput(BaseModel):
    brand_key: str = Field(description="Brand key")
    classification_category: str = Field(description="Classification category")
    strategy: str = Field(description="Strategy playbook name")
    conversation_history: List[Dict] = Field(description="Thread history")
    brand_context: Optional[Dict] = Field(default=None, description="Brand data override")
```

**Output Schema:**
```python
class DraftReplyOutput(BaseModel):
    subject: str
    body: str
    strategy: str
    compliance: Dict  # { status: PASS|FAIL, violations: [...] }
    brand_key: str
```

**Used By:** `EmailAgent` (Email Subgraph)

**Latency Target:** 2-5s

**Example Invocation:**
```python
result = await draft_reply_tool.ainvoke({
    "brand_key": "hydromax",
    "classification_category": "BOOKING_READY",
    "strategy": "send_calendly",
    "conversation_history": [
        {"direction": "outbound", "body": "..."},
        {"direction": "inbound", "body": "Can we schedule a call?"}
    ]
})
```

---

## 6. Admin Tools

### 6.1 `get_dashboard_metrics_tool`

**Description:** Fetch aggregate dashboard metrics for a time period.

**Function Signature:**
```python
@tool(args_schema=DashboardMetricsInput)
async def get_dashboard_metrics_tool(
    period: str = "today"
) -> Dict[str, Any]:
    """Fetch dashboard KPIs aggregated by period."""
    from backend.data.store import get_store
    from backend.core.supabase import get_supabase
    
    store = get_store()
    supabase = get_supabase()
    
    # Determine date range
    now = datetime.utcnow()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        return {"error": f"Invalid period: {period}"}
    
    # Aggregate from Supabase
    pipeline_result = await supabase.table("brands") \
        .select("stage, count(*)") \
        .gte("updated_at", start.isoformat()) \
        .group("stage") \
        .execute()
    
    stage_counts = {r["stage"]: r["count"] for r in pipeline_result.data}
    
    # Calculate funnel conversion
    total_enriched = stage_counts.get("CONTACT_ENRICHED", 0)
    total_sequenced = stage_counts.get("SEQUENCED", 0)
    total_replied = stage_counts.get("REPLIED", 0)
    total_demoed = stage_counts.get("DEMO_SCHEDULED", 0)
    
    funnel = {
        "enriched_to_sequenced": total_sequenced / total_enriched if total_enriched else 0,
        "sequenced_to_replied": total_replied / total_sequenced if total_sequenced else 0,
        "replied_to_demo": total_demoed / total_replied if total_replied else 0
    }
    
    # Average CQS
    cqs_result = await supabase.table("brands") \
        .select("client_quality_score") \
        .not_.is_("client_quality_score", "null") \
        .execute()
    
    avg_cqs = sum(r["client_quality_score"] for r in cqs_result.data) / len(cqs_result.data) if cqs_result.data else 0
    
    return {
        "period": period,
        "stage_counts": stage_counts,
        "funnel_conversion": funnel,
        "avg_cqs": round(avg_cqs, 2),
        "total_brands": sum(stage_counts.values()),
        "timestamp": now.isoformat()
    }
```

**Input Schema (`DashboardMetricsInput`):**
```python
class DashboardMetricsInput(BaseModel):
    period: str = Field(default="today", pattern=r"^(today|week|month)$")
```

**Output Schema:**
```python
class DashboardMetricsOutput(BaseModel):
    period: str
    stage_counts: Dict[str, int]
    funnel_conversion: Dict[str, float]
    avg_cqs: float
    total_brands: int
    timestamp: str
```

**Used By:** `AdminCopilotAgent` (Admin Subgraph)

**Latency Target:** <500ms

**Example Invocation:**
```python
result = await get_dashboard_metrics_tool.ainvoke({"period": "week"})
# Returns:
# {
#   period: "week",
#   stage_counts: { CONTACT_ENRICHED: 45, SEQUENCED: 30, REPLIED: 12, DEMO_SCHEDULED: 3 },
#   funnel_conversion: { enriched_to_sequenced: 0.67, sequenced_to_replied: 0.40, replied_to_demo: 0.25 },
#   avg_cqs: 72.4,
#   total_brands: 156
# }
```

---

### 6.2 `list_prospects_tool`

**Description:** List prospects filtered by stage, score, or date.

**Function Signature:**
```python
@tool(args_schema=ListProspectsInput)
async def list_prospects_tool(
    stage: Optional[str] = None,
    limit: int = 50,
    sort_by: str = "created_at",
    order: str = "desc"
) -> Dict[str, Any]:
    """List prospects with filtering and sorting."""
    supabase = get_supabase()
    
    query = supabase.table("brands").select(
        "brand_key, brand_name, stage, contact_email, "
        "contact_first_name, contact_last_name, intent_score, "
        "client_quality_score, reachability_index, updated_at"
    )
    
    if stage:
        query = query.eq("stage", stage)
    
    query = query.order(sort_by, desc=(order == "desc")).limit(limit)
    
    response = await query.execute()
    
    return {
        "prospects": response.data,
        "total": len(response.data),
        "filters": {"stage": stage, "limit": limit, "sort_by": sort_by, "order": order}
    }
```

**Input Schema (`ListProspectsInput`):**
```python
class ListProspectsInput(BaseModel):
    stage: Optional[str] = Field(default=None, description="Filter by pipeline stage")
    limit: int = Field(default=50, ge=1, le=200)
    sort_by: str = Field(default="created_at", pattern=r"^(created_at|score|reachability|updated_at)$")
    order: str = Field(default="desc", pattern=r"^(asc|desc)$")
```

**Output Schema:**
```python
class ProspectSummary(BaseModel):
    brand_key: str
    brand_name: str
    stage: str
    contact_email: Optional[str]
    contact_first_name: Optional[str]
    contact_last_name: Optional[str]
    intent_score: Optional[float]
    client_quality_score: Optional[float]
    reachability_index: Optional[float]
    updated_at: str

class ListProspectsOutput(BaseModel):
    prospects: List[ProspectSummary]
    total: int
    filters: Dict[str, Any]
```

**Used By:** `AdminCopilotAgent` (Admin Subgraph)

**Latency Target:** <1s

**Example Invocation:**
```python
result = await list_prospects_tool.ainvoke({
    "stage": "REPLIED",
    "limit": 20,
    "sort_by": "reachability",
    "order": "desc"
})
```

---

### 6.3 `update_prospect_stage_tool`

**Description:** Advance or modify a prospect's pipeline stage.

**Function Signature:**
```python
@tool(args_schema=UpdateStageInput)
async def update_prospect_stage_tool(
    brand_key: str,
    new_stage: str,
    reason: str = ""
) -> Dict[str, Any]:
    """Update prospect pipeline stage with validation and audit logging."""
    from acquisition_tool.models import STAGES
    from backend.agent.db_logger import AgentRunLogger
    
    # Validate stage
    if new_stage not in STAGES:
        return {
            "success": False,
            "error": f"Invalid stage: {new_stage}. Must be one of: {STAGES}"
        }
    
    supabase = get_supabase()
    logger = AgentRunLogger()
    
    # Fetch current stage
    current = await supabase.table("brands").select("stage").eq("brand_key", brand_key).single().execute()
    previous_stage = current.data.get("stage") if current.data else None
    
    # Validate transition
    if previous_stage and new_stage == previous_stage:
        return {"success": False, "error": "New stage is same as current stage"}
    
    # Update
    try:
        await supabase.table("brands").update({
            "stage": new_stage,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("brand_key", brand_key).execute()
        
        # Log to audit
        audit_id = await logger.log_audit({
            "actor": "omni.admin",
            "action": "STAGE_CHANGE",
            "resource_type": "brand",
            "resource_id": brand_key,
            "before_state": {"stage": previous_stage},
            "after_state": {"stage": new_stage},
            "reason": reason
        })
        
        return {
            "success": True,
            "brand_key": brand_key,
            "previous_stage": previous_stage,
            "new_stage": new_stage,
            "audit_log_id": audit_id
        }
    except Exception as exc:
        return {"success": False, "brand_key": brand_key, "error": str(exc)}
```

**Input Schema (`UpdateStageInput`):**
```python
class UpdateStageInput(BaseModel):
    brand_key: str = Field(description="Brand key to update")
    new_stage: str = Field(description="Target pipeline stage")
    reason: str = Field(default="", description="Reason for stage change")
```

**Output Schema:**
```python
class UpdateStageOutput(BaseModel):
    success: bool
    brand_key: str
    previous_stage: Optional[str]
    new_stage: str
    audit_log_id: Optional[str]
    error: Optional[str] = None
```

**Used By:** `AdminCopilotAgent` (Admin Subgraph)

**HITL Required:** Yes (for destructive stages: SKIP, PAID)

**Latency Target:** <500ms

**Example Invocation:**
```python
result = await update_prospect_stage_tool.ainvoke({
    "brand_key": "hydromax",
    "new_stage": "DEMO_SCHEDULED",
    "reason": "Calendly meeting booked via webhook"
})
```

---

## 7. Tool Registry Summary

| Tool Name | Category | Agents | HITL? | Destructive? | Latency |
|-----------|----------|--------|-------|--------------|---------|
| `cosmo_analysis_tool` | ANALYSIS | Listing | No | No | 2-5s |
| `competitor_intel_tool` | ANALYSIS | Competitor | No | No | 3-10s |
| `attribution_tool` | ANALYSIS | Attribution | No | No | 5-10s |
| `pipeline_trigger_tool` | PIPELINE | Outreach, Admin | Yes (sequence) | Yes | 2-8s |
| `apollo_enrich_tool` | PIPELINE | Outreach | No | No | 3-8s |
| `email_draft_tool` | PIPELINE | Outreach | No | No | 5-10s |
| `store_read_tool` | DATA | All | No | No | <50ms |
| `store_write_tool` | DATA | Listing, Outreach, Admin | No | Yes | <100ms |
| `supabase_query_tool` | DATA | Admin, Email | No | No | <500ms |
| `classify_email_tool` | COMMUNICATION | Email | No | No | 1-3s |
| `draft_reply_tool` | COMMUNICATION | Email | No | No | 2-5s |
| `get_dashboard_metrics_tool` | ADMIN | Admin | No | No | <500ms |
| `list_prospects_tool` | ADMIN | Admin | No | No | <1s |
| `update_prospect_stage_tool` | ADMIN | Admin | Yes (destructive) | Yes | <500ms |

---

## 8. Implementation Files

| File | Tools Defined | Status |
|------|-------------|--------|
| `backend/agent/graph/tools.py` | `cosmo_analysis_tool`, `competitor_intel_tool`, `attribution_tool`, `store_read_tool`, `pipeline_trigger_tool` | ✅ Implemented |
| `backend/agent/graph/subgraphs.py` | Tool invocations within subgraph nodes | ✅ Implemented |
| `backend/email_integration/conversation_classifier.py` | `classify_email_tool` | ✅ Existing |
| `backend/email_integration/conversation_drafter.py` | `draft_reply_tool` | ✅ Existing |
| `backend/routers/admin.py` | `get_dashboard_metrics_tool`, `list_prospects_tool`, `update_prospect_stage_tool` | ✅ Existing |
| `backend/agent/db_logger.py` | Audit logging | ✅ Existing |
| `acquisition_tool/cold_email.py` | `email_draft_tool` | ✅ Existing |
| `acquisition_tool/apollo_api.py` | `apollo_enrich_tool` | ✅ Existing |
| `backend/data/store.py` | `store_read_tool`, `store_write_tool` | ✅ Existing |
| `backend/core/supabase.py` | `supabase_query_tool` | 🔲 Pending |
