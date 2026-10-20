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
    start = time.perf_counter()
    inserted = 0
    for batch in documents:
        collection.insert_many(batch, ordered=False)
        inserted += len(batch)
        print(f"  {collection.name}: {inserted:,} / {total:,} "
              f"({time.perf_counter() - start:.0f} s)", end="\r", flush=True)
    print()


# --- Steps -------------------------------------------------------------------

def drop_collections(db):
    for name in ["movies", "ratings"]:
        db.drop_collection(name)
        print(f"Dropped collection {name} (if it existed)")


def movie_batches(movies):
    for start in range(0, len(movies), BATCH_SIZE):
        records = movies.iloc[start:start + BATCH_SIZE].to_dict("records")
        yield [{key: to_mongo_value(v) for key, v in doc.items()} for doc in records]


def insert_movies(db):
    movies = pd.read_pickle(CLEANED_DIR / "movies.pkl")
    print(f"\nInserting {len(movies):,} movies...")
    insert_in_batches(db["movies"], movie_batches(movies), len(movies))


def rating_batches(ratings):
    for start in range(0, len(ratings), BATCH_SIZE):
        batch = ratings.iloc[start:start + BATCH_SIZE]
        users = batch["userId"].tolist()
        movies = batch["tmdbId"].tolist()
        values = batch["rating"].tolist()
        times = batch["timestamp"].to_numpy().astype("datetime64[us]").tolist()
        yield [{"_id": {"userId": u, "tmdbId": m},
                "userId": u, "tmdbId": m, "rating": r, "timestamp": t}
               for u, m, r, t in zip(users, movies, values, times)]


def insert_ratings(db):
    ratings = pd.read_pickle(CLEANED_DIR / "ratings.pkl")
    print(f"\nInserting {len(ratings):,} ratings...")
    insert_in_batches(db["ratings"], rating_batches(ratings), len(ratings))


def create_indexes(db):
    print("\nCreating indexes...")
    db["movies"].create_index([("overview", TEXT), ("tagline", TEXT)],
                              name="overview_tagline_text")
    db["ratings"].create_index([("userId", ASCENDING)], name="userId")
    for name in ["movies", "ratings"]:
        print(f"  {name}: {list(db[name].index_information())}")


def print_summary(db):
    print("\nDocuments per collection:")
    for name in ["movies", "ratings"]:
        print(f"  {name}: {db[name].count_documents({}):,}")

    example = db["movies"].find_one(
        {"_id": 862},  
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
