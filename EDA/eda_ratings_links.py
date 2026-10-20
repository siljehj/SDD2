import pandas as pd

from eda_overview import load_csv, print_section
from eda_movies import parse_nested, percent, print_table


# --- Helpers ----------------------------------------------------------------

def summary_row(label, values):
    return [label, f"{values.min():,}", f"{values.median():,.0f}",
            f"{values.mean():,.1f}", f"{values.max():,}"]


def load_movie_id_sets():
    movies = load_csv("movies_metadata.csv")
    movies["id_num"] = pd.to_numeric(movies["id"], errors="coerce")
    movies = movies[movies["id_num"].notna()]

    has_genre = movies["genres"].apply(parse_nested).apply(
        lambda g: isinstance(g, list) and len(g) > 0)
    all_ids = set(movies["id_num"].astype(int))
    genre_ids = set(movies.loc[has_genre, "id_num"].astype(int))
    duplicate_ids = set(movies.loc[movies["id_num"].duplicated(), "id_num"].astype(int))
    return all_ids, genre_ids, duplicate_ids


# --- links.csv ---------------------------------------------------------------

def check_link_duplicates(links):
    """Print duplicate movieIds and tmdbIds that are used by several movieIds."""
    print_section("Links 1. Duplicate movieId and shared tmdbId")
    dup_movie = links["movieId"].duplicated().sum()

    tmdb_counts = links["tmdbId"].dropna().value_counts()
    shared = tmdb_counts[tmdb_counts > 1]
    print_table([
        ["Duplicate movieId values", dup_movie],
        ["tmdbId values used by more than one movieId", len(shared)],
        ["movieIds involved", shared.sum()],
    ], headers=["Measure", "Count"])

    if len(shared):
        examples = links[links["tmdbId"].isin(shared.index[:5])].sort_values("tmdbId")
        print("\nExamples:")
        print_table(examples[["tmdbId", "movieId", "imdbId"]].values.tolist(),
                    headers=["tmdbId", "movieId", "imdbId"])


def check_missing_tmdb(links):
    """Print the number of links without a tmdbId."""
    print_section("Links 2. Missing tmdbId")
    missing = links["tmdbId"].isna().sum()
    print_table([["tmdbId missing", missing, percent(missing, len(links))]],
                headers=["Measure", "Count", "Percent"])


def check_tmdb_in_movies(links, movie_ids):
    """Print how many tmdbId values exist in movies_metadata.csv."""
    print_section("Links 3. tmdbId found in movies_metadata")
    tmdb = links["tmdbId"].dropna().drop_duplicates()
    found = tmdb.isin(movie_ids).sum()
    print_table([
        ["Distinct tmdbId values", len(tmdb), ""],
        ["Found in movies_metadata", found, percent(found, len(tmdb))],
        ["Not found", len(tmdb) - found, percent(len(tmdb) - found, len(tmdb))],
    ], headers=["Measure", "Count", "Percent"])


# --- ratings.csv -------------------------------------------------------------

def count_rating_values(ratings):
    """Print value counts of rating, sorted by rating, to show the scale."""
    print_section("Ratings 1. Rating values")
    counts = ratings["rating"].value_counts().sort_index()
    print_table([[r, f"{c:,}", percent(c, len(ratings))] for r, c in counts.items()],
                headers=["Rating", "Count", "Percent"])


def count_duplicate_pairs(ratings):
    """Print the number of (userId, movieId) pairs that occur more than once."""
    print_section("Ratings 2. Duplicate (userId, movieId) pairs")
    dup = ratings.duplicated(subset=["userId", "movieId"]).sum()
    print(f"Duplicate pairs: {dup:,} ({percent(dup, len(ratings))})")


def show_time_range(ratings):
    """Print the earliest and latest timestamp as dates (UTC)."""
    print_section("Ratings 3. Time range")
    first = pd.to_datetime(ratings["timestamp"].min(), unit="s")
    last = pd.to_datetime(ratings["timestamp"].max(), unit="s")
    print_table([["Earliest", first], ["Latest", last]],
                headers=["", "Timestamp (UTC)"])


def summarise_users(ratings, min_ratings=20):
    """Print the number of users and statistics of ratings per user."""
    print_section("Ratings 4. Ratings per user")
    per_user = ratings["userId"].value_counts()
    active = (per_user >= min_ratings).sum()
    print(f"Distinct users: {len(per_user):,}")
    print(f"Users with >= {min_ratings} ratings: {active:,} "
          f"({percent(active, len(per_user))})")
    print_table([summary_row("Ratings per user", per_user)],
                headers=["", "Min", "Median", "Mean", "Max"])


def summarise_movies(ratings):
    """Print the number of rated movies and statistics of ratings per movie."""
    print_section("Ratings 5. Ratings per movie")
    per_movie = ratings["movieId"].value_counts()
    print(f"Distinct rated movies: {len(per_movie):,}")
    print_table([summary_row("Ratings per movie", per_movie)],
                headers=["", "Min", "Median", "Mean", "Max"])


def check_coverage(ratings, links, movie_ids, genre_ids):
    """
    Print how many ratings can be linked step by step to a movie:
      movieId -> tmdbId in links.csv -> id in movies_metadata -> has a genre.
    """
    print_section("Ratings 6. Coverage of ratings")

    with_tmdb = links[links["tmdbId"].notna()]
    in_movies = with_tmdb[with_tmdb["tmdbId"].isin(movie_ids)]
    with_genre = in_movies[in_movies["tmdbId"].isin(genre_ids)]

    total = len(ratings)
    table = []
    for label, subset in [("movieId has a tmdbId in links.csv", with_tmdb),
                          ("... tmdbId exists in movies_metadata", in_movies),
                          ("... movie has at least one genre", with_genre)]:
        n = ratings["movieId"].isin(subset["movieId"]).sum()
        table.append([label, f"{n:,}", percent(n, total)])
    print_table(table, headers=["Condition", "Ratings", "Percent"])


# --- Cross-file checks -------------------------------------------------------

def shared_tmdb_ids(links):
    """Return the set of tmdbId values used by more than one movieId."""
    counts = links["tmdbId"].dropna().value_counts()
    return set(counts[counts > 1].index)


def check_duplicate_user_tmdb(ratings, links, n_examples=5):
    """Count users who rated the same TMDB movie through different movieIds."""
    print_section("Cross 1. Duplicate (userId, tmdbId) pairs")

    shared = links[links["tmdbId"].isin(shared_tmdb_ids(links))]
    subset = ratings[ratings["movieId"].isin(shared["movieId"])].copy()
    subset["tmdbId"] = subset["movieId"].map(shared.set_index("movieId")["tmdbId"])

    dup = subset[subset.duplicated(subset=["userId", "tmdbId"], keep=False)]
    pairs = dup.groupby(["userId", "tmdbId"]).agg(
        movieIds=("movieId", list), ratings=("rating", list))

    print_table([
        ["Ratings of movieIds with a shared tmdbId", f"{len(subset):,}"],
        ["Duplicate (userId, tmdbId) pairs", f"{len(pairs):,}"],
        ["Ratings involved in these pairs", f"{len(dup):,}"],
    ], headers=["Measure", "Count"])

    if len(pairs):
        print(f"\nExamples (first {min(n_examples, len(pairs))}):")
        print_table([[u, t, m, r] for (u, t), (m, r) in pairs.head(n_examples).iterrows()],
                    headers=["userId", "tmdbId", "movieIds", "ratings"])


def compare_duplicate_ids(links, movie_duplicate_ids):
    """Compare tmdbIds shared in links.csv with duplicate ids in movies_metadata.csv."""
    print_section("Cross 2. Shared tmdbIds in links vs. duplicate ids in movies_metadata")
    in_links = shared_tmdb_ids(links)
    print_table([
        ["In both", len(in_links & movie_duplicate_ids)],
        ["Only shared in links.csv", len(in_links - movie_duplicate_ids)],
        ["Only duplicated in movies_metadata.csv", len(movie_duplicate_ids - in_links)],
    ], headers=["Ids", "Count"])


# --- Main --------------------------------------------------------------------

def main():
    movie_ids, genre_ids, movie_duplicate_ids = load_movie_id_sets()

    print("=" * 80)
    print("links.csv")
    print("=" * 80)
    links = load_csv("links.csv")
    links["tmdbId"] = links["tmdbId"].astype("Int64")
    check_link_duplicates(links)
    check_missing_tmdb(links)
    check_tmdb_in_movies(links, movie_ids)
    print()

    print("=" * 80)
    print("ratings.csv")
    print("=" * 80)
    ratings = load_csv("ratings.csv") 
    count_rating_values(ratings)
    count_duplicate_pairs(ratings)
    show_time_range(ratings)
    summarise_users(ratings)
    summarise_movies(ratings)
    check_coverage(ratings, links, movie_ids, genre_ids)
    print()

    print("=" * 80)
    print("Cross-file checks")
    print("=" * 80)
    check_duplicate_user_tmdb(ratings, links)
    compare_duplicate_ids(links, movie_duplicate_ids)


if __name__ == "__main__":
    main()
