"""Check an uploaded CSV before it is used anywhere else.

The goal is error messages a non-technical owner can act on, for example:
    "Column 'units_sold' has values that are not numbers in rows 4, 9."

Row numbers match what you see in Excel or Google Sheets
(row 1 is the header, so the first data row is row 2).
"""

from dataclasses import dataclass, field

import pandas as pd

from ops.schemas import SCHEMAS

MAX_ROWS_TO_LIST = 5  # keep messages short when many rows are bad


@dataclass
class ValidationResult:
    """The cleaned table plus any problems found."""

    dataset: str
    data: pd.DataFrame | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _spreadsheet_rows(mask: pd.Series) -> str:
    """Turn a True/False mask into a readable list like 'rows 2, 5, 7 (+3 more)'."""
    rows = [int(i) + 2 for i in mask[mask].index]  # +2: header is row 1, index starts at 0
    shown = ", ".join(str(r) for r in rows[:MAX_ROWS_TO_LIST])
    extra = len(rows) - MAX_ROWS_TO_LIST
    label = "row" if len(rows) == 1 else "rows"
    return f"{label} {shown}" + (f" (+{extra} more)" if extra > 0 else "")


def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """'Units Sold ' -> 'units_sold' so small header differences don't fail the upload."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def validate(df: pd.DataFrame, dataset: str) -> ValidationResult:
    """Validate one table against its schema and return cleaned, correctly typed data."""
    if dataset not in SCHEMAS:
        raise ValueError(f"Unknown dataset '{dataset}'. Expected one of {list(SCHEMAS)}.")

    schema = SCHEMAS[dataset]
    expected = schema["columns"]
    result = ValidationResult(dataset=dataset, data=None)

    df = _clean_column_names(df).reset_index(drop=True)

    # 1. Required columns
    missing = [c for c in expected if c not in df.columns]
    if missing:
        result.errors.append(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {', '.join(expected)}."
        )
        return result  # nothing else can be checked reliably

    extra = [c for c in df.columns if c not in expected]
    if extra:
        result.warnings.append(f"Ignored extra column(s): {', '.join(extra)}.")
    df = df[list(expected)].copy()

    if df.empty:
        result.errors.append("The file has a header but no data rows.")
        return result

    # 2. Each column has the right kind of value
    for col, col_type in expected.items():
        raw = df[col]
        blank = raw.isna() | (raw.astype(str).str.strip() == "")
        if blank.any():
            result.errors.append(f"Column '{col}' is blank in {_spreadsheet_rows(blank)}.")

        if col_type == "text":
            df[col] = raw.astype(str).str.strip()

        elif col_type == "date":
            parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
            bad = parsed.isna() & ~blank
            if bad.any():
                result.errors.append(
                    f"Column '{col}' has values that are not valid dates in {_spreadsheet_rows(bad)}. "
                    "Use the format YYYY-MM-DD, for example 2026-07-15."
                )
            df[col] = parsed.dt.normalize()

        else:  # "int" or "float"
            parsed = pd.to_numeric(raw, errors="coerce")
            bad = parsed.isna() & ~blank
            if bad.any():
                result.errors.append(
                    f"Column '{col}' has values that are not numbers in {_spreadsheet_rows(bad)}."
                )
            negative = parsed < 0
            if negative.any():
                result.errors.append(f"Column '{col}' has negative values in {_spreadsheet_rows(negative)}.")
            if col_type == "int":
                not_whole = parsed.notna() & (parsed % 1 != 0)
                if not_whole.any():
                    result.errors.append(
                        f"Column '{col}' should hold whole numbers but has decimals in {_spreadsheet_rows(not_whole)}."
                    )
            df[col] = parsed

    # 3. Duplicate rows (e.g. the same product twice on the same day)
    key = schema["unique_key"]
    if key:
        dupes = df.duplicated(subset=key, keep=False) & df[key].notna().all(axis=1)
        if dupes.any():
            result.errors.append(
                f"Duplicate {' + '.join(key)} found in {_spreadsheet_rows(dupes)}. "
                "Each combination should appear only once; combine or remove the duplicates."
            )

    if result.errors:
        return result

    # Safe to convert now that every value is known to be a whole number.
    for col, col_type in expected.items():
        if col_type == "int":
            df[col] = df[col].astype(int)

    result.data = df
    return result


def check_consistency(sales: pd.DataFrame, inventory: pd.DataFrame, waste: pd.DataFrame | None = None) -> list[str]:
    """Warnings about how the files relate to each other. These never block an upload."""
    warnings = []
    inventory_products = set(inventory["product"])

    sold_not_stocked = sorted(set(sales["product"]) - inventory_products)
    if sold_not_stocked:
        warnings.append(
            f"{len(sold_not_stocked)} product(s) appear in sales but not in inventory, so they have no "
            f"cost and are left out of margin and reorder numbers: {', '.join(sold_not_stocked[:5])}"
            + ("..." if len(sold_not_stocked) > 5 else "")
        )

    if waste is not None:
        wasted_not_stocked = sorted(set(waste["product"]) - inventory_products)
        if wasted_not_stocked:
            warnings.append(
                f"{len(wasted_not_stocked)} wasted product(s) are not in inventory, so their waste cost "
                f"is unknown: {', '.join(wasted_not_stocked[:5])}"
            )
    return warnings
