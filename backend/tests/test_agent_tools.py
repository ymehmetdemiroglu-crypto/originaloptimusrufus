import sys
from pathlib import Path

# Add backend to sys.path so tests can run cleanly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Add acquisition-tool to sys.path
acq_path = Path(__file__).resolve().parent.parent.parent / "acquisition-tool"

# To prevent import collision between backend/models.py and acquisition-tool/models.py,
# we temporarily delete 'models' from sys.modules, import reply_classifier, and restore it.
original_models = sys.modules.get("models")
if "models" in sys.modules:
    del sys.modules["models"]

original_sys_path = sys.path.copy()
sys.path.insert(0, str(acq_path))

try:
    import reply_classifier
finally:
    # Restore models and path
    if original_models:
        sys.modules["models"] = original_models
    else:
        if "models" in sys.modules:
            del sys.modules["models"]
    sys.path = original_sys_path

import pytest
from unittest.mock import MagicMock, patch

from agent.graph.tools import (
    supabase_query_tool,
    classify_email_tool,
    draft_reply_tool,
    get_dashboard_metrics_tool,
    list_prospects_tool,
    update_prospect_stage_tool,
)


@pytest.fixture
def mock_supabase_client():
    mock_client = MagicMock()
    mock_builder = MagicMock()

    mock_client.table.return_value = mock_builder
    mock_builder.select.return_value = mock_builder
    mock_builder.insert.return_value = mock_builder
    mock_builder.update.return_value = mock_builder
    mock_builder.eq.return_value = mock_builder
    mock_builder.limit.return_value = mock_builder
    mock_builder.order.return_value = mock_builder

    mock_builder.execute.return_value = MagicMock(data=[{"id": "test_id", "asin": "B08N5WRWNW", "stage": "LISTING_FOUND"}])
    return mock_client


@patch("core.supabase.get_supabase")
def test_supabase_query_tool_whitelisting(mock_get_sb, mock_supabase_client):
    mock_get_sb.return_value = mock_supabase_client

    # Querying non-whitelisted table should fail
    res = supabase_query_tool.invoke({"table": "users", "action": "select"})
    assert res["success"] is False
    assert "not whitelisted" in res["error"]

    # Querying whitelisted table should succeed
    res = supabase_query_tool.invoke({"table": "prospects", "action": "select"})
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["asin"] == "B08N5WRWNW"


@patch("core.supabase.get_supabase")
def test_supabase_query_tool_operations(mock_get_sb, mock_supabase_client):
    mock_get_sb.return_value = mock_supabase_client

    # Select with params
    res = supabase_query_tool.invoke({"table": "prospects", "action": "select", "query_params": {"asin": "B08N5WRWNW"}})
    assert res["success"] is True
    mock_supabase_client.table.assert_called_with("prospects")

    # Insert
    res = supabase_query_tool.invoke({"table": "agent_runs", "action": "insert", "data": {"run_type": "scrape", "status": "running"}})
    assert res["success"] is True

    # Update
    res = supabase_query_tool.invoke({"table": "prospects", "action": "update", "query_params": {"asin": "B08N5WRWNW"}, "data": {"stage": "WEAK_LISTING"}})
    assert res["success"] is True


@patch("reply_classifier.classify_reply")
def test_classify_email_tool(mock_classify):
    mock_classify.return_value = {
        "category": "BOOKING_READY",
        "confidence": 0.95,
        "reason": "Wants to book a call",
        "suggested_action": "Send booking link",
    }

    res = classify_email_tool.invoke({"reply_text": "I would love to jump on a call next Tuesday"})
    assert res["success"] is True
    assert res["classification"]["category"] == "BOOKING_READY"
    assert res["classification"]["confidence"] == 0.95


@patch("openai.resources.chat.completions.Completions.create")
def test_draft_reply_tool(mock_openai_create):
    mock_openai_create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Here is a Hormozi objection handling reply"))]
    )

    res = draft_reply_tool.invoke({
        "brand_key": "test_brand",
        "reply_text": "Is this free?",
        "category": "OBJECTION"
    })
    assert res["success"] is True
    assert "Hormozi" in res["draft"]


@patch("core.supabase.get_supabase")
def test_get_dashboard_metrics_tool(mock_get_sb, mock_supabase_client):
    mock_get_sb.return_value = mock_supabase_client

    res = get_dashboard_metrics_tool.invoke({})
    assert res["success"] is True
    assert "metrics" in res
    assert res["metrics"]["active_listings"] == 988   # sum of seeded listing counts
    assert res["metrics"]["jobs_count"] == 4          # seeded jobs count


@patch("core.supabase.get_supabase")
def test_list_prospects_tool(mock_get_sb, mock_supabase_client):
    mock_get_sb.return_value = mock_supabase_client

    res = list_prospects_tool.invoke({"stage": "LISTING_FOUND", "limit": 10})
    assert res["success"] is True
    assert "prospects" in res
    assert len(res["prospects"]) == 1


@patch("core.supabase.get_supabase")
def test_update_prospect_stage_tool(mock_get_sb, mock_supabase_client):
    mock_get_sb.return_value = mock_supabase_client

    res = update_prospect_stage_tool.invoke({"identifier": "B08N5WRWNW", "stage": "CONTACT_ENRICHED"})
    assert res["success"] is True
    assert res["memory_updated"] is True
    assert res["supabase_updated"] is True
