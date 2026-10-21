import sys
import time
from collections import Counter
from itertools import combinations
from pathlib import Path
from pprint import pprint

from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from DbConnector import DbConnector


# Settings

MIN_DIRECTOR_MOVIES = 5      # Task 1
MIN_CO_APPEARANCES = 3       # Task 2
SHOW_PAIRS = 20              # Task 2
MAX_BILLING = None           # Task 2 (None = all cast)
MIN_ACTOR_MOVIES = 10        # Task 3
MIN_COLLECTION_MOVIES = 3    # Task 4
TOP_BILLED = 5               # Task 6
MIN_NOIR_VOTES = 50          # Task 7
MIN_PAIR_FILMS = 3           # Task 8
MIN_PAIR_VOTES = 100         # Task 8
MIN_USER_RATINGS = 20        # Task 10

FEMALE, MALE = 1, 2

DATE_FORMAT = "%Y-%m-%d"

PLAIN_NUMBERS = {"userId", "year"}


# Helpers

def format_value(key, value, decimals):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or key in PLAIN_NUMBERS:
        return value
    if key.endswith("_pct"):
        return f"{value:.1f} %"
    if isinstance(value, float) and not (value.is_integer() and abs(value) >= 1000):
        return f"{value:,.{decimals}f}"
    return f"{int(value):,}"


def column_decimals(rows, key):
    floats = [r.get(key) for r in rows if isinstance(r.get(key), float)]
    return 3 if floats and all(abs(v) <= 1 for v in floats) else 2


def show(title, rows):
    print(f"\n{title}")
    if not rows:
        print("  (no results)")
        return
    headers = list(rows[0])
    decimals = {k: column_decimals(rows, k) for k in headers}
    table = [[format_value(k, row.get(k), decimals[k]) for k in headers] for row in rows]
    align = ["right" if any(isinstance(r.get(k), (int, float)) for r in rows) else "left"
             for k in headers]
    print(tabulate(table, headers=headers, tablefmt="psql", colalign=align,
                   disable_numparse=True, missingval="-"))
    print()
    pprint(rows, sort_dicts=False, width=120)


def median_of(field):
    return {"$median": {"input": field, "method": "approximate"}}


def decade_of(date_field):
    return {"$multiply": [{"$floor": {"$divide": [{"$year": date_field}, 10]}}, 10]}


def date_string(date_field):
    return {"$dateToString": {"date": date_field, "format": DATE_FORMAT}}


def directors_of():
    return {"$setUnion": [{"$map": {
        "input": {"$filter": {"input": "$crew", "as": "c",
                              "cond": {"$eq": ["$$c.job", "Director"]}}},
        "in": {"id": "$$this.id", "name": "$$this.name"}}}]}


# Tasks

def task_1(db):
    pipeline = [
        {"$project": {"revenue": 1, "vote_average": 1, "directors": directors_of()}},
        {"$unwind": "$directors"},
        {"$group": {"_id": "$directors.id",
                    "director": {"$first": "$directors.name"},
                    "movie_count": {"$sum": 1},
                    "with_revenue": {"$sum": {"$cond": [{"$eq": ["$revenue", None]}, 0, 1]}},
                    "median_revenue": median_of("$revenue"),
                    "mean_vote_average": {"$avg": "$vote_average"}}},
        {"$match": {"movie_count": {"$gte": MIN_DIRECTOR_MOVIES},
                    "median_revenue": {"$ne": None}}},
        {"$sort": {"median_revenue": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "director": 1, "movie_count": 1, "with_revenue": 1,
                      "median_revenue": 1,
                      "mean_vote_average": {"$round": ["$mean_vote_average", 2]}}},
    ]
    show("Task 1: Top 10 directors by median revenue (>= 5 movies)",
         list(db.movies.aggregate(pipeline)))


def count_pairs(movies, min_count):
    actor_movies = Counter(a for actors, _ in movies for a in actors)
    movies = [([a for a in actors if actor_movies[a] >= min_count], vote)
              for actors, vote in movies]

    pair_counts = Counter()
    for actors, _ in movies:
        pair_counts.update(combinations(actors, 2))
    pairs = {p: [n, 0.0, 0] for p, n in pair_counts.items() if n >= min_count}
    del pair_counts

    for actors, vote in movies:
        if vote is None:
            continue
        for p in combinations(actors, 2):
            stats = pairs.get(p)
            if stats:
                stats[1] += vote
                stats[2] += 1
    return pairs


def task_2(db):
    cast = "$cast" if MAX_BILLING is None else {
        "$filter": {"input": "$cast", "cond": {"$lt": ["$$this.order", MAX_BILLING]}}}
    pipeline = [
        {"$match": {"cast.1": {"$exists": True}}},
        {"$project": {"_id": 0, "vote_average": 1,
                      "cast": {"$map": {"input": cast,
                                        "in": {"id": "$$this.id", "name": "$$this.name"}}}}},
    ]
    names = {}
    movies = []
    for doc in db.movies.aggregate(pipeline, allowDiskUse=True):
        for c in doc["cast"]:
            names.setdefault(c["id"], c["name"])
        actors = sorted({c["id"] for c in doc["cast"]})
        movies.append((actors, doc.get("vote_average")))

    pairs = count_pairs(movies, MIN_CO_APPEARANCES)
    rows = [{"actor_1": names[a], "actor_2": names[b], "co_appearances": n,
             "avg_vote_average": round(vote_sum / vote_n, 2) if vote_n else None}
            for (a, b), (n, vote_sum, vote_n) in pairs.items()]
    rows.sort(key=lambda r: (-r["co_appearances"], r["actor_1"], r["actor_2"]))

    show(f"Task 2: Top {SHOW_PAIRS} actor pairs by co-appearances", rows[:SHOW_PAIRS])
    print(f"\nTotal number of actor pairs with >= {MIN_CO_APPEARANCES} co-appearances: "
          f"{len(rows):,}")
    return rows


def task_3(db):
    pipeline = [
        {"$project": {"genres": "$genres.name",
                      "cast": {"$setUnion": [{"$map": {
                          "input": "$cast",
                          "in": {"id": "$$this.id", "name": "$$this.name"}}}]}}},
        {"$unwind": "$cast"},
        {"$group": {"_id": "$cast.id",
                    "actor": {"$first": "$cast.name"},
                    "movie_count": {"$sum": 1},
                    "genre_lists": {"$push": "$genres"}}},
        {"$match": {"movie_count": {"$gte": MIN_ACTOR_MOVIES}}},
        {"$project": {"_id": 0, "actor": 1, "movie_count": 1,
                      "genres": {"$reduce": {"input": "$genre_lists", "initialValue": [],
                                             "in": {"$setUnion": ["$$value", "$$this"]}}}}},
        {"$addFields": {"genre_count": {"$size": "$genres"}}},
        {"$sort": {"genre_count": -1, "movie_count": -1, "actor": 1}},
        {"$limit": 10},
        {"$project": {"actor": 1, "movie_count": 1, "genre_count": 1,
                      "example_genres": {"$slice": ["$genres", 5]}}},
    ]
    show("Task 3: Top 10 actors by genre breadth (>= 10 movies)",
         list(db.movies.aggregate(pipeline, allowDiskUse=True)))


def task_4(db):
    pipeline = [
        {"$match": {"belongs_to_collection.name": {"$ne": None}}},
        {"$group": {"_id": "$belongs_to_collection.id",
                    "collection": {"$first": "$belongs_to_collection.name"},
                    "movie_count": {"$sum": 1},
                    "total_revenue": {"$sum": "$revenue"},
                    "median_vote_average": median_of("$vote_average"),
                    "earliest": {"$min": "$release_date"},
                    "latest": {"$max": "$release_date"}}},
        {"$match": {"movie_count": {"$gte": MIN_COLLECTION_MOVIES}}},
        {"$sort": {"total_revenue": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "collection": "$collection", "movies": "$movie_count",
                      "total_revenue": "$total_revenue", "median_vote": "$median_vote_average",
                      "released": {"$concat": [date_string("$earliest"), " -> ",
                                               date_string("$latest")]}}},
    ]
    show("Task 4: Top 10 collections by total revenue (>= 3 movies)",
         list(db.movies.aggregate(pipeline)))


def task_5(db):
    pipeline = [
        {"$match": {"release_date": {"$ne": None}, "runtime": {"$ne": None},
                    "genres.0": {"$exists": True}}},
        {"$group": {"_id": {"decade": decade_of("$release_date"),
                            "genre": {"$arrayElemAt": ["$genres.name", 0]}},
                    "median_runtime": median_of("$runtime"),
                    "movie_count": {"$sum": 1}}},
        {"$sort": {"_id.decade": -1, "median_runtime": -1}},
        {"$project": {"_id": 0,
                      "decade": {"$concat": [{"$toString": {"$toInt": "$_id.decade"}}, "s"]},
                      "primary_genre": "$_id.genre",
                      "median_runtime": "$median_runtime",
                      "movie_count": "$movie_count"}},
    ]
    show("Task 5: Median runtime by decade and primary genre",
         list(db.movies.aggregate(pipeline)))


def task_6(db):
    top_cast = {"$slice": [{"$sortArray": {"input": "$cast", "sortBy": {"order": 1}}},
                           TOP_BILLED]}
    pipeline = [
        {"$match": {"release_date": {"$ne": None}, "cast.0": {"$exists": True}}},
        {"$project": {
            "decade": decade_of("$release_date"),
            "people": {"$filter": {
                "input": {"$setUnion": [{"$map": {
                    "input": top_cast, "in": {"id": "$$this.id", "gender": "$$this.gender"}}}]},
                "cond": {"$in": ["$$this.gender", [FEMALE, MALE]]}}}}},
        {"$match": {"people.0": {"$exists": True}}},
        {"$project": {"decade": 1,
                      "female_share": {"$divide": [
                          {"$size": {"$filter": {"input": "$people",
                                                 "cond": {"$eq": ["$$this.gender", FEMALE]}}}},
                          {"$size": "$people"}]}}},
        {"$group": {"_id": "$decade",
                    "avg_female_share": {"$avg": "$female_share"},
                    "movie_count": {"$sum": 1}}},
        {"$sort": {"avg_female_share": -1}},
        {"$project": {"_id": 0,
                      "decade": {"$concat": [{"$toString": {"$toInt": "$_id"}}, "s"]},
                      "avg_female_pct": {"$round": [
                          {"$multiply": ["$avg_female_share", 100]}, 1]},
                      "movie_count": "$movie_count"}},
    ]
    show(f"Task 6: Female share of the top {TOP_BILLED} billed cast, by decade",
         list(db.movies.aggregate(pipeline)))


def task_7(db):
    pipeline = [
        {"$match": {"$text": {"$search": "noir"}, "vote_count": {"$gte": MIN_NOIR_VOTES}}},
        {"$sort": {"vote_average": -1, "vote_count": -1}},
        {"$limit": 20},
        {"$project": {"_id": 0, "title": "$title", "year": {"$year": "$release_date"},
                      "vote_average": "$vote_average", "vote_count": "$vote_count"}},
    ]
    show("Task 7: Top 20 noir / neo-noir movies (vote_count >= 50)",
         list(db.movies.aggregate(pipeline)))


def task_8(db):
    pipeline = [
        {"$match": {"vote_count": {"$gte": MIN_PAIR_VOTES}}},
        {"$project": {
            "vote_average": 1, "revenue": 1,
            "directors": directors_of(),
            "actors": {"$setUnion": [{"$map": {
                "input": "$cast", "in": {"id": "$$this.id", "name": "$$this.name"}}}]}}},
        {"$unwind": "$directors"},
        {"$unwind": "$actors"},
        {"$match": {"$expr": {"$ne": ["$directors.id", "$actors.id"]}}},
        {"$group": {"_id": {"director": "$directors.id", "actor": "$actors.id"},
                    "director": {"$first": "$directors.name"},
                    "actor": {"$first": "$actors.name"},
                    "films": {"$sum": 1},
                    "mean_vote_average": {"$avg": "$vote_average"},
                    "mean_revenue": {"$avg": "$revenue"}}},
        {"$match": {"films": {"$gte": MIN_PAIR_FILMS}}},
        {"$sort": {"mean_vote_average": -1, "films": -1}},
        {"$limit": 20},
        {"$project": {"_id": 0, "director": 1, "actor": 1, "films": 1,
                      "mean_vote_average": {"$round": ["$mean_vote_average", 2]},
                      "mean_revenue": {"$round": ["$mean_revenue", 0]}}},
    ]
    show("Task 8: Top 20 director-actor pairs by mean vote_average",
         list(db.movies.aggregate(pipeline, allowDiskUse=True)))


def task_9(db):
    pipeline = [
        {"$match": {"original_language": {"$nin": ["en", None]},
                    "production_countries.iso_3166_1": "US"}},
        {"$group": {"_id": "$original_language",
                    "count": {"$sum": 1},
                    "example_title": {"$first": "$title"}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "language": "$_id", "count": "$count",
                      "example_title": "$example_title"}},
    ]
    show("Task 9: Top 10 non-English original languages in US productions",
         list(db.movies.aggregate(pipeline)))


def genre_masks(db):
    bit = {}
    masks = {}
    for doc in db.movies.find({}, {"genres.name": 1}):
        mask = 0
        for g in doc["genres"]:
            mask |= 1 << bit.setdefault(g["name"], len(bit))
        masks[doc["_id"]] = mask
    return masks


def user_stats(users, masks):
    rows = []
    for u in users:
        mask = 0
        for movie in u["movies"]:
            mask |= masks.get(movie, 0)
        rows.append({"userId": u["_id"], "ratings": u["count"],
                     "variance": round(u["variance"], 3),
                     "distinct_genres": bin(mask).count("1")})
    return rows


def task_10(db):
    masks = genre_masks(db)
    pipeline = [
        {"$project": {"_id": 0, "userId": 1, "tmdbId": 1, "rating": 1}},
        {"$group": {"_id": "$userId",
                    "count": {"$sum": 1},
                    "std": {"$stdDevPop": "$rating"},
                    "movies": {"$push": "$tmdbId"}}},
        {"$project": {"count": 1, "movies": 1, "variance": {"$pow": ["$std", 2]}}},
    ]
    print("\nTask 10: grouping all ratings by user (this takes a few minutes)...")
    all_users = user_stats(db.ratings.aggregate(pipeline, allowDiskUse=True), masks)
    rows = [r for r in all_users if r["ratings"] >= MIN_USER_RATINGS]
    print(f"\nTotal number of users: {len(all_users):,}")
    print(f"Users with >= {MIN_USER_RATINGS} ratings: {len(rows):,}")

    by_genres = sorted(rows, key=lambda r: (-r["distinct_genres"], -r["ratings"], r["userId"]))
    top = by_genres[0]["distinct_genres"]
    ties = sum(r["distinct_genres"] == top for r in rows)
    show(f"Task 10a: Top 10 most genre-diverse users ({ties:,} users share the max of "
         f"{top} genres; ties broken by ratings count)", by_genres[:10])

    by_variance = sorted(rows, key=lambda r: (-r["variance"], -r["ratings"], r["userId"]))
    show("Task 10b: Top 10 highest-variance users", by_variance[:10])


# Main

TASKS = {1: task_1, 2: task_2, 3: task_3, 4: task_4, 5: task_5,
         6: task_6, 7: task_7, 8: task_8, 9: task_9, 10: task_10}


def main():
    selected = [int(a) for a in sys.argv[1:]] or list(TASKS)
    connection = DbConnector()
    db = connection.db
    try:
        for number in selected:
            start = time.perf_counter()
            TASKS[number](db)
            print(f"  (task {number}: {time.perf_counter() - start:.1f} s)")
    finally:
        connection.close_connection()


if __name__ == "__main__":
    main()