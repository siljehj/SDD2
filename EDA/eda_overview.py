import time
from pathlib import Path
from tabulate import tabulate

import pandas as pd


# --- Paths -----------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent / "dataset"


# --- Per-file loading options ----------------------------------------------
FILE_CONFIG = {
    "movies_metadata.csv": {"low_memory": False},
    "credits.csv": {},
    "keywords.csv": {},
    "ratings.csv": {
        "dtype": {
            "userId": "int32",
            "movieId": "int32",
            "rating": "float32",
            "timestamp": "int32",  
        }
    },
    "ratings_small.csv": {},
    "links.csv": {"dtype": {"imdbId": "string"}},
    "links_small.csv": {"dtype": {"imdbId": "string"}},
}

# Columns holding nested JSON
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
