import pytest

from ops import database
from ops import waste as waste_mod


def test_waste_by_product(sales, waste, inventory):
    by_product = waste_mod.waste_by_product(sales, waste, inventory).set_index("product")
    widget = by_product.loc["Widget"]
    assert widget["units_wasted"] == 6
    assert widget["waste_cost"] == pytest.approx(18)
    # Widget sold 360 units, wasted 6 -> 6 / 366
    assert widget["waste_rate_pct"] == pytest.approx(6 / 366 * 100)
    assert by_product["share_of_waste_cost_pct"].sum() == pytest.approx(100)


def test_waste_by_reason_is_a_pareto(waste, inventory):
    by_reason = waste_mod.waste_by_reason(waste, inventory)
    # Expired: 4 Widget ($12) + 1 Gadget ($6) = $18; Damaged: 2 Widget = $6
    assert list(by_reason["reason"]) == ["Expired", "Damaged"]
    assert by_reason["cumulative_pct"].iloc[-1] == pytest.approx(100)


def test_waste_by_weekday_counts_days_without_waste(waste, inventory):
    by_weekday = waste_mod.waste_by_weekday(waste, inventory).set_index("weekday")
    # Mondays in range: Jun 1 ($12) and Jun 8 ($6) -> average $9
    assert by_weekday.loc["Monday", "avg_waste_cost"] == pytest.approx(9)


def test_insights_are_plain_sentences(sales, waste, inventory):
    insights = waste_mod.waste_insights(
        waste_mod.waste_by_product(sales, waste, inventory),
        waste_mod.waste_by_weekday(waste, inventory),
        waste_mod.waste_by_reason(waste, inventory),
    )
    assert any("Monday" in line for line in insights)
    assert any("Expired" in line for line in insights)


def test_database_round_trip(tmp_path, sales):
    db = tmp_path / "test.db"
    assert database.load_dataset("sales", db) is None
    database.save_dataset(sales, "sales", db)
    loaded = database.load_dataset("sales", db)
    assert len(loaded) == len(sales)
    assert loaded["date"].min() == sales["date"].min()


def test_sql_explorer_is_read_only(tmp_path, sales):
    db = tmp_path / "test.db"
    database.save_dataset(sales, "sales", db)
    assert database.run_query("SELECT COUNT(*) AS n FROM sales", db)["n"].item() == len(sales)
    with pytest.raises(ValueError):
        database.run_query("DELETE FROM sales", db)
