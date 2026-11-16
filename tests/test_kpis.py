import pytest

from ops import kpis


def test_summary_kpis_current_window(sales, inventory, waste):
    result = kpis.summary_kpis(sales, inventory, waste, window_days=14)
    cur = result["current"]
    # Last 14 days = 2 weeks. Widget: 10 weekdays x 10 + 4 weekend days x 20 = 180 units ($900).
    # Gadget: 14 x 2 = 28 units ($280).
    assert cur["units_sold"] == 208
    assert cur["revenue"] == pytest.approx(1180)
    # Cost: 180 x 3 + 28 x 6 = 708 -> margin = (1180 - 708) / 1180
    assert cur["gross_margin_pct"] == pytest.approx((1180 - 708) / 1180 * 100)
    # No waste in the last 14 days of the fixture
    assert cur["waste_rate_pct"] == 0


def test_previous_window_and_change(sales, inventory, waste):
    result = kpis.summary_kpis(sales, inventory, waste, window_days=14)
    prev = result["previous"]
    # Previous 14 days have the same sales but 7 wasted units (6 Widget, 1 Gadget).
    assert prev["revenue"] == pytest.approx(1180)
    assert prev["waste_cost"] == pytest.approx(6 * 3 + 1 * 6)
    assert result["change_pct"]["revenue"] == pytest.approx(0)
    # Waste rate change is in percentage points
    assert result["change_pct"]["waste_rate_pct"] == pytest.approx(-7 / (208 + 7) * 100)


def test_no_previous_window_when_history_too_short(sales, inventory):
    result = kpis.summary_kpis(sales, inventory, None, window_days=28)
    assert result["previous"] is None
    assert result["change_pct"]["revenue"] is None


def test_daily_revenue_fills_missing_days(sales):
    gap = sales[sales["date"] != sales["date"].min() + __import__("pandas").Timedelta(days=3)]
    daily = kpis.daily_revenue(gap)
    assert len(daily) == 28
    assert (daily["revenue"] == 0).sum() == 1


def test_product_performance_ranks_by_revenue(sales, inventory):
    perf = kpis.product_performance(sales, inventory)
    assert perf.iloc[0]["product"] == "Widget"
    assert perf["revenue_share_pct"].sum() == pytest.approx(100)


def test_weekday_profile_is_in_calendar_order(sales):
    profile = kpis.weekday_profile(sales)
    assert list(profile["weekday"]) == kpis.WEEKDAYS
    assert profile.loc[profile["weekday"] == "Saturday", "avg_revenue"].item() == pytest.approx(120)
