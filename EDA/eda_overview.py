"""
EDA overview of The Movies Dataset (TDT4225, Part 1).

For each CSV file in dataset/ this script prints:
  - number of rows and columns
  - column names and data types
  - number and percentage of missing values per column
  - whether each column contains nested JSON-like strings (not parsed here)

Run from anywhere:  python Part1/eda_overview.py
"""

import time
from pathlib import Path
from tabulate import tabulate

import pandas as pd


# --- Paths -----------------------------------------------------------------
# The script lives in <repo>/Part1/, the data in <repo>/dataset/.
# Building the path from __file__ makes the script independent of the
# directory it is run from.
SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent / "dataset"


# --- Per-file loading options ----------------------------------------------
# Extra keyword arguments passed to pd.read_csv for each file.
FILE_CONFIG = {
    # Some rows in this file are malformed, so pandas would guess different
    # types per chunk. low_memory=False reads the whole file before choosing
    # dtypes, which avoids the "mixed types" warning.
    "movies_metadata.csv": {"low_memory": False},
    "credits.csv": {},
    "keywords.csv": {},
    # ~26 million rows: explicit compact dtypes roughly halve memory use
    # compared to pandas' default int64/float64.
    "ratings.csv": {
        "dtype": {
            "userId": "int32",
            "movieId": "int32",
            "rating": "float32",
            "timestamp": "int32",  # Unix seconds, fits in int32 until 2038
        }
    },
    "ratings_small.csv": {},
    # imdbId is read as text so leading zeros (e.g. "0114709") are kept.
    "links.csv": {"dtype": {"imdbId": "string"}},
    "links_small.csv": {"dtype": {"imdbId": "string"}},
}

# Columns holding nested JSON-like strings, e.g.
# "[{'id': 16, 'name': 'Animation'}, ...]". They use Python syntax (single
# quotes), so they are not strict JSON. They are only noted here; parsing is
# done later during cleaning.
NESTED_COLUMNS = {
    "movies_metadata.csv": [
        "belongs_to_collection",
        "genres",
        "production_companies",
        "production_countries",
        "spoken_languages",
    ],
    "credits.csv": ["cast", "crew"],
    "keywords.csv": ["keywords"],
}


def load_csv(filename):
    """Read one CSV file from the dataset folder using its configured options."""
    path = DATASET_DIR / filename
    options = FILE_CONFIG.get(filename, {})

    # Large files (credits.csv, ratings.csv) take a while to read, so show
    # progress to make it clear the script is still working.
    size_mb = path.stat().st_size / 1_000_000
    print(f"Loading {filename} ({size_mb:.0f} MB)...", flush=True)
    start = time.perf_counter()
    df = pd.read_csv(path, **options)
    print(f"Loaded in {time.perf_counter() - start:.1f} s\n")
    return df


def print_section(title):
    """Print a section title underlined with dashes."""
    print(f"\n{title}")
    print("-" * len(title))


def print_shape(df):
    """Print the number of rows and columns."""
    rows, cols = df.shape
    print_section("Dataset overview")
    print(f"Number of rows: {rows:,}")
    print(f"Number of columns: {cols}")


def print_columns_and_missing(filename, df):
    """
    Print one table with each column's data type, whether it holds nested
    JSON-like strings (listed in NESTED_COLUMNS), and its missing values.
    """
    missing_count = df.isna().sum()
    missing_percent = (missing_count / len(df) * 100).round(2)
    nested = NESTED_COLUMNS.get(filename, [])

    table = [
        [col, str(df[col].dtype), "yes" if col in nested else "no",
         missing_count[col], f"{missing_percent[col]:.2f} %"]
        for col in df.columns
    ]
    print_section("Columns and missing values")
    print(tabulate(table,
                   headers=["Column", "Data type", "Nested", "Missing", "Missing (%)"],
                   tablefmt="pretty"))


def overview_file(filename):
    """Load one file and print the full overview for it."""
    print("=" * 80)
    print(filename)
    print("=" * 80)

    df = load_csv(filename)
    print_shape(df)
    print_columns_and_missing(filename, df)
    print()


def main():
    """Run the overview for every file, one at a time to limit memory use."""
    for filename in FILE_CONFIG:
        overview_file(filename)


if __name__ == "__main__":
    main()
