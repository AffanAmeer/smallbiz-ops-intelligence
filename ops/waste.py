"""Where waste happens and what it costs.

    waste rate %  = units_wasted / (units_sold + units_wasted)
                    "Out of everything that left the shelf, what share went in the bin?"
    waste cost    = units_wasted x unit_cost  (what the business paid for it)

The reason breakdown is a Pareto view: reasons sorted from biggest to
smallest with a running total, because usually one or two causes explain
most of the problem.
"""

import pandas as pd

from ops.kpis import WEEKDAYS


def _with_cost(waste: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    w = waste.merge(inventory[["product", "unit_cost"]], on="product", how="left")
    w["waste_cost"] = w["units_wasted"] * w["unit_cost"]
    return w


def waste_by_product(sales: pd.DataFrame, waste: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    """Units wasted, waste rate and waste cost per product, most costly first."""
    w = _with_cost(waste, inventory).groupby("product", as_index=False).agg(
        units_wasted=("units_wasted", "sum"),
        waste_cost=("waste_cost", lambda x: x.sum(min_count=1)),
    )
    sold = sales.groupby("product", as_index=False)["units_sold"].sum()
    out = w.merge(sold, on="product", how="left").fillna({"units_sold": 0})
    out["waste_rate_pct"] = out["units_wasted"] / (out["units_sold"] + out["units_wasted"]) * 100
    total_cost = out["waste_cost"].sum()
    out["share_of_waste_cost_pct"] = out["waste_cost"] / total_cost * 100 if total_cost else 0.0
    return out.sort_values("waste_cost", ascending=False).reset_index(drop=True)


def waste_by_weekday(waste: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    """Average waste cost per calendar day, for each day of the week."""
    w = _with_cost(waste, inventory)
    daily = w.groupby("date")["waste_cost"].sum()
    all_days = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(all_days, fill_value=0).rename_axis("date").reset_index()
    daily["weekday"] = daily["date"].dt.day_name()
    out = daily.groupby("weekday", as_index=False)["waste_cost"].mean()
    out["weekday"] = pd.Categorical(out["weekday"], categories=WEEKDAYS, ordered=True)
    return out.sort_values("weekday").rename(columns={"waste_cost": "avg_waste_cost"}).reset_index(drop=True)


def waste_by_reason(waste: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    """Pareto table of waste reasons."""
    w = _with_cost(waste, inventory)
    out = w.groupby("reason", as_index=False).agg(
        units_wasted=("units_wasted", "sum"), waste_cost=("waste_cost", "sum")
    ).sort_values("waste_cost", ascending=False)
    out["share_pct"] = out["waste_cost"] / out["waste_cost"].sum() * 100
    out["cumulative_pct"] = out["share_pct"].cumsum()
    return out.reset_index(drop=True)


def waste_insights(by_product: pd.DataFrame, by_weekday: pd.DataFrame, by_reason: pd.DataFrame) -> list[str]:
    """Plain-English findings generated from the tables above."""
    insights = []
    if by_product.empty:
        return ["No waste recorded."]

    top3 = by_product.head(3)
    insights.append(
        f"{len(top3)} products ({', '.join(top3['product'])}) cause "
        f"{top3['share_of_waste_cost_pct'].sum():.0f}% of waste cost."
    )

    worst_rate = by_product.sort_values("waste_rate_pct", ascending=False).iloc[0]
    insights.append(
        f"{worst_rate['product']} has the highest waste rate: {worst_rate['waste_rate_pct']:.1f}% of units "
        "were thrown out. Consider ordering smaller batches more often."
    )

    if not by_weekday.empty and by_weekday["avg_waste_cost"].mean() > 0:
        peak = by_weekday.sort_values("avg_waste_cost", ascending=False).iloc[0]
        ratio = peak["avg_waste_cost"] / by_weekday["avg_waste_cost"].mean()
        insights.append(
            f"{peak['weekday']} is the most wasteful day, at {ratio:.1f}x the average daily waste cost."
        )

    if not by_reason.empty:
        top = by_reason.iloc[0]
        insights.append(f"'{top['reason']}' is the top reason, at {top['share_pct']:.0f}% of waste cost.")
    return insights
