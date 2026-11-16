"""Create the SIMULATED sample data in data/sample/.

The business ("Corner Market") is fictional and every number is generated
with random noise around patterns we chose on purpose, so the dashboard has
something realistic to find:
    - busier Fridays and weekends, quieter Mondays and Tuesdays
    - a small summer lift for produce and cold drinks
    - perishable items (bread, produce, dairy, meat) produce more waste,
      with extra expiry waste on Mondays after weekend over-ordering
    - a few products deliberately low on stock (should trigger "Reorder now")
    - a few deliberately over-stocked (should show as "Slow mover")

Run:  python scripts/generate_sample_data.py
The output is the same every time because the random seed is fixed.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START, END = "2026-04-01", "2026-09-30"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

# Monday ... Sunday
WEEKDAY_FACTOR = [0.85, 0.80, 0.90, 1.00, 1.20, 1.35, 1.10]

# name, category, avg units/day, price, cost, lead time (days), daily waste rate, on_hand today
PRODUCTS = [
    ("Milk 2L",              "Dairy",     30.0, 5.49,  3.70, 2, 0.04,  45),   # low -> reorder
    ("Eggs (dozen)",         "Dairy",     18.0, 4.99,  3.20, 3, 0.02, 120),
    ("Greek Yogurt 750g",    "Dairy",      9.0, 6.49,  4.10, 3, 0.06,  20),   # low -> reorder
    ("Cheddar Block 400g",   "Dairy",      6.0, 7.99,  5.10, 5, 0.02,  70),
    ("Sourdough Loaf",       "Bakery",    14.0, 6.99,  3.40, 1, 0.12,  30),
    ("Bagels (6 pack)",      "Bakery",     8.0, 4.49,  2.10, 1, 0.10,  22),
    ("Bananas (bunch)",      "Produce",   20.0, 1.99,  0.95, 2, 0.09,  55),
    ("Spinach 312g",         "Produce",    7.0, 4.49,  2.60, 2, 0.15,  30),
    ("Gala Apples 3lb",      "Produce",    8.0, 5.99,  3.30, 4, 0.03,  60),
    ("Chicken Breast 1kg",   "Meat",       6.0, 14.99, 9.80, 3, 0.05,  14),   # low -> reorder
    ("Basmati Rice 2kg",     "Pantry",     4.0, 8.99,  5.40, 7, 0.00,  70),
    ("Pasta 900g",           "Pantry",     7.0, 2.99,  1.40, 7, 0.00,  90),
    ("Canned Tomatoes",      "Pantry",     6.0, 1.79,  0.85, 7, 0.01,  35),   # low -> reorder
    ("Orange Juice 1.5L",    "Beverages", 10.0, 5.29,  3.30, 3, 0.03,  60),
    ("Cold Brew Coffee",     "Beverages",  5.0, 4.99,  2.40, 5, 0.01,  40),
    ("Premium Olive Oil 1L", "Specialty",  0.6, 24.99, 15.50, 10, 0.00, 70),  # slow mover
    ("Gift Basket",          "Specialty",  0.15, 49.99, 31.00, 14, 0.00, 25), # slow mover
]

SUMMER_BOOST = {"Produce": 0.15, "Beverages": 0.25}  # extra demand at the peak of summer


def main() -> None:
    rng = np.random.default_rng(SEED)
    dates = pd.date_range(START, END, freq="D")
    # 0 in April, rising to 1 in late July, back toward 0 by end of September
    summer = np.clip(np.sin(np.linspace(0, np.pi, len(dates))), 0, 1)

    sales_rows, waste_rows, inventory_rows = [], [], []
    for name, category, base, price, cost, lead, waste_rate, on_hand in PRODUCTS:
        for i, day in enumerate(dates):
            season = 1 + SUMMER_BOOST.get(category, 0) * summer[i]
            demand = base * WEEKDAY_FACTOR[day.dayofweek] * season
            units = int(rng.poisson(demand))
            if units > 0:
                sales_rows.append((day.date(), name, category, units, price))

            if waste_rate > 0:
                monday_extra = 1.8 if day.dayofweek == 0 else 1.0
                wasted = int(rng.poisson(base * waste_rate * monday_extra))
                if wasted > 0:
                    if category in ("Bakery", "Produce"):
                        reason = rng.choice(["Expired", "Spoiled", "Damaged"], p=[0.55, 0.35, 0.10])
                    elif category in ("Dairy", "Meat"):
                        reason = rng.choice(["Expired", "Spoiled", "Damaged"], p=[0.70, 0.15, 0.15])
                    else:
                        reason = rng.choice(["Expired", "Damaged"], p=[0.3, 0.7])
                    waste_rows.append((day.date(), name, wasted, str(reason)))

        inventory_rows.append((name, category, on_hand, cost, lead))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sales_rows, columns=["date", "product", "category", "units_sold", "unit_price"]).to_csv(
        OUT_DIR / "sales.csv", index=False)
    pd.DataFrame(inventory_rows, columns=["product", "category", "on_hand", "unit_cost", "lead_time_days"]).to_csv(
        OUT_DIR / "inventory.csv", index=False)
    pd.DataFrame(waste_rows, columns=["date", "product", "units_wasted", "reason"]).to_csv(
        OUT_DIR / "waste.csv", index=False)

    # A deliberately broken file for demonstrating validation errors.
    broken = pd.DataFrame([
        ("2026-09-01", "Milk 2L", "Dairy", "31", "5.49"),
        ("2026-09-01", "", "Dairy", "12", "4.99"),                 # blank product
        ("2026-09-02", "Pasta 900g", "Pantry", "-3", "2.99"),      # negative units
        ("2026-13-40", "Spinach 312g", "Produce", "6", "4.49"),    # impossible date
        ("2026-09-03", "Bananas (bunch)", "Produce", "20", "abc"), # price not a number
        ("2026-09-04", "Milk 2L", "Dairy", "2.5", "5.49"),         # half a unit
        ("2026-09-01", "Milk 2L", "Dairy", "29", "5.49"),          # duplicate date + product
    ], columns=["date", "product", "category", "units_sold", "unit_price"])
    broken.to_csv(OUT_DIR / "sales_with_errors.csv", index=False)

    print(f"Wrote {len(sales_rows)} sales rows, {len(waste_rows)} waste rows and "
          f"{len(inventory_rows)} products to {OUT_DIR}")


if __name__ == "__main__":
    main()
