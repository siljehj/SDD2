import ast
import time
from pathlib import Path

import pandas as pd


# --- Settings ----------------------------------------------------------------

# True: use ratings_small.csv and links_small.csv for quick testing.
USE_SMALL = False

# Movies with a runtime above this are removed
MAX_RUNTIME = 300

# Budget and revenue below this are treated as unknown. 
MIN_MONEY = 1000

ROOT_DIR = Path(__file__).resolve().parent
DATASET_DIR = ROOT_DIR / "dataset"
CLEANED_DIR = ROOT_DIR / "cleaned"

RATINGS_FILE = "ratings_small.csv" if USE_SMALL else "ratings.csv"
LINKS_FILE = "links_small.csv" if USE_SMALL else "links.csv"

MOVIE_LIST_COLUMNS = ["genres", "production_companies", "production_countries",
                      "spoken_languages"]

TEXT_COLUMNS = ["belongs_to_collection", "homepage", "imdb_id", "original_language",
                "original_title", "overview", "poster_path", "status", "tagline",
                "title"]

CAST_FIELDS = ["id", "name", "character", "gender", "order"]
CREW_FIELDS = ["id", "name", "job", "department", "gender"]


# --- Helpers -----------------------------------------------------------------

def log_step(name, before, after, note=""):
    removed = before - after
    extra = f"  ({note})" if note else ""
    print(f"  {name:<52} {before:>10,} -> {after:>10,}  removed {removed:>9,}{extra}")


def format_date(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_nested(value):
    if not isinstance(value, str):
        return None
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return None


def to_list(value):
    return value if isinstance(value, list) else []


def read_csv(filename, **options):
    print(f"\nLoading {filename}...", flush=True)
    start = time.perf_counter()
    df = pd.read_csv(DATASET_DIR / filename, **options)
    print(f"  loaded {len(df):,} rows in {time.perf_counter() - start:.1f} s")
    return df


# --- movies_metadata.csv -----------------------------------------------------

# Remove rows where id is not numeric, and the row directly before each
def remove_malformed_rows(movies):
    before = len(movies)
    bad_rows = movies.index[pd.to_numeric(movies["id"], errors="coerce").isna()]
    to_drop = list(bad_rows) + [i - 1 for i in bad_rows]
    movies = movies.drop(index=to_drop)
    log_step("Remove malformed rows (+ row before)", before, len(movies))
    return movies


def convert_numeric(movies):
    for col in ["id", "budget", "revenue", "runtime", "popularity",
                "vote_average", "vote_count"]:
        movies[col] = pd.to_numeric(movies[col], errors="coerce")
    return movies

# Keep one row per id: the one with the highest vote_count
def remove_duplicate_movies(movies):
    before = len(movies)
    movies = (movies.sort_values("vote_count", ascending=False, kind="stable")
                    .drop_duplicates(subset="id", keep="first")
                    .sort_index())
    log_step("Remove duplicate ids (keep highest vote_count)", before, len(movies))
    return movies

# Store budget/revenue < MIN_MONEY and runtime = 0 as null
def nullify_unknown_numbers(movies):
    for col in ["budget", "revenue"]:
        invalid = movies[col] < MIN_MONEY
        movies.loc[invalid, col] = None
        log_step(f"Set {col} < {MIN_MONEY:,} to null", len(movies), len(movies),
                 f"{invalid.sum():,} values set to null")

    zero = movies["runtime"] == 0
    movies.loc[zero, "runtime"] = None
    log_step("Set runtime = 0 to null", len(movies), len(movies),
             f"{zero.sum():,} values set to null")
    return movies

# Remove movies with runtime above MAX_RUNTIME
def remove_long_runtimes(movies):
    before = len(movies)
    movies = movies[~(movies["runtime"] > MAX_RUNTIME)]
    log_step(f"Remove runtime > {MAX_RUNTIME} min", before, len(movies))
    return movies

# Store vote_average as null when vote_count = 0
def nullify_vote_average(movies):
    no_votes = movies["vote_count"] == 0
    movies.loc[no_votes, "vote_average"] = None
    log_step("Set vote_average to null when vote_count = 0", len(movies), len(movies),
             f"{no_votes.sum():,} values set to null")
    return movies


def convert_types(movies):
    for col in ["id", "budget", "revenue", "vote_count"]:
        has_null = movies[col].isna().any()
        movies[col] = movies[col].astype("Int64" if has_null else "int64")
    for col in ["popularity", "runtime", "vote_average"]:
        has_null = movies[col].isna().any()
        movies[col] = movies[col].astype("Float64" if has_null else "float64")

    for col in ["adult", "video"]:
        movies[col] = movies[col].astype(str).map({"True": True, "False": False})
        unknown = movies[col].isna().sum()
        if unknown:
            print(f"  WARNING: {unknown} values in {col} are not True/False")
        movies[col] = movies[col].astype(bool)
    return movies


def parse_movie_nested(movies):
    for col in MOVIE_LIST_COLUMNS:
        parsed = movies[col].apply(parse_nested)
        not_list = parsed.apply(lambda v: not isinstance(v, list)).sum()
        movies[col] = parsed.apply(to_list)
        log_step(f"Parse {col}", len(movies), len(movies),
                 f"{not_list:,} missing/unparseable stored as []")

    collection = movies["belongs_to_collection"].apply(parse_nested)
    movies["belongs_to_collection"] = collection.apply(
        lambda v: v if isinstance(v, dict) else None)
    log_step("Parse belongs_to_collection", len(movies), len(movies),
             f"{movies['belongs_to_collection'].notna().sum():,} movies in a collection")
    return movies

# Store missing or empty text values as null
def nullify_missing_text(movies):
    for col in TEXT_COLUMNS:
        if col == "belongs_to_collection":
            continue  
        empty = movies[col].isna() | (movies[col].astype(str).str.strip() == "")
        movies[col] = movies[col].where(~empty, None)
    print("  Missing/empty text fields stored as null")
    return movies


def convert_release_date(movies):
    original_missing = movies["release_date"].isna().sum()
    movies["release_date"] = pd.to_datetime(movies["release_date"],
                                            format="%Y-%m-%d", errors="coerce")
    invalid = movies["release_date"].isna().sum() - original_missing
    dates = movies["release_date"].dropna()
    print(f"  release_date: {len(dates):,} dates, {original_missing:,} missing, "
          f"{invalid:,} invalid set to null")
    print(f"  release_date range: {format_date(dates.min())} to {format_date(dates.max())}")
    return movies


def clean_movies():
    movies = read_csv("movies_metadata.csv", low_memory=False)
    print("Cleaning movies_metadata.csv:")
    movies = remove_malformed_rows(movies)
    movies = convert_numeric(movies)
    movies = remove_duplicate_movies(movies)
    movies = nullify_unknown_numbers(movies)
    movies = remove_long_runtimes(movies)
    movies = nullify_vote_average(movies)
    movies = convert_types(movies)
    movies = parse_movie_nested(movies)
    movies = nullify_missing_text(movies)
    movies = convert_release_date(movies)
    return movies


# --- credits.csv and keywords.csv --------------------------------------------

# Remove duplicate ids, keeping the first row 
def remove_duplicate_ids(df, name):
    before = len(df)
    df = df.drop_duplicates(subset="id", keep="first")
    log_step(f"Remove duplicate ids in {name}", before, len(df))
    return df

# gender 0 -> null
def slim_person(person, fields):
    slim = {field: person.get(field) for field in fields}
    if slim["gender"] == 0:
        slim["gender"] = None
    return slim


def parse_people(df, col, fields):
    start = time.perf_counter()
    parsed = df[col].apply(parse_nested).apply(to_list)
    df[col] = parsed.apply(lambda people: [slim_person(p, fields) for p in people])
    log_step(f"Parse {col} (keep {', '.join(fields)})", len(df), len(df),
             f"{time.perf_counter() - start:.1f} s")
    return df

def clean_credits():
    credits = read_csv("credits.csv")
    print("Cleaning credits.csv:")
    credits = remove_duplicate_ids(credits, "credits")
    credits = parse_people(credits, "cast", CAST_FIELDS)
    credits = parse_people(credits, "crew", CREW_FIELDS)
    return credits


def clean_keywords():
    keywords = read_csv("keywords.csv")
    print("Cleaning keywords.csv:")
    keywords = remove_duplicate_ids(keywords, "keywords")
    keywords["keywords"] = keywords["keywords"].apply(parse_nested).apply(to_list)
    log_step("Parse keywords", len(keywords), len(keywords))
    return keywords


def embed(movies, extra, columns, name):
    before = len(movies)
    movies = movies.merge(extra[["id"] + columns], on="id", how="left")
    no_match = movies[columns[0]].isna().sum()
    for col in columns:
        movies[col] = movies[col].apply(to_list)
    log_step(f"Embed {name}", before, len(movies),
             f"movies without a row get []: {no_match:,}")
    return movies


def build_movie_documents(movies):
    movies = movies.rename(columns={"id": "_id"})
    columns = ["_id"] + [c for c in movies.columns if c != "_id"]
    return movies[columns].reset_index(drop=True)


# --- ratings.csv and links.csv -----------------------------------------------

def load_links():
    links = read_csv(LINKS_FILE, dtype={"movieId": "int32", "imdbId": "string"})
    links = links.dropna(subset=["tmdbId"])
    return links.set_index("movieId")["tmdbId"].astype("int32")


def load_ratings():
    return read_csv(RATINGS_FILE, dtype={"userId": "int32", "movieId": "int32",
                                         "rating": "float32", "timestamp": "int64"})


def map_to_tmdb(ratings, movie_to_tmdb):
    before = len(ratings)
    ratings["tmdbId"] = ratings["movieId"].map(movie_to_tmdb)  
    ratings = ratings.dropna(subset=["tmdbId"]).astype({"tmdbId": "int32"})
    log_step("Remove ratings without tmdbId", before, len(ratings))
    return ratings.drop(columns="movieId")


def remove_unknown_movies(ratings, movie_ids):
    before = len(ratings)
    ratings = ratings[ratings["tmdbId"].isin(movie_ids)]
    log_step("Remove ratings of movies not in cleaned movies", before, len(ratings))
    return ratings


def remove_duplicate_ratings(ratings):
    before = len(ratings)
    ratings = (ratings.sort_values("timestamp", kind="stable")
                      .drop_duplicates(subset=["userId", "tmdbId"], keep="last"))
    log_step("Remove duplicate (userId, tmdbId), keep latest", before, len(ratings))
    return ratings


def convert_timestamp(ratings):
    ratings["timestamp"] = pd.to_datetime(ratings["timestamp"], unit="s")
    print(f"  timestamp range: {format_date(ratings['timestamp'].min())} to "
          f"{format_date(ratings['timestamp'].max())} (UTC)")
    return ratings


def clean_ratings(movie_ids):
    movie_to_tmdb = load_links()
    ratings = load_ratings()
    print(f"Cleaning {RATINGS_FILE}:")
    ratings = map_to_tmdb(ratings, movie_to_tmdb)
    ratings = remove_unknown_movies(ratings, movie_ids)
    ratings = remove_duplicate_ratings(ratings)
    ratings = convert_timestamp(ratings)
    columns = ["userId", "tmdbId", "rating", "timestamp"]
    return ratings[columns].sort_index().reset_index(drop=True)


# --- Main --------------------------------------------------------------------

def save(df, filename):
    CLEANED_DIR.mkdir(exist_ok=True)
    path = CLEANED_DIR / filename
    df.to_pickle(path)
    size_mb = path.stat().st_size / 1_000_000
    print(f"\nSaved {path.relative_to(ROOT_DIR)}: {len(df):,} rows ({size_mb:.0f} MB)")


def main():
    if USE_SMALL:
        print(f"TEST MODE: using {RATINGS_FILE} and {LINKS_FILE}")

    movies = clean_movies()

    credits = clean_credits()
    movies = embed(movies, credits, ["cast", "crew"], "cast and crew")
    del credits

    keywords = clean_keywords()
    movies = embed(movies, keywords, ["keywords"], "keywords")
    del keywords

    movies = build_movie_documents(movies)
    save(movies, "movies.pkl")

    movie_ids = set(movies["_id"])
    del movies

    ratings = clean_ratings(movie_ids)
    save(ratings, "ratings.pkl")


if __name__ == "__main__":
    main()
