"""Small hand-made datasets shared by the tests.

They are tiny on purpose so every expected answer can be worked out by hand.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Let the tests import the ops package without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sales():
    # 28 days (4 full weeks starting on a Monday). "Widget" sells 10 on weekdays and 20 on weekends.
    # "Gadget" sells 2 every day.
    days = pd.date_range("2026-06-01", periods=28, freq="D")  # 2026-06-01 is a Monday
    rows = []
    for d in days:
        rows.append({"date": d, "product": "Widget", "category": "Tools",
                     "units_sold": 20 if d.dayofweek >= 5 else 10, "unit_price": 5.0})
        rows.append({"date": d, "product": "Gadget", "category": "Tools", "units_sold": 2, "unit_price": 10.0})
    return pd.DataFrame(rows)


@pytest.fixture
def inventory():
    return pd.DataFrame([
        {"product": "Widget", "category": "Tools", "on_hand": 20, "unit_cost": 3.0, "lead_time_days": 2},
        {"product": "Gadget", "category": "Tools", "on_hand": 200, "unit_cost": 6.0, "lead_time_days": 5},
        {"product": "Doohickey", "category": "Tools", "on_hand": 5, "unit_cost": 1.0, "lead_time_days": 3},
    ])


@pytest.fixture
def waste():
    return pd.DataFrame([
        {"date": pd.Timestamp("2026-06-01"), "product": "Widget", "units_wasted": 4, "reason": "Expired"},
        {"date": pd.Timestamp("2026-06-08"), "product": "Widget", "units_wasted": 2, "reason": "Damaged"},
        {"date": pd.Timestamp("2026-06-09"), "product": "Gadget", "units_wasted": 1, "reason": "Expired"},
    ])
