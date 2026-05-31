"""End-to-End Integration Test Suite for FastAPI Backend Routes."""

import pytest
from fastapi.testclient import TestClient
from main import app
from data.store import store

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_store():
    """Clear and pre-populate the in-memory data store for integration runs."""
    store.listings.clear()
    store.competitors.clear()
    store.jobs.clear()
    store.traffic_history.clear()
    store._seed()
    yield

def test_health_endpoint():
    """Validate that the health check endpoint returns 200 and indicates running status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "rufus-cosmos-optimization-engine"

def test_listings_workflow():
    """Validate full listing upsert and analysis workflow through API endpoints."""
    # 1. Upsert a new listing
    new_listing = {
        "asin": "B0INTEG001",
        "title": "Premium Stainless Hydration Bottle - Vacuum Flask",
        "bullets": ["Vacuum insulated all day cold.", "Eco-friendly BPA-free material."],
        "description": "Daily hydration cup.",
        "brand": "HydroTest",
        "client_id": "c-101"
    }
    
    response = client.post("/api/listings", json=new_listing)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Verify it is in store
    assert "B0INTEG001" in store.listings
    assert store.get_listing("B0INTEG001")["brand"] == "HydroTest"

    # 2. Analyze the newly upserted listing
    analysis_payload = {"asin": "B0INTEG001"}
    response = client.post("/api/analyze", json=analysis_payload)
    assert response.status_code == 200
    analysis_data = response.json()
    assert analysis_data["asin"] == "B0INTEG001"
    assert analysis_data["title"] == "Premium Stainless Hydration Bottle - Vacuum Flask"
    assert "overall_score" in analysis_data
    assert "relations" in analysis_data
    assert len(analysis_data["safety_checks"]) > 0

def test_causal_attribution_workflow():
    """Validate that the attribution analysis endpoint correctly calculates lift models."""
    payload = {
        "treatment_asin": "B08N5WRWNW",
        "control_asin": "B0ABC123",
        "days": 10
    }
    response = client.post("/api/attribution/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["treatment_asin"] == "B08N5WRWNW"
    assert data["control_asin"] == "B0ABC123"
    assert "metrics" in data
    assert "time_series" in data
    
    metrics = data["metrics"]
    assert "attributed_causal_lift" in metrics
    assert "scm_lift" in metrics
