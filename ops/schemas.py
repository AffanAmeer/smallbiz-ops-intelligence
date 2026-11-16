"""What each CSV file must look like.

Every dataset has a list of required columns and the type each column holds.
Keeping this in one place means the validator, the database and the README
all describe the same thing.

Column types:
    "text"  -> any non-blank text
    "date"  -> a date such as 2026-07-15
    "int"   -> a whole number, 0 or more
    "float" -> a number, 0 or more
"""

SCHEMAS = {
    "sales": {
        "description": "One row per product per day: how many units were sold and at what price.",
        "columns": {
            "date": "date",
            "product": "text",
            "category": "text",
            "units_sold": "int",
            "unit_price": "float",
        },
        # A product should appear at most once per day.
        "unique_key": ["date", "product"],
    },
    "inventory": {
        "description": "One row per product: what is on the shelf today and how long a reorder takes.",
        "columns": {
            "product": "text",
            "category": "text",
            "on_hand": "int",
            "unit_cost": "float",
            "lead_time_days": "int",
        },
        "unique_key": ["product"],
    },
    "waste": {
        "description": "One row per waste event: units thrown out and why.",
        "columns": {
            "date": "date",
            "product": "text",
            "units_wasted": "int",
            "reason": "text",
        },
        # The same product can be wasted twice in a day for different reasons.
        "unique_key": None,
    },
}

DATASET_NAMES = list(SCHEMAS)
