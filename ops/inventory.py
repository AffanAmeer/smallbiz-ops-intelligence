"""Reorder recommendations and slow-moving stock.

For each product, using the last `lookback_days` of sales:

    avg daily demand  = total units sold / lookback_days   (days with no sales count as 0)
    demand std dev    = how much daily sales jump around
    safety stock      = z x demand std dev x sqrt(lead time)
                        z comes from the service level (95% -> z = 1.645). It is extra
                        stock to cover days when demand is higher than average while
                        waiting for a delivery.
    reorder point     = avg daily demand x lead time + safety stock
                        "When stock falls to this level, place an order."
    days of cover     = on hand / avg daily demand
                        "How many days the current stock will last."
    suggested order   = (avg daily demand x (lead time + review period) + safety stock) - on hand
                        Enough to get back up to a target level that lasts until the next
                        review, rounded up to whole units, never below 0.

Status rules (checked in this order):
    "No recent sales"  -> nothing sold in the lookback window but stock is on hand
    "Reorder now"      -> on hand <= reorder point
    "Slow mover"       -> days of cover > slow_mover_days (cash tied up on the shelf)
    "OK"               -> everything else
"""

import math
from statistics import NormalDist

import pandas as pd


def daily_demand_matrix(sales: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    """Rows = each day in the lookback window, columns = products, values = units sold (0 if none)."""
    end = sales["date"].max()
    start = end - pd.Timedelta(days=lookback_days - 1)
    recent = sales[sales["date"] >= start]
    matrix = recent.pivot_table(index="date", columns="product", values="units_sold", aggfunc="sum")
    all_days = pd.date_range(start, end, freq="D")
    return matrix.reindex(all_days).fillna(0)


def reorder_report(
    sales: pd.DataFrame,
    inventory: pd.DataFrame,
    lookback_days: int = 28,
    service_level: float = 0.95,
    review_period_days: int = 3,
    slow_mover_days: int = 45,
) -> pd.DataFrame:
    if not 0.5 <= service_level < 1:
        raise ValueError("service_level must be between 0.5 and 0.99.")

    z = NormalDist().inv_cdf(service_level)
    demand = daily_demand_matrix(sales, lookback_days)

    rows = []
    for item in inventory.itertuples(index=False):
        history = demand[item.product] if item.product in demand.columns else pd.Series(0.0, index=demand.index)
        avg = history.mean()
        std = history.std(ddof=0)
        safety_stock = z * std * math.sqrt(item.lead_time_days)
        reorder_point = avg * item.lead_time_days + safety_stock
        target_level = avg * (item.lead_time_days + review_period_days) + safety_stock
        days_of_cover = item.on_hand / avg if avg > 0 else math.inf

        if avg == 0 and item.on_hand > 0:
            status = "No recent sales"
        elif item.on_hand <= reorder_point:
            status = "Reorder now"
        elif days_of_cover > slow_mover_days:
            status = "Slow mover"
        else:
            status = "OK"

        suggested = max(0, math.ceil(target_level - item.on_hand)) if status == "Reorder now" else 0

        rows.append({
            "product": item.product,
            "category": item.category,
            "status": status,
            "on_hand": item.on_hand,
            "avg_daily_demand": round(avg, 2),
            "demand_std": round(std, 2),
            "lead_time_days": item.lead_time_days,
            "safety_stock": round(safety_stock, 1),
            "reorder_point": round(reorder_point, 1),
            "days_of_cover": round(days_of_cover, 1) if math.isfinite(days_of_cover) else None,
            "suggested_order_qty": suggested,
            "stock_value": round(item.on_hand * item.unit_cost, 2),
        })

    status_order = {"Reorder now": 0, "No recent sales": 1, "Slow mover": 2, "OK": 3}
    report = pd.DataFrame(rows)
    report["_sort"] = report["status"].map(status_order)
    return report.sort_values(["_sort", "product"]).drop(columns="_sort").reset_index(drop=True)
