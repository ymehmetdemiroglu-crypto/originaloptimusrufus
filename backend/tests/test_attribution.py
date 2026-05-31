"""Comprehensive Unit and Property-Based Tests for Causal Attribution Model."""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings
from analysis.attribution import attribution_model

def test_did_calculation_isolated():
    """Verify Difference-in-Differences causal mathematical logic with standard inputs."""
    res = attribution_model.calculate_did_lift(
        treatment_pre_sessions=2000,
        treatment_pre_orders=100,      # 5.0%
        treatment_post_sessions=2000,
        treatment_post_orders=160,     # 8.0%
        control_pre_sessions=2000,
        control_pre_orders=100,        # 5.0%
        control_post_sessions=2000,
        control_post_orders=100        # 5.0%
    )
    
    assert res["treatment_pre_conversion_rate"] == 0.05
    assert res["treatment_post_conversion_rate"] == 0.08
    assert res["control_pre_conversion_rate"] == 0.05
    assert res["control_post_conversion_rate"] == 0.05
    assert res["attributed_causal_lift"] == 0.03
    assert res["is_statistically_significant"] is True
    assert res["z_score"] > 2.0

def test_scm_lift_calculation():
    """Verify Synthetic Control Method weight optimization and counterfactual CR construction."""
    t_history = []
    donor_a = []
    donor_b = []
    
    for d in range(1, 21):
        dt = f"2026-05-{d:02d}"
        is_post = d > 10
        t_cr = 0.065 if is_post else 0.045
        t_history.append({"date": dt, "sessions": 1000, "orders": int(1000 * t_cr)})
        donor_a.append({"date": dt, "sessions": 1000, "orders": int(1000 * 0.035)})
        donor_b.append({"date": dt, "sessions": 1000, "orders": int(1000 * 0.055)})
        
    donor_histories = {
        "DONOR-A": donor_a,
        "DONOR-B": donor_b
    }
    
    res = attribution_model.calculate_synthetic_control_lift(
        treatment_history=t_history,
        donor_histories=donor_histories,
        intervention_date="2026-05-11"
    )
    
    # Assertions
    assert abs(res["attributed_causal_lift"] - 0.02) < 1e-3
    assert abs(sum(res["donor_weights"].values()) - 1.0) < 1e-4
    assert res["pre_fit_rmsd"] < 1e-3

# Setup property-based testing configuration (keep iterations bounded for speed)
@settings(max_examples=50, deadline=1000)
@given(
    treatment_sessions=st.integers(min_value=500, max_value=5000),
    control_sessions=st.integers(min_value=500, max_value=5000),
    treatment_pre_orders=st.integers(min_value=10, max_value=200),
    treatment_post_orders=st.integers(min_value=10, max_value=200),
    control_pre_orders=st.integers(min_value=10, max_value=200),
    control_post_orders=st.integers(min_value=10, max_value=200),
)
def test_did_lift_math_invariants(
    treatment_sessions,
    control_sessions,
    treatment_pre_orders,
    treatment_post_orders,
    control_pre_orders,
    control_post_orders
):
    """Enforce mathematical boundaries and check invariants over wide input domains using property-based checks."""
    t_pre_o = min(treatment_pre_orders, treatment_sessions)
    t_post_o = min(treatment_post_orders, treatment_sessions)
    c_pre_o = min(control_pre_orders, control_sessions)
    c_post_o = min(control_post_orders, control_sessions)

    res = attribution_model.calculate_did_lift(
        treatment_pre_sessions=treatment_sessions,
        treatment_pre_orders=t_pre_o,
        treatment_post_sessions=treatment_sessions,
        treatment_post_orders=t_post_o,
        control_pre_sessions=control_sessions,
        control_pre_orders=c_pre_o,
        control_post_sessions=control_sessions,
        control_post_orders=c_post_o
    )

    # Invariants
    assert 0.0 <= res["treatment_pre_conversion_rate"] <= 1.0
    assert 0.0 <= res["treatment_post_conversion_rate"] <= 1.0
    assert 0.0 <= res["control_pre_conversion_rate"] <= 1.0
    assert 0.0 <= res["control_post_conversion_rate"] <= 1.0
    assert -1.0 <= res["attributed_causal_lift"] <= 1.0
    assert 0.0 <= res["p_value"] <= 1.0
