import sys
import pytest
from pathlib import Path

# Add backend directory to path so tests can run from anywhere
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

@pytest.fixture
def mock_asin_listing():
    return {
        "asin": "B0TEST0001",
        "title": "Standard Premium Commuter Hydration Bottle - Double-Wall Vacuum Insulated Water Flask",
        "bullets": [
            "ADVANCED TEMPERTURE CONTROL keeps coffee hot for 12 hours or water ice cold for 24 hours.",
            "PREMIUM BPA-FREE FOOD GRADE STAINLESS STEEL construction ensures clean taste and pure safety.",
            "LEAK-PROOF SPORT LID with carry handle makes daily travel and athletic gym routines effortless."
        ],
        "description": "Ergonomic, lightweight commuter bottle for healthy lifestyles.",
        "brand": "HydroMax",
        "client_id": "c-101"
    }

@pytest.fixture
def mock_traffic_history():
    t_history = []
    c_history = []
    for d in range(1, 21):
        dt = f"2026-05-{d:02d}"
        is_post = d > 10
        t_cr = 0.06 if is_post else 0.04
        c_cr = 0.04
        t_history.append({"date": dt, "sessions": 1000, "orders": int(1000 * t_cr)})
        c_history.append({"date": dt, "sessions": 1000, "orders": int(1000 * c_cr)})
    return t_history, c_history
