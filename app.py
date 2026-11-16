"""Streamlit dashboard: Small Business Operations Intelligence.

Run with:  streamlit run app.py

This file only handles the screen. All calculations live in the ops/ package
so they can be tested on their own (see tests/).
"""

from pathlib import Path
from statistics import NormalDist

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ops import database, forecast, inventory, kpis, waste
from ops.schemas import SCHEMAS
from ops.validation import check_consistency, validate

SAMPLE_DIR = Path(__file__).resolve().parent / "data" / "sample"
STATUS_COLORS = {"Reorder now": "#d62728", "No recent sales": "#7f7f7f", "Slow mover": "#ff7f0e", "OK": "#2ca02c"}

st.set_page_config(page_title="Ops Intelligence", page_icon="📦", layout="wide")


# ---------------------------------------------------------------------------
# Loading data
# ---------------------------------------------------------------------------
def load_and_store(frames: dict[str, pd.DataFrame]) -> dict:
    """Validate each table; if all pass, save to SQLite and read back from it."""
    results = {name: validate(df, name) for name, df in frames.items()}
    if not all(r.ok for r in results.values()):
        return {"ok": False, "results": results}
    for name, result in results.items():
        database.save_dataset(result.data, name)
    data = {name: database.load_dataset(name) for name in frames}
    return {"ok": True, "results": results, "data": data}


def sidebar() -> dict | None:
    st.sidebar.title("📦 Ops Intelligence")
    source = st.sidebar.radio("Data source", ["Simulated sample data", "Upload my own CSVs"])

    if source == "Simulated sample data":
        if st.session_state.get("loaded_source") != "sample":
            frames = {name: pd.read_csv(SAMPLE_DIR / f"{name}.csv") for name in SCHEMAS}
            st.session_state["load"] = load_and_store(frames)
            st.session_state["loaded_source"] = "sample"
    else:
        st.sidebar.caption("Column formats are listed on the **Data & SQL** tab. Waste is optional.")
        uploads = {
            "sales": st.sidebar.file_uploader("sales.csv", type="csv"),
            "inventory": st.sidebar.file_uploader("inventory.csv", type="csv"),
            "waste": st.sidebar.file_uploader("waste.csv (optional)", type="csv"),
        }
        if st.sidebar.button("Validate and load", type="primary"):
            if not uploads["sales"] or not uploads["inventory"]:
                st.sidebar.error("Please upload at least sales.csv and inventory.csv.")
            else:
                frames = {}
                for name, file in uploads.items():
                    if file is None:
                        continue
                    try:
                        frames[name] = pd.read_csv(file)
                    except Exception as exc:  # unreadable file: report it instead of crashing
                        st.sidebar.error(f"Could not read {name}.csv as a CSV file: {exc}")
                        return None
                st.session_state["load"] = load_and_store(frames)
                st.session_state["loaded_source"] = "upload"
        if st.session_state.get("loaded_source") != "upload":
            st.info("Upload your CSV files in the sidebar and press **Validate and load**.")
            return None

    st.sidebar.divider()
    st.sidebar.subheader("Settings")
    settings = {
        "lookback_days": st.sidebar.slider("Days of history for averages", 14, 90, 28, step=7),
        "service_level": st.sidebar.slider("Target service level", 0.80, 0.99, 0.95, step=0.01,
                                           help="Chance of not running out while waiting for a delivery."),
        "review_period_days": st.sidebar.slider("Days between orders", 1, 14, 3),
        "slow_mover_days": st.sidebar.slider("Slow mover if stock lasts more than (days)", 20, 120, 45, step=5),
    }
    return {**st.session_state["load"], "source": st.session_state["loaded_source"], "settings": settings}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def fmt_money(x):
    return "n/a" if x is None else f"${x:,.0f}"


def fmt_pct(x):
    return "n/a" if x is None else f"{x:.1f}%"


def fmt_delta(x, points=False):
    if x is None:
        return None
    return f"{x:+.1f} pts" if points else f"{x:+.1f}%"


def page_overview(sales, inv, wst, settings):
    summary = kpis.summary_kpis(sales, inv, wst, window_days=settings["lookback_days"])
    cur, chg = summary["current"], summary["change_pct"]
    st.caption(
        f"Last {settings['lookback_days']} days ({summary['current_start']:%b %d} to {summary['current_end']:%b %d, %Y}), "
        "compared with the same number of days before that."
    )

    cols = st.columns(6)
    cols[0].metric("Revenue", fmt_money(cur["revenue"]), fmt_delta(chg["revenue"]))
    cols[1].metric("Avg revenue / day", fmt_money(cur["avg_daily_revenue"]), fmt_delta(chg["avg_daily_revenue"]))
    cols[2].metric("Units sold", f"{cur['units_sold']:,}", fmt_delta(chg["units_sold"]))
    cols[3].metric("Gross margin", fmt_pct(cur["gross_margin_pct"]), fmt_delta(chg["gross_margin_pct"], True))
    cols[4].metric("Waste rate", fmt_pct(cur["waste_rate_pct"]), fmt_delta(chg["waste_rate_pct"], True),
                   delta_color="inverse")
    cols[5].metric("Waste cost", fmt_money(cur["waste_cost"]), fmt_delta(chg["waste_cost"]), delta_color="inverse")

    daily = kpis.daily_revenue(sales)
    fig = go.Figure()
    fig.add_bar(x=daily["date"], y=daily["revenue"], name="Daily revenue", marker_color="#c6dbef")
    fig.add_scatter(x=daily["date"], y=daily["rolling_7d"], name="7-day average", line=dict(color="#08519c", width=3))
    fig.update_layout(title="Revenue over time", height=380, yaxis_title="Revenue ($)", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    perf = kpis.product_performance(sales, inv)
    fig = px.bar(perf.head(10).sort_values("revenue"), x="revenue", y="product", color="category", orientation="h",
                 title="Top 10 products by revenue", labels={"revenue": "Revenue ($)", "product": ""})
    left.plotly_chart(fig, use_container_width=True)

    wd = kpis.weekday_profile(sales)
    fig = px.bar(wd, x="weekday", y="avg_revenue", title="Average revenue by day of week",
                 labels={"avg_revenue": "Avg revenue ($)", "weekday": ""})
    right.plotly_chart(fig, use_container_width=True)

    with st.expander("How these numbers are calculated"):
        st.markdown(
            "- **Revenue** = units sold × unit price.\n"
            "- **Gross margin** = (revenue − units sold × unit cost) ÷ revenue. Only products with a cost in inventory count.\n"
            "- **Waste rate** = units wasted ÷ (units sold + units wasted).\n"
            "- **Waste cost** = units wasted × unit cost.\n"
            "- Changes in margin and waste rate are shown in percentage **points** (40% → 42% is +2 pts)."
        )


def page_inventory(sales, inv, settings):
    report = inventory.reorder_report(
        sales, inv,
        lookback_days=settings["lookback_days"],
        service_level=settings["service_level"],
        review_period_days=settings["review_period_days"],
        slow_mover_days=settings["slow_mover_days"],
    )
    counts = report["status"].value_counts()
    cols = st.columns(4)
    cols[0].metric("Reorder now", int(counts.get("Reorder now", 0)))
    cols[1].metric("Slow movers", int(counts.get("Slow mover", 0)))
    cols[2].metric("No recent sales", int(counts.get("No recent sales", 0)))
    tied_up = report.loc[report["status"].isin(["Slow mover", "No recent sales"]), "stock_value"].sum()
    cols[3].metric("Cash tied up in slow stock", fmt_money(tied_up))

    reorder = report[report["status"] == "Reorder now"]
    if not reorder.empty:
        st.subheader("🛒 Suggested order")
        st.dataframe(reorder[["product", "on_hand", "reorder_point", "days_of_cover", "lead_time_days",
                              "suggested_order_qty"]], hide_index=True, use_container_width=True)
        st.download_button("Download order list (CSV)", reorder.to_csv(index=False), "suggested_order.csv", "text/csv")

    chart = report.copy()
    chart["days_of_cover_capped"] = chart["days_of_cover"].fillna(999).clip(upper=120)
    fig = px.bar(chart.sort_values("days_of_cover_capped"), x="days_of_cover_capped", y="product", color="status",
                 color_discrete_map=STATUS_COLORS, orientation="h", height=520,
                 title="How many days will current stock last?",
                 labels={"days_of_cover_capped": "Days of cover (capped at 120)", "product": ""})
    fig.add_vline(x=settings["slow_mover_days"], line_dash="dash", annotation_text="slow mover threshold", annotation_position="bottom right")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("All products")
    st.dataframe(report, hide_index=True, use_container_width=True)

    with st.expander("How the reorder numbers are calculated"):
        st.markdown(
            f"Using the last **{settings['lookback_days']} days** of sales (days with no sales count as 0):\n\n"
            "- **Average daily demand** = units sold ÷ number of days.\n"
            f"- **Safety stock** = z × daily demand std dev × √lead time. At a {settings['service_level']:.0%} "
            "service level, z ≈ " f"{NormalDist().inv_cdf(settings['service_level']):.2f}. "
            "This is a cushion for busier-than-usual days while a delivery is on its way.\n"
            "- **Reorder point** = average daily demand × lead time + safety stock.\n"
            "- **Days of cover** = on hand ÷ average daily demand.\n"
            "- **Suggested order** = average daily demand × (lead time + days between orders) + safety stock − on hand.\n"
            f"- **Slow mover**: stock would last more than {settings['slow_mover_days']} days.\n\n"
            "Assumptions: demand is roughly steady, lead times are reliable, and sales equal demand "
            "(if an item sold out, real demand was higher than recorded)."
        )


def page_forecast(sales, settings):
    products = ["All products"] + sorted(sales["product"].unique())
    left, right = st.columns([2, 1])
    choice = left.selectbox("Product", products)
    horizon = right.slider("Days to forecast", 7, 28, 14)
    product = None if choice == "All products" else choice

    series = forecast.daily_units(sales, product)
    try:
        future = forecast.same_weekday_forecast(series, horizon_days=horizon)
        bt = forecast.backtest(series)
    except ValueError as exc:
        st.warning(str(exc))
        return

    recent = series.iloc[-56:]
    fig = go.Figure()
    fig.add_scatter(x=recent.index, y=recent.values, name="Actual units sold", line=dict(color="#4c78a8"))
    fig.add_scatter(x=future["date"], y=future["forecast"], name="Forecast", line=dict(color="#f58518", dash="dash"))
    fig.update_layout(title=f"Next {horizon} days: {choice}", height=380, yaxis_title="Units per day",
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("How accurate was it? (last 28 days, tested day by day)")
    cols = st.columns(4)
    cols[0].metric("Forecast error (MAE)", f"{bt['mae']:.1f} units/day")
    cols[1].metric("Baseline error (MAE)", f"{bt['baseline_mae']:.1f} units/day")
    cols[2].metric("Forecast WAPE", fmt_pct(bt["wape_pct"]))
    cols[3].metric("Baseline WAPE", fmt_pct(bt["baseline_wape_pct"]))

    if bt["mae"] < bt["baseline_mae"]:
        improvement = (1 - bt["mae"] / bt["baseline_mae"]) * 100
        st.success(f"The weekday method was {improvement:.0f}% more accurate than simply using last week's average.")
    else:
        st.warning("For this product the weekday method did not beat the simple baseline. Its sales probably "
                   "don't have a strong weekly pattern, so the simpler average is just as good.")
    if series.iloc[-28:].mean() < 2:
        st.info("This product sells fewer than 2 units a day, so percentage errors look large even when the "
                "forecast is off by less than one unit. Judge it by MAE instead.")

    res = bt["results"]
    fig = go.Figure()
    fig.add_scatter(x=res["date"], y=res["actual"], name="Actual", line=dict(color="#4c78a8", width=3))
    fig.add_scatter(x=res["date"], y=res["forecast"], name="Weekday forecast", line=dict(color="#f58518"))
    fig.add_scatter(x=res["date"], y=res["baseline"], name="Baseline (last 7 days)", line=dict(color="#bab0ac", dash="dot"))
    fig.update_layout(title="Backtest: forecast vs what actually happened", height=340, legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Method and limitations"):
        st.markdown(
            "**Method:** the forecast for a day is the average units sold on the same weekday over the last "
            "4 weeks (for example, next Saturday = average of the last 4 Saturdays).\n\n"
            "**Baseline:** the average of the previous 7 days. A forecast is only useful if it beats this.\n\n"
            "**MAE** is the average size of the miss in units. **WAPE** is total miss ÷ total actual units.\n\n"
            "**Limitations:**\n"
            "- It does not know about holidays, promotions, weather or local events.\n"
            "- It reacts slowly to sudden changes because it averages 4 weeks.\n"
            "- It treats past sales as past demand; stock-outs make it under-forecast.\n"
            "- It needs at least 4 weeks of history (8 weeks to run the accuracy test)."
        )


def page_waste(sales, inv, wst):
    if wst is None or wst.empty:
        st.info("No waste file loaded. Upload waste.csv to see this page.")
        return
    by_product = waste.waste_by_product(sales, wst, inv)
    by_weekday = waste.waste_by_weekday(wst, inv)
    by_reason = waste.waste_by_reason(wst, inv)

    st.subheader("Key findings")
    for line in waste.waste_insights(by_product, by_weekday, by_reason):
        st.markdown(f"- {line}")

    left, right = st.columns(2)
    fig = px.bar(by_product.head(10).sort_values("waste_cost"), x="waste_cost", y="product", orientation="h",
                 hover_data=["units_wasted", "waste_rate_pct"], title="Waste cost by product (top 10)",
                 labels={"waste_cost": "Waste cost ($)", "product": ""})
    left.plotly_chart(fig, use_container_width=True)

    fig = px.bar(by_weekday, x="weekday", y="avg_waste_cost", title="Average waste cost by day of week",
                 labels={"avg_waste_cost": "Avg waste cost ($)", "weekday": ""})
    right.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    fig.add_bar(x=by_reason["reason"], y=by_reason["waste_cost"], name="Waste cost ($)", marker_color="#e45756")
    fig.add_scatter(x=by_reason["reason"], y=by_reason["cumulative_pct"], name="Cumulative %", yaxis="y2",
                    line=dict(color="#333"))
    fig.update_layout(title="Why stock is wasted (Pareto)", height=360, legend=dict(orientation="h", y=1.12),
                      yaxis=dict(title="Waste cost ($)"),
                      yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105], ticksuffix="%", dtick=25))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(by_product.round(1), hide_index=True, use_container_width=True)


def page_data(data, results, source):
    st.subheader("Loaded datasets")
    cols = st.columns(len(data))
    for col, (name, df) in zip(cols, data.items()):
        col.metric(name, f"{len(df):,} rows")
        if "date" in df.columns:
            col.caption(f"{df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}")
        for warning in results[name].warnings:
            col.warning(warning)

    for warning in check_consistency(data["sales"], data["inventory"], data.get("waste")):
        st.warning(warning)

    st.subheader("SQL explorer")
    st.caption("The cleaned data is stored in a local SQLite database (ops.db). Try your own SELECT query.")
    sql = st.text_area("Query", "SELECT category, SUM(units_sold * unit_price) AS revenue\n"
                                "FROM sales\nGROUP BY category\nORDER BY revenue DESC;", height=120)
    if st.button("Run query"):
        try:
            st.dataframe(database.run_query(sql), hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(f"Query failed: {exc}")

    st.subheader("Expected CSV formats")
    for name, schema in SCHEMAS.items():
        st.markdown(f"**{name}.csv**: {schema['description']}")
        st.code(",".join(schema["columns"]), language="text")


def show_validation_errors(results):
    st.error("Some files have problems. Fix them and upload again. Nothing was saved.")
    for name, result in results.items():
        if result.errors:
            st.markdown(f"**{name}.csv**")
            for err in result.errors:
                st.markdown(f"- {err}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    state = sidebar()
    st.title("Small Business Operations Intelligence")
    if state is None:
        return
    if not state["ok"]:
        show_validation_errors(state["results"])
        return
    if state["source"] == "sample":
        st.info("**Simulated data.** \"Corner Market\" is a fictional grocery store. Every number on this page "
                "was generated by `scripts/generate_sample_data.py`, not taken from a real business.")

    data = state["data"]
    sales, inv, wst = data["sales"], data["inventory"], data.get("waste")
    settings = state["settings"]

    tabs = st.tabs(["Overview", "Inventory & reorder", "Demand forecast", "Waste", "Data & SQL"])
    with tabs[0]:
        page_overview(sales, inv, wst, settings)
    with tabs[1]:
        page_inventory(sales, inv, settings)
    with tabs[2]:
        page_forecast(sales, settings)
    with tabs[3]:
        page_waste(sales, inv, wst)
    with tabs[4]:
        page_data(data, state["results"], state["source"])


main()
