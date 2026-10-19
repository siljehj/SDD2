"""
Insert the cleaned data into MongoDB (TDT4225).

Input:  cleaned/movies.pkl and cleaned/ratings.pkl (made by clean_data.py)
Output: the collections movies and ratings in the database from DbConnector

Steps:
  1. drop the movies and ratings collections (so the script can be rerun)
  2. insert movies, then ratings, in batches of 50,000 with insert_many
  3. create a text index on overview + tagline (movies) and an index on
     userId (ratings)
  4. print the number of documents and one example movie

Run from anywhere:  python insert_data.py
"""

import time
from pathlib import Path
from pprint import pprint

import numpy as np
import pandas as pd
from pymongo import ASCENDING, TEXT

from DbConnector import DbConnector


ROOT_DIR = Path(__file__).resolve().parent
CLEANED_DIR = ROOT_DIR / "cleaned"

BATCH_SIZE = 50_000


# --- Helpers -----------------------------------------------------------------

def to_mongo_value(value):
    """
    Convert one value from pandas to a type pymongo can store.

    - lists and dicts (the embedded documents) are kept as they are
    - pandas missing values (NaN, NaT, pd.NA) become None, stored as null
    - pandas Timestamps become Python datetime objects (stored as ISODate)
    - numpy numbers (e.g. numpy.int64) become plain Python numbers
    """
    if isinstance(value, (list, dict)):
        return value
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        return value.item()
    return value


def insert_in_batches(collection, documents, total):
    """Insert documents (an iterator of batches) with insert_many, printing progress."""
    start = time.perf_counter()
    inserted = 0
    for batch in documents:
        # ordered=False lets MongoDB insert the batch without stopping at the
        # first error, which is also faster.
        collection.insert_many(batch, ordered=False)
        inserted += len(batch)
        print(f"  {collection.name}: {inserted:,} / {total:,} "
              f"({time.perf_counter() - start:.0f} s)", end="\r", flush=True)
    print()


# --- Steps -------------------------------------------------------------------

def drop_collections(db):
    """Drop the movies and ratings collections so the script can be rerun."""
    for name in ["movies", "ratings"]:
        db.drop_collection(name)
        print(f"Dropped collection {name} (if it existed)")


def movie_batches(movies):
    """Yield the movies as lists of documents, BATCH_SIZE at a time."""
    for start in range(0, len(movies), BATCH_SIZE):
        records = movies.iloc[start:start + BATCH_SIZE].to_dict("records")
        yield [{key: to_mongo_value(v) for key, v in doc.items()} for doc in records]


def insert_movies(db):
    """Load cleaned/movies.pkl and insert one document per movie (_id = TMDB id)."""
    movies = pd.read_pickle(CLEANED_DIR / "movies.pkl")
    print(f"\nInserting {len(movies):,} movies...")
    insert_in_batches(db["movies"], movie_batches(movies), len(movies))


def rating_batches(ratings):
    """
    Yield the ratings as lists of documents, BATCH_SIZE at a time.

    _id = {userId, tmdbId} makes each (user, movie) pair unique. userId and
    tmdbId are also stored as normal fields, so they can be indexed and
    queried directly. The columns are converted with tolist(), which gives
    plain Python types quickly (no loop over values in pandas).
    """
    for start in range(0, len(ratings), BATCH_SIZE):
        batch = ratings.iloc[start:start + BATCH_SIZE]
        users = batch["userId"].tolist()
        movies = batch["tmdbId"].tolist()
        values = batch["rating"].tolist()
        # Timestamps become Python datetime objects (stored as ISODate, UTC).
        # numpy's datetime64 with microsecond precision converts to datetime
        # directly with tolist().
        times = batch["timestamp"].to_numpy().astype("datetime64[us]").tolist()
        yield [{"_id": {"userId": u, "tmdbId": m},
                "userId": u, "tmdbId": m, "rating": r, "timestamp": t}
               for u, m, r, t in zip(users, movies, values, times)]


def insert_ratings(db):
    """Load cleaned/ratings.pkl and insert one document per rating."""
    ratings = pd.read_pickle(CLEANED_DIR / "ratings.pkl")
    print(f"\nInserting {len(ratings):,} ratings...")
    insert_in_batches(db["ratings"], rating_batches(ratings), len(ratings))


def create_indexes(db):
    """Create a text index on overview + tagline, and an index on ratings.userId."""
    print("\nCreating indexes...")
    db["movies"].create_index([("overview", TEXT), ("tagline", TEXT)],
                              name="overview_tagline_text")
    db["ratings"].create_index([("userId", ASCENDING)], name="userId")
    for name in ["movies", "ratings"]:
        print(f"  {name}: {list(db[name].index_information())}")


def print_summary(db):
    """Print the number of documents per collection and one example movie."""
    print("\nDocuments per collection:")
    for name in ["movies", "ratings"]:
        print(f"  {name}: {db[name].count_documents({}):,}")

    # Show only the first few cast/crew/keywords so the example stays readable.
    example = db["movies"].find_one(
        {"_id": 862},  # Toy Story
        {"cast": {"$slice": 2}, "crew": {"$slice": 2}, "keywords": {"$slice": 3}})
    print("\nExample movie document (cast, crew and keywords shortened):")
    pprint(example, sort_dicts=False, width=100)


# --- Main --------------------------------------------------------------------

def main():
    connection = DbConnector()
    db = connection.db
    try:
        drop_collections(db)
        insert_movies(db)
        insert_ratings(db)
        create_indexes(db)
        print_summary(db)
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()
