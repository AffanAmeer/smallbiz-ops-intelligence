import pandas as pd
import pytest

from ops import forecast


def weekly_pattern(weeks=8):
    """10 units on weekdays, 20 on weekends, starting on a Monday."""
    days = pd.date_range("2026-06-01", periods=weeks * 7, freq="D")
    return pd.Series([20.0 if d.dayofweek >= 5 else 10.0 for d in days], index=days)


def test_daily_units_fills_zero_days(sales):
    sparse = sales[(sales["product"] == "Gadget") & (sales["date"].dt.day % 2 == 0)]
    combined = pd.concat([sales[sales["product"] == "Widget"], sparse])
    series = forecast.daily_units(combined, "Gadget")
    assert len(series) == 28
    assert (series == 0).sum() == 14


def test_unknown_product_raises(sales):
    with pytest.raises(ValueError):
        forecast.daily_units(sales, "Nope")


def test_forecast_repeats_the_weekly_pattern():
    series = weekly_pattern()
    result = forecast.same_weekday_forecast(series, horizon_days=7)
    assert len(result) == 7
    weekend = result[result["date"].dt.dayofweek >= 5]["forecast"]
    weekday = result[result["date"].dt.dayofweek < 5]["forecast"]
    assert (weekend == 20).all() and (weekday == 10).all()


def test_forecast_starts_the_day_after_history_ends():
    series = weekly_pattern()
    result = forecast.same_weekday_forecast(series)
    assert result["date"].iloc[0] == series.index[-1] + pd.Timedelta(days=1)


def test_backtest_is_perfect_on_a_perfect_pattern_and_beats_baseline():
    bt = forecast.backtest(weekly_pattern(), test_days=28)
    assert bt["mae"] == 0
    assert bt["wape_pct"] == 0
    assert bt["baseline_mae"] > 0  # a flat 7-day average can't follow the weekend spikes


def test_backtest_only_uses_past_data():
    series = weekly_pattern()
    series.iloc[-1] = 1000  # a huge spike on the very last day
    bt = forecast.backtest(series, test_days=28)
    # The forecast for that last day must not have "seen" the spike.
    assert bt["results"]["forecast"].iloc[-1] == 20


def test_not_enough_history_gives_clear_error():
    with pytest.raises(ValueError, match="Need at least"):
        forecast.backtest(weekly_pattern(weeks=5), test_days=28)
