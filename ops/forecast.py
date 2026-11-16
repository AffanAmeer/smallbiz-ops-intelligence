"""A simple demand forecast that anyone can check by hand.

Method: "same weekday average"
    Forecast for a future day = the average units sold on the same weekday
    over the last `weeks` weeks.
    Example: next Saturday's forecast = average of the last 4 Saturdays.

Why this method: small businesses usually have a strong weekly pattern
(busy weekends, quiet Mondays). This captures it, needs no extra libraries,
and the owner can verify any number with a calculator.

How we know if it is any good (backtest):
    We pretend we are standing at each of the last `test_days` days, forecast
    that day using only earlier data, and compare against what really happened.
    We do the same for a simpler baseline ("average of the last 7 days") so we
    can see whether the weekday method actually helps.

    MAE  = average size of the error, in units per day
    WAPE = total absolute error / total actual units. 10% means forecasts were
           off by 10% of actual volume overall. Unlike MAPE it does not blow up
           on days with zero sales.

Limitations (also shown in the app):
    - Does not know about holidays, promotions, weather or local events.
    - Reacts slowly to sudden changes (it averages 4 weeks).
    - Assumes past sales = past demand. If a product sold out, true demand
      was higher than recorded sales, so the forecast will be too low.
    - Needs at least `weeks` full weeks of history.
"""

import pandas as pd


def daily_units(sales: pd.DataFrame, product: str | None = None) -> pd.Series:
    """Units sold per day for one product (or all products), with 0 for days with no sales."""
    data = sales if product is None else sales[sales["product"] == product]
    if data.empty:
        raise ValueError(f"No sales found for product '{product}'.")
    series = data.groupby("date")["units_sold"].sum()
    all_days = pd.date_range(sales["date"].min(), sales["date"].max(), freq="D")
    return series.reindex(all_days, fill_value=0).astype(float).rename("units")


def _check_history(series: pd.Series, needed_days: int) -> None:
    if len(series) < needed_days:
        raise ValueError(
            f"Need at least {needed_days} days of history for this forecast, but only {len(series)} are available."
        )


def same_weekday_forecast(series: pd.Series, horizon_days: int = 14, weeks: int = 4) -> pd.DataFrame:
    """Forecast the next `horizon_days` days after the end of `series`."""
    _check_history(series, weeks * 7)
    history = series.iloc[-weeks * 7:]
    by_weekday = history.groupby(history.index.dayofweek).mean()

    future = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    return pd.DataFrame({"date": future, "forecast": [by_weekday[d.dayofweek] for d in future]})


def backtest(series: pd.Series, test_days: int = 28, weeks: int = 4) -> dict:
    """Walk-forward test of the weekday method against a last-7-day average baseline."""
    _check_history(series, weeks * 7 + test_days)

    rows = []
    for i in range(len(series) - test_days, len(series)):
        day = series.index[i]
        past = series.iloc[:i]  # only data available before this day
        same_weekday = past[past.index.dayofweek == day.dayofweek].iloc[-weeks:]
        rows.append({
            "date": day,
            "actual": series.iloc[i],
            "forecast": same_weekday.mean(),
            "baseline": past.iloc[-7:].mean(),
        })
    results = pd.DataFrame(rows)

    def mae(col):
        return (results[col] - results["actual"]).abs().mean()

    def wape(col):
        total = results["actual"].sum()
        return None if total == 0 else (results[col] - results["actual"]).abs().sum() / total * 100

    return {
        "results": results,
        "mae": mae("forecast"),
        "wape_pct": wape("forecast"),
        "baseline_mae": mae("baseline"),
        "baseline_wape_pct": wape("baseline"),
    }
