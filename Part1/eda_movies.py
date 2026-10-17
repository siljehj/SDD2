"""
Deeper EDA of movies_metadata.csv (TDT4225, Part 1).

The script:
  1. finds rows whose id is not a number (malformed rows)
  2. counts duplicate ids and checks whether the duplicates are identical
  3. counts hidden missing values (0 instead of unknown, empty lists "[]")
  4. summarises the distributions of the main attributes
  5. saves three plots to Part1/figures/
  6. runs extra quality checks (zero ratings, tiny budgets, collections,
     status vs. release date)

The data files are only read, never modified.

Run from anywhere:  python Part1/eda_movies.py
"""

import ast

import matplotlib

matplotlib.use("Agg")  # save figures to files without opening a window
import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate

# Reuse the loading function, paths and section style from the overview script.
from eda_overview import SCRIPT_DIR, load_csv, print_section


FIGURES_DIR = SCRIPT_DIR / "figures"

# Columns that are stored as text but should be numbers.
NUMERIC_COLUMNS = ["id", "budget", "revenue", "runtime", "popularity",
                   "vote_average", "vote_count"]

# Nested columns that hold a list of dicts, e.g. "[{'id': 16, 'name': 'Animation'}]".
LIST_COLUMNS = ["genres", "production_companies", "production_countries",
                "spoken_languages"]

# Colours for the plots: one series colour plus muted text/grid colours.
BAR_COLOR = "#2a78d6"
TEXT_COLOR = "#52514e"
GRID_COLOR = "#e4e3df"


# --- Helpers ----------------------------------------------------------------

def print_table(rows, headers):
    """Print a list of rows as a table in the same style as eda_overview.py."""
    print(tabulate(rows, headers=headers, tablefmt="pretty"))


def percent(count, total):
    """Format count/total as a percentage string."""
    return f"{count / total * 100:.2f} %"


def parse_nested(value):
    """
    Parse one nested value with ast.literal_eval.

    The values use Python syntax (single quotes), so json.loads would fail.
    Returns None for missing (NaN) or unparseable values.
    """
    if not isinstance(value, str):
        return None
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return None


# --- Preparation -------------------------------------------------------------

def prepare_data(df):
    """
    Add converted copies of the columns used in the analysis.

    The original text columns are kept unchanged so malformed values can still
    be inspected. New columns:
      <col>_num      numeric version of each column in NUMERIC_COLUMNS
      <col>_parsed   parsed Python list for each column in LIST_COLUMNS
      release_dt     release_date as a datetime
    """
    df = df.copy()
    for col in NUMERIC_COLUMNS:
        # errors="coerce" turns values that are not numbers into NaN.
        df[f"{col}_num"] = pd.to_numeric(df[col], errors="coerce")
    for col in LIST_COLUMNS:
        df[f"{col}_parsed"] = df[col].apply(parse_nested)
    df["release_dt"] = pd.to_datetime(df["release_date"], format="%Y-%m-%d",
                                      errors="coerce")
    return df


# --- 1. Malformed rows -------------------------------------------------------

def check_malformed_rows(df):
    """Print rows whose id is not a number and compare them with rows missing title etc."""
    bad_id = df["id_num"].isna()
    print_section("1. Rows where id is not a number")
    print(f"Number of rows: {bad_id.sum()}")

    # Show a few columns of each malformed row, to see that values are shifted.
    show_cols = ["id", "imdb_id", "title", "budget", "popularity", "vote_count"]
    rows = df.loc[bad_id, show_cols].astype(str).values.tolist()
    print_table([[i] + r for i, r in zip(df.index[bad_id], rows)],
                headers=["Row"] + show_cols)

    # Are these the same rows as those with missing title, vote_count, ...?
    print("\nOverlap with rows that have missing values in other columns:")
    table = []
    for col in ["title", "vote_count", "vote_average", "revenue", "video"]:
        missing = df[col].isna()
        both = (missing & bad_id).sum()
        table.append([col, missing.sum(), both, (missing & ~bad_id).sum()])
    print_table(table, headers=["Column", "Missing", "Also bad id", "Not bad id"])

    # The other rows with a missing title turn out to be the rows directly
    # before each malformed row: one movie has been split over two lines in
    # the CSV (the first line ends early, the second is shifted into the wrong
    # columns).
    before = malformed_row_pairs(df)
    print("\nRows with missing title, grouped with the malformed row after them:")
    table = [[i, df.at[i, "id"], df.at[i, "original_title"], i + 1, df.at[i + 1, "id"]]
             for i in before]
    print_table(table, headers=["Row", "id", "original_title", "Next row", "Next id"])


def malformed_row_pairs(df):
    """Return the index of each row that is directly followed by a malformed row."""
    bad_rows = df.index[df["id_num"].isna()]
    return [i - 1 for i in bad_rows]


def remove_malformed_rows(df):
    """Drop the malformed rows and the incomplete row before each of them."""
    before = malformed_row_pairs(df)
    to_drop = before + [i + 1 for i in before]
    print_section("Removing malformed rows")
    print(f"Dropped {len(to_drop)} rows ({len(before)} movies split over two lines). "
          f"Sections 3-5 use the remaining {len(df) - len(to_drop)} rows.")
    return df.drop(index=to_drop)


# --- 2. Duplicates -----------------------------------------------------------

def check_duplicates(df):
    """Count duplicate ids and check whether the duplicate rows are identical."""
    print_section("2. Duplicate ids")

    # Only use the original columns, not the converted copies.
    original = df[[c for c in df.columns if not c.endswith(("_num", "_parsed"))
                   and c != "release_dt"]]

    dup_ids = original["id"].duplicated(keep=False)  # all copies of a duplicated id
    print(f"Ids that occur more than once: {original.loc[dup_ids, 'id'].nunique()}")
    print(f"Extra rows caused by duplicate ids: {original['id'].duplicated().sum()}")
    print(f"Fully identical duplicate rows: {original.duplicated().sum()}")

    # For duplicates that are NOT identical, show which columns differ.
    differing = []
    for movie_id, group in original[dup_ids].groupby("id"):
        diff_cols = [c for c in group.columns if group[c].nunique(dropna=False) > 1]
        if diff_cols:
            differing.append([movie_id, len(group), ", ".join(diff_cols)])
    print(f"\nDuplicate ids where the copies differ: {len(differing)}")
    if differing:
        print_table(differing, headers=["id", "Copies", "Columns that differ"])


# --- 3. Hidden missing values ------------------------------------------------

def count_hidden_missing(df):
    """Count values that mean 'unknown' without being NaN: 0 and empty lists."""
    total = len(df)
    print_section("3. Hidden missing values")
    table = []

    # A budget, revenue or runtime of 0 almost certainly means "unknown".
    for col in ["budget", "revenue", "runtime"]:
        zeros = (df[f"{col}_num"] == 0).sum()
        table.append([col, "= 0", zeros, percent(zeros, total)])

    # Empty lists mean no genres/companies/... are registered.
    for col in LIST_COLUMNS:
        empty = df[f"{col}_parsed"].apply(lambda v: v == []).sum()
        table.append([col, "[]", empty, percent(empty, total)])

    print_table(table, headers=["Column", "Value", "Count", "Percent"])

    # Values that could not be parsed at all (NaN or malformed text).
    unparsed = [[col, df[f"{col}_parsed"].isna().sum()] for col in LIST_COLUMNS]
    print("\nNested values that could not be parsed (NaN or malformed):")
    print_table(unparsed, headers=["Column", "Count"])


# --- 4. Distributions --------------------------------------------------------

def summarise_release_dates(df):
    """Print how many release dates parse, and the number of movies per decade."""
    parsed = df["release_dt"].notna().sum()
    print_section("4a. release_date")
    print(f"Parsed as dates: {parsed} of {len(df)} ({percent(parsed, len(df))})")
    print(f"Earliest: {df['release_dt'].min().date()}   "
          f"Latest: {df['release_dt'].max().date()}")

    decade = (df["release_dt"].dt.year // 10 * 10).dropna().astype(int)
    counts = decade.value_counts().sort_index()
    print_table([[f"{d}s", n] for d, n in counts.items()],
                headers=["Decade", "Movies"])


def summarise_numeric(df):
    """Print min, max, median and mean for runtime, vote_average and vote_count."""
    print_section("4b. runtime, vote_average, vote_count")
    table = []
    for col in ["runtime", "vote_average", "vote_count"]:
        s = df[f"{col}_num"].dropna()
        table.append([col, len(s), s.min(), s.max(), s.median(), round(s.mean(), 2)])
    print_table(table, headers=["Column", "Count", "Min", "Max", "Median", "Mean"])


def count_vote_thresholds(df):
    """Print how many movies have at least 50 and at least 100 votes."""
    print_section("4c. Movies with enough votes")
    votes = df["vote_count_num"]
    table = [[f">= {t}", (votes >= t).sum(), percent((votes >= t).sum(), len(df))]
             for t in [50, 100]]
    print_table(table, headers=["vote_count", "Movies", "Percent"])


def summarise_money(df):
    """Print summary statistics for budget and revenue, using only values > 0."""
    print_section("4d. budget and revenue (only values > 0)")
    table = []
    for col in ["budget", "revenue"]:
        s = df[f"{col}_num"]
        s = s[s > 0]
        table.append([col, len(s), f"{s.min():,.0f}", f"{s.median():,.0f}",
                      f"{s.mean():,.0f}", f"{s.max():,.0f}"])
    print_table(table, headers=["Column", "Count", "Min", "Median", "Mean", "Max"])


def top_languages(df, n=10):
    """Print the n most common original_language values."""
    print_section(f"4e. Top {n} original_language")
    counts = df["original_language"].value_counts().head(n)
    print_table([[lang, c, percent(c, len(df))] for lang, c in counts.items()],
                headers=["Language", "Movies", "Percent"])


def first_genre(genres):
    """Return the name of the first genre in a parsed list, or '(none)'."""
    if isinstance(genres, list) and genres:
        return genres[0]["name"]
    return "(none)"


def count_first_genres(df):
    """Print the number of movies per first genre and return the counts."""
    print_section("4f. Movies per first genre")
    counts = df["genres_parsed"].apply(first_genre).value_counts()
    print_table([[g, c, percent(c, len(df))] for g, c in counts.items()],
                headers=["First genre", "Movies", "Percent"])
    return counts


def count_status(df):
    """Print value counts for status, including missing values."""
    print_section("4g. status")
    counts = df["status"].value_counts(dropna=False)
    print_table([[str(s), c, percent(c, len(df))] for s, c in counts.items()],
                headers=["Status", "Movies", "Percent"])


# --- 5. Plots ----------------------------------------------------------------

def style_axes(ax, title, xlabel, ylabel):
    """Apply a common, quiet style: title, labels, light grid, no top/right border."""
    ax.set_title(title, loc="left", fontsize=12)
    ax.set_xlabel(xlabel, color=TEXT_COLOR)
    ax.set_ylabel(ylabel, color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    ax.grid(color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)


def save_figure(fig, filename):
    """Save a figure to Part1/figures/ and close it."""
    FIGURES_DIR.mkdir(exist_ok=True)
    path = FIGURES_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved {path.relative_to(SCRIPT_DIR.parent)}")


def plot_movies_per_year(df):
    """Line chart of the number of movies per release year."""
    counts = df["release_dt"].dt.year.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(counts.index, counts.values, color=BAR_COLOR, linewidth=2)
    style_axes(ax, "Movies per release year", "Release year", "Number of movies")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "movies_per_year.png")


def plot_vote_average(df):
    """Histogram of vote_average (one bin per 0.5 points)."""
    values = df["vote_average_num"].dropna()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = [x / 2 for x in range(0, 21)]  # 0.0, 0.5, ..., 10.0
    ax.hist(values, bins=bins, color=BAR_COLOR, edgecolor="white", linewidth=1)
    style_axes(ax, "Distribution of vote_average", "vote_average", "Number of movies")
    ax.grid(axis="x", visible=False)
    save_figure(fig, "vote_average_distribution.png")


def plot_first_genres(genre_counts):
    """Horizontal bar chart of movies per first genre, largest at the top."""
    counts = genre_counts.sort_values()
    fig, ax = plt.subplots(figsize=(8, 6.5))
    ax.barh(counts.index, counts.values, color=BAR_COLOR, height=0.7)
    style_axes(ax, "Movies per first genre", "Number of movies", "")
    ax.grid(axis="y", visible=False)
    save_figure(fig, "movies_per_first_genre.png")


# --- 6. Extra quality checks -------------------------------------------------

def check_zero_vote_average(df):
    """Count movies with vote_average = 0 and how many of them have no votes."""
    print_section("6a. vote_average = 0")
    zero_avg = df["vote_average_num"] == 0
    no_votes = zero_avg & (df["vote_count_num"] == 0)
    table = [
        ["vote_average = 0", zero_avg.sum(), percent(zero_avg.sum(), len(df))],
        ["... and vote_count = 0", no_votes.sum(), percent(no_votes.sum(), zero_avg.sum())],
    ]
    # The second percentage is relative to the movies with vote_average = 0.
    print_table(table, headers=["Condition", "Movies", "Percent"])


def check_tiny_money(df, limit=1000, n_examples=8):
    """Count movies with budget or revenue between 0 and limit, and show examples."""
    print_section(f"6b. budget or revenue > 0 but < {limit:,}")
    budget, revenue = df["budget_num"], df["revenue_num"]
    tiny_budget = (budget > 0) & (budget < limit)
    tiny_revenue = (revenue > 0) & (revenue < limit)
    tiny_any = tiny_budget | tiny_revenue

    print_table([["budget", tiny_budget.sum()],
                 ["revenue", tiny_revenue.sum()],
                 ["budget or revenue", tiny_any.sum()]],
                headers=["Column", "Movies"])

    # Such small values are probably given in millions (e.g. 5 = 5,000,000)
    # or are simply wrong. Show a few examples.
    examples = df.loc[tiny_any, ["title", "budget_num", "revenue_num"]].head(n_examples)
    print(f"\nExamples (first {len(examples)}):")
    print_table([[t, f"{b:,.0f}", f"{r:,.0f}"] for t, b, r in examples.values],
                headers=["Title", "Budget", "Revenue"])


def check_collections(df):
    """Parse belongs_to_collection and count movies and collections."""
    print_section("6c. belongs_to_collection")

    # Each value is a single dict, e.g. "{'id': 10194, 'name': 'Toy Story Collection', ...}".
    parsed = df["belongs_to_collection"].apply(parse_nested)
    in_collection = parsed.apply(lambda v: isinstance(v, dict))
    unparsed = df["belongs_to_collection"].notna() & ~in_collection

    # Count movies per collection id (the id is unique, names may not be).
    collections = parsed[in_collection].apply(lambda v: (v["id"], v["name"]))
    per_collection = collections.value_counts()

    print_table([
        ["Movies in a collection", in_collection.sum(), percent(in_collection.sum(), len(df))],
        ["Distinct collections", len(per_collection), ""],
        ["Collections with >= 3 movies", (per_collection >= 3).sum(), ""],
        ["Values that could not be parsed", unparsed.sum(), ""],
    ], headers=["Measure", "Count", "Percent of movies"])

    print("\nLargest collections:")
    print_table([[name, n] for (_, name), n in per_collection.head(5).items()],
                headers=["Collection", "Movies"])


def release_category(date):
    """Group a release date as 'missing', 'after 2017' or '2017 or earlier'."""
    if pd.isna(date):
        return "missing"
    return "after 2017" if date.year > 2017 else "2017 or earlier"


def crosstab_status_release(df):
    """Cross-table of status against whether release_date is missing or after 2017."""
    print_section("6d. status vs. release_date")
    category = df["release_dt"].apply(release_category)
    status = df["status"].fillna("(missing)")
    table = pd.crosstab(status, category, margins=True, margins_name="Total")

    # Fixed column order so the table reads from "normal" to "suspicious".
    columns = ["2017 or earlier", "after 2017", "missing", "Total"]
    table = table.reindex(columns=columns, fill_value=0)
    print_table([[s] + list(row) for s, row in zip(table.index, table.values)],
                headers=["Status"] + columns)


# --- Main --------------------------------------------------------------------

def main():
    df = prepare_data(load_csv("movies_metadata.csv"))

    check_malformed_rows(df)
    check_duplicates(df)

    # The rest of the analysis ignores the malformed rows, so their shifted
    # values (e.g. company names in genres) do not distort the results.
    df = remove_malformed_rows(df)
    count_hidden_missing(df)

    summarise_release_dates(df)
    summarise_numeric(df)
    count_vote_thresholds(df)
    summarise_money(df)
    top_languages(df)
    genre_counts = count_first_genres(df)
    count_status(df)

    print_section("5. Figures")
    plot_movies_per_year(df)
    plot_vote_average(df)
    plot_first_genres(genre_counts)

    check_zero_vote_average(df)
    check_tiny_money(df)
    check_collections(df)
    crosstab_status_release(df)


if __name__ == "__main__":
    main()
