import time
from collections import Counter
import pandas as pd

from eda_overview import load_csv, print_section
from eda_movies import parse_nested, percent, print_table

GENDER_LABELS = {0: "0 (unknown)", 1: "1 (female)", 2: "2 (male)"}


# --- Helpers ----------------------------------------------------------------

def load_movie_ids():
    """Return the set of numeric ids in movies_metadata.csv."""
    movies = load_csv("movies_metadata.csv")
    ids = pd.to_numeric(movies["id"], errors="coerce").dropna().astype(int)
    return set(ids)


def parse_columns(df, columns):
    """Add a parsed copy (<col>_parsed) of each nested column."""
    for col in columns:
        print(f"Parsing {col}...", flush=True)
        start = time.perf_counter()
        df[f"{col}_parsed"] = df[col].apply(parse_nested)
        print(f"Parsed in {time.perf_counter() - start:.1f} s")
    return df


def check_ids(df, raw_columns, movie_ids, title):
    """Print duplicate ids, identical duplicates, and ids found / not found in movies."""
    print_section(title)
    total = len(df)
    extra_rows = df["id"].duplicated().sum()
    identical = df[raw_columns].duplicated().sum()
    unique_ids = df["id"].drop_duplicates()
    in_movies = unique_ids.isin(movie_ids).sum()

    print_table([
        ["Rows", total, ""],
        ["Ids that occur more than once", df.loc[df["id"].duplicated(), "id"].nunique(), ""],
        ["Extra rows caused by duplicate ids", extra_rows, percent(extra_rows, total)],
        ["... of which fully identical rows", identical, ""],
        ["Distinct ids", len(unique_ids), ""],
        ["Distinct ids found in movies_metadata", in_movies,
         percent(in_movies, len(unique_ids))],
        ["Distinct ids NOT in movies_metadata", len(unique_ids) - in_movies,
         percent(len(unique_ids) - in_movies, len(unique_ids))],
    ], headers=["Measure", "Count", "Percent"])


def count_empty_lists(df, columns, title):
    """Print how many rows have an empty list in each of the given columns."""
    print_section(title)
    table = []
    for col in columns:
        parsed = df[f"{col}_parsed"]
        empty = parsed.apply(lambda v: v == []).sum()
        unparsed = parsed.isna().sum()
        table.append([col, empty, percent(empty, len(df)), unparsed])
    print_table(table, headers=["Column", "Empty []", "Percent", "Not parseable"])


# --- credits.csv -------------------------------------------------------------

def list_fields(df):
    """Print every field used in the cast and crew objects, and how often it occurs."""
    print_section("Credits 3. Fields in the cast and crew objects")
    for col in ["cast", "crew"]:
        keys = Counter()
        n_objects = 0
        for people in df[f"{col}_parsed"].dropna():
            for person in people:
                keys.update(person.keys())
                n_objects += 1
        print(f"\n{col} ({n_objects:,} objects):")
        print_table([[k, f"{n:,}", percent(n, n_objects)] for k, n in keys.most_common()],
                    headers=["Field", "Objects with field", "Percent"])


def summarise_sizes(df):
    """Print min, median, mean and max number of cast and crew members per movie."""
    print_section("Credits 4. Cast and crew members per movie")
    table = []
    for col in ["cast", "crew"]:
        sizes = df[f"{col}_parsed"].dropna().apply(len)
        table.append([col, sizes.min(), sizes.median(), round(sizes.mean(), 2), sizes.max()])
    print_table(table, headers=["Column", "Min", "Median", "Mean", "Max"])


def top_cast(people, n=5):
    """Return the first n cast members of a movie, sorted by their 'order' field."""
    return sorted(people, key=lambda p: p["order"])[:n]


def count_genders(df):
    """Print gender value counts for all cast members and for the top 5 per movie."""
    print_section("Credits 5. Gender of cast members")
    cast_lists = df["cast_parsed"].dropna()
    all_genders = Counter(p["gender"] for people in cast_lists for p in people)
    top_genders = Counter(p["gender"] for people in cast_lists for p in top_cast(people))

    all_total, top_total = sum(all_genders.values()), sum(top_genders.values())
    table = [[GENDER_LABELS.get(g, g),
              f"{all_genders[g]:,}", percent(all_genders[g], all_total),
              f"{top_genders[g]:,}", percent(top_genders[g], top_total)]
             for g in sorted(all_genders)]
    print_table(table, headers=["Gender", "All cast", "Percent",
                                "Top 5 per movie", "Percent"])


def count_directors(df):
    """Print the number of movies with 0, 1 and more than 1 director."""
    print_section("Credits 6. Directors per movie (crew job = 'Director')")
    crew_lists = df["crew_parsed"].dropna()
    n_directors = crew_lists.apply(lambda people: sum(p["job"] == "Director" for p in people))

    groups = {"0": (n_directors == 0).sum(),
              "1": (n_directors == 1).sum(),
              "> 1": (n_directors > 1).sum()}
    print_table([[k, v, percent(v, len(n_directors))] for k, v in groups.items()],
                headers=["Directors", "Movies", "Percent"])
    print(f"Most directors in one movie: {n_directors.max()}")


def names_with_several_ids(df, n_examples=5):
    """Count names that belong to more than one person id, for cast and crew."""
    print_section("Credits 7. Names with more than one person id")
    for col in ["cast", "crew"]:
        pairs = {(p["name"], p["id"]) for people in df[f"{col}_parsed"].dropna()
                 for p in people}
        pairs = pd.DataFrame(list(pairs), columns=["name", "id"])
        ids_per_name = pairs.groupby("name")["id"].nunique()
        shared = ids_per_name[ids_per_name > 1].sort_values(ascending=False)

        print(f"\n{col}: {len(shared):,} of {len(ids_per_name):,} names "
              f"({percent(len(shared), len(ids_per_name))}) have more than one id")
        examples = []
        for name, n_ids in shared.head(n_examples).items():
            ids = sorted(pairs.loc[pairs["name"] == name, "id"])
            examples.append([name, n_ids, ", ".join(map(str, ids[:5]))])
        print_table(examples, headers=["Name", "Ids", "First ids"])


def inspect_differing_duplicates(df):
    print_section("Credits 8. Duplicate ids with different content")

    duplicated = df[df["id"].duplicated(keep=False)]
    n_versions = duplicated.groupby("id")[["cast", "crew"]].apply(
        lambda g: len(g.drop_duplicates()))
    differing_ids = n_versions[n_versions > 1].index
    print(f"Ids with copies that differ: {len(differing_ids)}")

    for movie_id in differing_ids:
        copies = df[df["id"] == movie_id]

        people = {row: {("cast", p["id"]) for p in copy["cast_parsed"]}
                       | {("crew", p["id"]) for p in copy["crew_parsed"]}
                  for row, copy in copies.iterrows()}

        print(f"\nid {movie_id}:")
        table = []
        for row, copy in copies.iterrows():
            cast, crew = copy["cast_parsed"], copy["crew_parsed"]
            table.append([row, len(cast), len(crew),
                          len({p["id"] for p in cast}), len({p["id"] for p in crew})])
        print_table(table, headers=["Row", "Cast", "Crew",
                                    "Distinct cast ids", "Distinct crew ids"])

        rows = list(people)
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if people[a] == people[b]:
                    same_objects = all(
                        sorted(map(repr, copies.at[a, f"{col}_parsed"]))
                        == sorted(map(repr, copies.at[b, f"{col}_parsed"]))
                        for col in ["cast", "crew"])
                    detail = ("only the order of the objects differs" if same_objects
                              else "some fields differ")
                    print(f"Copies {a} and {b} contain exactly the same people ({detail})")
                elif people[b] <= people[a]:
                    print(f"Copy {a} contains all people in the other copy ({b})")
                elif people[a] <= people[b]:
                    print(f"Copy {b} contains all people in the other copy ({a})")
                else:
                    print(f"Copies contain different people: "
                          f"{len(people[a] - people[b])} only in row {a}, "
                          f"{len(people[b] - people[a])} only in row {b}")

        sizes = {row: len(c["cast_parsed"]) + len(c["crew_parsed"])
                 for row, c in copies.iterrows()}
        keep = max(sizes, key=sizes.get)
        print(f"Kept by the rule: row {keep} ({sizes[keep]} cast and crew members)")


def analyse_credits(movie_ids):
    """Run all checks on credits.csv."""
    print("=" * 80)
    print("credits.csv")
    print("=" * 80)
    df = load_csv("credits.csv")
    check_ids(df, ["cast", "crew", "id"], movie_ids,
              "Credits 1. Duplicate ids and match with movies_metadata")
    df = parse_columns(df, ["cast", "crew"])
    count_empty_lists(df, ["cast", "crew"], "Credits 2. Empty cast and crew lists")
    list_fields(df)
    summarise_sizes(df)
    count_genders(df)
    count_directors(df)
    names_with_several_ids(df)
    inspect_differing_duplicates(df)
    print()


# --- keywords.csv ------------------------------------------------------------

def analyse_keywords(movie_ids):
    """Run all checks on keywords.csv."""
    print("=" * 80)
    print("keywords.csv")
    print("=" * 80)
    df = load_csv("keywords.csv")
    check_ids(df, ["id", "keywords"], movie_ids,
              "Keywords 1. Duplicate ids and match with movies_metadata")
    df = parse_columns(df, ["keywords"])
    count_empty_lists(df, ["keywords"], "Keywords 1. Empty keyword lists")
    print()


# --- Main --------------------------------------------------------------------

def main():
    movie_ids = load_movie_ids()
    analyse_credits(movie_ids)
    analyse_keywords(movie_ids)


if __name__ == "__main__":
    main()
