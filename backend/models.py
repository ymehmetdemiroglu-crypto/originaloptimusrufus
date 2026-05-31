from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ListingInput(BaseModel):
    asin: str

class RelationCoverage(BaseModel):
    relation: str
    cluster: str
    detected_signals: List[str]
    confidence_score: float
    coverage_grade: str

class SafetyCheck(BaseModel):
    label: str
    status: str
    detail: str

class ListingAnalysisResponse(BaseModel):
    asin: str
    title: str
    overall_score: int
    keyword_safety: str
    embedding_dimensions: int
    relations: List[RelationCoverage]
    safety_checks: List[SafetyCheck]

class CompetitorProfile(BaseModel):
    asin: str
    title: str
    similarity: float
    price: Optional[str]
    rating: Optional[str]
    review_count: Optional[int]

class GapOpportunity(BaseModel):
    gap_id: str
    description: str
    competitors_covering: List[str]
    client_coverage_score: float
    opportunity_score: float
    suggested_content: str
    keyword_safety_rating: str
    estimated_traffic_impact: str
    lexical_safety_report: Optional[Dict[str, Any]] = None

class CompetitorAnalysisResponse(BaseModel):
    asin: str
    competitor_profiles: List[CompetitorProfile]
    gap_opportunities: List[GapOpportunity]
    positioning_summary: Dict[str, Any]

class JobStatus(BaseModel):
    id: str
    asin: str
    client: str
    stage: str
    status: str
    progress: int
    started: str
    eta: Optional[str]
    readiness_before: int
    readiness_after: Optional[int]
    date: str

class PipelineResponse(BaseModel):
    running: int
    queued: int
    completed: int
    failed: int
    jobs: List[JobStatus]

class Client(BaseModel):
    id: str
    name: str
    tier: str
    listings: int
    asins: int
    usage: int
    mrr: int
    status: str
    last_active: str

class OverviewMetrics(BaseModel):
    cosmo_readiness_score: int
    grade: str
    active_listings: int
    avg_competitor_similarity: float
    optimization_jobs_7d: int
    readiness_trend: List[Dict[str, Any]]
    cluster_breakdown: List[Dict[str, Any]]
    recent_jobs: List[Dict[str, Any]]
    gap_alerts: List[Dict[str, Any]]
    competitor_similarity: List[Dict[str, Any]]

class QASeedInput(BaseModel):
    asin: str
    target_relations: Optional[List[str]] = None

class QASeedResponse(BaseModel):
    asin: str
    seeds: List[dict]

class AttributionInput(BaseModel):
    treatment_asin: str
    control_asin: str
    days: int = 14

class AttributionResponse(BaseModel):
    treatment_asin: str
    control_asin: str
    metrics: dict
    time_series: List[dict]

