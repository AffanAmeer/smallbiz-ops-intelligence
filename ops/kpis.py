"""Headline business numbers (KPIs) for the overview page.

Definitions used everywhere in the app:
    revenue        = units_sold x unit_price
    cost of goods  = units_sold x unit_cost (from inventory)
    gross margin % = (revenue - cost of goods) / revenue
                     (only products that have a cost in inventory are included)
    waste rate %   = units_wasted / (units_sold + units_wasted)
    waste cost     = units_wasted x unit_cost
"""

import pandas as pd

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def add_revenue(sales: pd.DataFrame) -> pd.DataFrame:
    sales = sales.copy()
    sales["revenue"] = sales["units_sold"] * sales["unit_price"]
    return sales


def _safe_pct(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator * 100


def _window_metrics(sales, inventory, waste, start, end) -> dict:
    """KPIs for dates start..end (inclusive)."""
    s = add_revenue(sales[(sales["date"] >= start) & (sales["date"] <= end)])
    days = (end - start).days + 1

    costed = s.merge(inventory[["product", "unit_cost"]], on="product", how="inner")
    costed_revenue = costed["revenue"].sum()
    cogs = (costed["units_sold"] * costed["unit_cost"]).sum()

    units_sold = int(s["units_sold"].sum())
    metrics = {
        "revenue": float(s["revenue"].sum()),
        "units_sold": units_sold,
        "avg_daily_revenue": float(s["revenue"].sum()) / days,
        "gross_margin_pct": _safe_pct(float(costed_revenue - cogs), float(costed_revenue)),
        "waste_rate_pct": None,
        "waste_cost": None,
    }

    if waste is not None:
        w = waste[(waste["date"] >= start) & (waste["date"] <= end)]
        units_wasted = int(w["units_wasted"].sum())
        metrics["waste_rate_pct"] = _safe_pct(units_wasted, units_sold + units_wasted)
        w_costed = w.merge(inventory[["product", "unit_cost"]], on="product", how="inner")
        metrics["waste_cost"] = float((w_costed["units_wasted"] * w_costed["unit_cost"]).sum())
    return metrics


def summary_kpis(sales, inventory, waste=None, window_days: int = 28) -> dict:
    """Compare the most recent `window_days` with the window just before it.

    Returns {"current": {...}, "previous": {...} or None, "change_pct": {...},
             "current_start": date, "current_end": date}
    """
    end = sales["date"].max()
    start = end - pd.Timedelta(days=window_days - 1)
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=window_days - 1)

    current = _window_metrics(sales, inventory, waste, start, end)
    has_previous = sales["date"].min() <= prev_start
    previous = _window_metrics(sales, inventory, waste, prev_start, prev_end) if has_previous else None

    change = {}
    for key, value in current.items():
        old = previous.get(key) if previous else None
        if value is None or old is None:
            change[key] = None
        elif key.endswith("_pct"):
            change[key] = value - old  # percentage points, not % of a %
        else:
            change[key] = _safe_pct(value - old, old)

    return {"current": current, "previous": previous, "change_pct": change,
            "current_start": start, "current_end": end}


def daily_revenue(sales: pd.DataFrame) -> pd.DataFrame:
    """Revenue per day (days with no sales count as 0) plus a 7-day rolling average."""
    s = add_revenue(sales)
    daily = s.groupby("date")["revenue"].sum()
    all_days = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(all_days, fill_value=0).rename_axis("date").reset_index()
    daily["rolling_7d"] = daily["revenue"].rolling(7, min_periods=1).mean()
    return daily


def product_performance(sales: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    """Revenue, units and gross margin per product, best sellers first."""
    s = add_revenue(sales).merge(inventory[["product", "unit_cost"]], on="product", how="left")
    s["gross_profit"] = s["revenue"] - s["units_sold"] * s["unit_cost"]
    out = (
        s.groupby(["product", "category"], as_index=False)
        .agg(units_sold=("units_sold", "sum"), revenue=("revenue", "sum"),
             gross_profit=("gross_profit", lambda x: x.sum(min_count=1)))
    )
    out["gross_margin_pct"] = out["gross_profit"] / out["revenue"] * 100
    out["revenue_share_pct"] = out["revenue"] / out["revenue"].sum() * 100
    return out.sort_values("revenue", ascending=False).reset_index(drop=True)


def weekday_profile(sales: pd.DataFrame) -> pd.DataFrame:
    """Average revenue for each day of the week."""
    daily = daily_revenue(sales)
    daily["weekday"] = daily["date"].dt.day_name()
    out = daily.groupby("weekday", as_index=False)["revenue"].mean()
    out["weekday"] = pd.Categorical(out["weekday"], categories=WEEKDAYS, ordered=True)
    return out.sort_values("weekday").rename(columns={"revenue": "avg_revenue"}).reset_index(drop=True)
