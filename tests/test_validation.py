import pandas as pd

from ops.validation import check_consistency, validate


def good_sales_csv():
    return pd.DataFrame({
        "date": ["2026-06-01", "2026-06-01", "2026-06-02"],
        "product": ["Milk", "Bread", "Milk"],
        "category": ["Dairy", "Bakery", "Dairy"],
        "units_sold": ["5", "3", "4"],
        "unit_price": ["4.99", "3.50", "4.99"],
    })


def test_valid_file_passes_and_is_typed():
    result = validate(good_sales_csv(), "sales")
    assert result.ok
    assert pd.api.types.is_datetime64_any_dtype(result.data["date"])
    assert result.data["units_sold"].tolist() == [5, 3, 4]


def test_messy_headers_are_accepted():
    df = good_sales_csv().rename(columns={"units_sold": " Units Sold ", "unit_price": "Unit Price"})
    assert validate(df, "sales").ok


def test_missing_column_is_reported():
    result = validate(good_sales_csv().drop(columns="unit_price"), "sales")
    assert not result.ok
    assert "unit_price" in result.errors[0]


def test_extra_column_is_a_warning_not_an_error():
    df = good_sales_csv().assign(notes="hello")
    result = validate(df, "sales")
    assert result.ok
    assert "notes" in result.warnings[0]


def test_empty_file_is_rejected():
    df = good_sales_csv().iloc[0:0]
    assert not validate(df, "sales").ok


def test_error_messages_use_spreadsheet_row_numbers():
    df = good_sales_csv()
    df.loc[1, "units_sold"] = "abc"  # second data row = row 3 in Excel
    result = validate(df, "sales")
    assert not result.ok
    assert "units_sold" in result.errors[0] and "row 3" in result.errors[0]


def test_bad_values_are_each_reported():
    df = good_sales_csv()
    df.loc[0, "date"] = "2026-13-40"
    df.loc[1, "product"] = " "
    df.loc[2, "unit_price"] = "-1"
    errors = " ".join(validate(df, "sales").errors)
    assert "not valid dates" in errors
    assert "'product' is blank" in errors
    assert "negative" in errors


def test_decimal_units_are_rejected():
    df = good_sales_csv()
    df.loc[0, "units_sold"] = "2.5"
    assert "whole numbers" in " ".join(validate(df, "sales").errors)


def test_duplicate_product_on_same_day_is_rejected():
    df = pd.concat([good_sales_csv(), good_sales_csv().iloc[[0]]], ignore_index=True)
    result = validate(df, "sales")
    assert any("Duplicate" in e for e in result.errors)


def test_waste_allows_same_product_twice_a_day():
    df = pd.DataFrame({"date": ["2026-06-01"] * 2, "product": ["Milk"] * 2,
                       "units_wasted": [1, 2], "reason": ["Expired", "Damaged"]})
    assert validate(df, "waste").ok


def test_consistency_warns_about_products_missing_from_inventory(sales, inventory):
    warnings = check_consistency(sales, inventory[inventory["product"] != "Gadget"])
    assert len(warnings) == 1 and "Gadget" in warnings[0]


def test_sample_data_is_valid():
    from pathlib import Path
    sample = Path(__file__).resolve().parent.parent / "data" / "sample"
    for name in ["sales", "inventory", "waste"]:
        assert validate(pd.read_csv(sample / f"{name}.csv"), name).ok, name
    broken = validate(pd.read_csv(sample / "sales_with_errors.csv"), "sales")
    assert len(broken.errors) == 6
