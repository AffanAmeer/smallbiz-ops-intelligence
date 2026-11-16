import math

import pytest

from ops.inventory import reorder_report


def row(report, product):
    return report.set_index("product").loc[product]


def test_reorder_point_formula(sales, inventory):
    report = reorder_report(sales, inventory, lookback_days=28, service_level=0.95)
    widget = row(report, "Widget")
    # Widget: 20 units x 8 weekend days + 10 x 20 weekdays = 360 over 28 days
    avg = 360 / 28
    assert widget["avg_daily_demand"] == pytest.approx(avg, abs=0.01)
    expected_rop = avg * 2 + 1.645 * widget["demand_std"] * math.sqrt(2)
    assert widget["reorder_point"] == pytest.approx(expected_rop, abs=0.2)


def test_low_stock_is_flagged_with_an_order_quantity(sales, inventory):
    widget = row(reorder_report(sales, inventory), "Widget")
    assert widget["status"] == "Reorder now"  # 20 on hand < ~31 reorder point
    assert widget["suggested_order_qty"] > 0


def test_steady_seller_with_lots_of_stock_is_slow_mover(sales, inventory):
    gadget = row(reorder_report(sales, inventory, slow_mover_days=45), "Gadget")
    # Gadget sells exactly 2/day with no variation -> safety stock 0, cover = 200 / 2 = 100 days
    assert gadget["safety_stock"] == 0
    assert gadget["days_of_cover"] == 100
    assert gadget["status"] == "Slow mover"
    assert gadget["suggested_order_qty"] == 0


def test_item_with_no_sales_is_flagged(sales, inventory):
    doohickey = row(reorder_report(sales, inventory), "Doohickey")
    assert doohickey["status"] == "No recent sales"
    assert doohickey["days_of_cover"] is None or math.isnan(doohickey["days_of_cover"])


def test_reorder_items_are_listed_first(sales, inventory):
    report = reorder_report(sales, inventory)
    assert report.iloc[0]["status"] == "Reorder now"


def test_higher_service_level_means_more_safety_stock(sales, inventory):
    low = row(reorder_report(sales, inventory, service_level=0.80), "Widget")["safety_stock"]
    high = row(reorder_report(sales, inventory, service_level=0.99), "Widget")["safety_stock"]
    assert high > low


def test_invalid_service_level_raises(sales, inventory):
    with pytest.raises(ValueError):
        reorder_report(sales, inventory, service_level=1.5)
