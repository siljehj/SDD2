# ----- timestamp ----
# movies_metadata.release_date and ratings.timestamp (and ratings_small)
# need need to have them same timestamp (as described in the assignemnt sheet). 
# Convert both fields to the same datetime type:
# pd.to_datetime(df["release_date"], errors="coerce"). Bad values become NaT (missing), which you can drop or store as null.
# pd.to_datetime(df["timestamp"], unit="s") for the ratings files.


# ----- HUSK -----
# Note: For initial testing or development, you may use ratings_small.csv and links_small.csv.
# However, your finalsolution and delivery should be designed to handle the full ratings.csv and
# links.csv datasets.