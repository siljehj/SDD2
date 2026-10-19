# TDT4225 – Assignment 3: Movies dataset with MongoDB

This project uses MongoDB 7.0.1 running locally in Docker, and Python for data cleaning, insertion and queries. Each group member runs their own local database. The database is shared through code: running the insertion script gives everyone the same data.

## Database settings

All group members use the same settings, so `DbConnector.py` works for everyone without changes:

| Setting  | Value       |
| -------- | ----------- |
| Host     | `localhost` |
| Port     | `27017`     |
| Database | `movies`    |
| User     | `oscar`     |
| Password | `oscar123`  |

These credentials are only used for a local test database. Do not reuse a real password here.

---

## First-time setup

Do these steps once, the first time you set up the project on your computer.

### 1. Install Docker Desktop

Download and install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/). Open it and check that it works:

```
docker --version
```

### 2. Create and start the MongoDB container

```
docker run -d --name tdt4225-mongo -p 27017:27017 -v mongo-data:/data/db -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=admin123 mongo:7.0.1
```

This downloads MongoDB 7.0.1, starts it in the background and creates an admin user. The data is stored in the Docker volume `mongo-data`, so it is kept when the container is stopped.

Check that it is running:

```
docker ps
```

`tdt4225-mongo` should appear with status `Up`.

### 3. Create the database user

Open the Mongo shell as admin:

```
docker exec -it tdt4225-mongo mongosh -u admin -p admin123 --authenticationDatabase admin
```

Then run:

```
use movies
db.createUser({ user: "oscar", pwd: "oscar123", roles: [{ role: "readWrite", db: "movies" }] })
show users
```

Check that `oscar` has the role `readWrite` on `movies`, then type `exit`.

### 4. Clone the repository

```
git clone <repo-url>
cd <repo-folder>
```

### 5. Create the Python environment

```
conda create -n tdt4225 python=3.11
conda activate tdt4225
python -m pip install -r requirements.txt
```

Use `python -m pip`, not just `pip`. Otherwise the packages may be installed in the wrong Python installation.

### 6. Add the dataset

Download [The Movies Dataset](https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset) from Kaggle and put all the CSV files in a folder called `dataset/` in the repo root.

The `dataset/` folder is listed in `.gitignore` and must not be pushed, because `ratings.csv` is larger than GitHub's 100 MB file limit.

### 7. Test the connection

```
python example.py
```

The script should connect to `movies`, create a `Person` collection, insert and print three documents, and then drop the collection.

---

## Daily use

Do these steps every time you work on the project.

### 1. Start the database

Open Docker Desktop, then start the container if it is not already running:

```
docker start tdt4225-mongo
```

Check with `docker ps` that `tdt4225-mongo` has status `Up`.

### 2. Activate the Python environment

```
conda activate tdt4225
```

The start of the terminal line should change from `(base)` to `(tdt4225)`.

### 3. Get the latest changes from the group

```
git pull
```

### 4. Update the database

If someone has changed `clean_data.py` or `insert_data.py`, rebuild your database so it matches everyone else's:

```
python clean_data.py
python insert_data.py
```

If only `insert_data.py` has changed, you can skip `clean_data.py` and run `insert_data.py` alone.

### 5. Look at the data (optional)

To check collections or test simple queries without Python, open the Mongo shell:

```
docker exec -it tdt4225-mongo mongosh -u oscar -p oscar123 --authenticationDatabase movies movies
```

Useful commands in the shell:

```
show collections
db.<collection>.countDocuments()
db.<collection>.findOne()
```

Type `exit` to leave the shell.

### 6. Share your changes

Pull before you push, to avoid conflicts with your teammates' changes:

```
git pull
git add <files>
git commit -m "Describe what you changed"
git push
```

Use `git status` to check what will be committed. The `dataset/` and `cleaned/` folders should never appear there.

### 7. Stop the database when you are done

```
docker stop tdt4225-mongo
```

The data is kept and will be there the next time you start the container.

---

### 8. Build the database

The database is built in two steps: first the data is cleaned and saved to files, then the cleaned files are inserted into MongoDB.

```
python clean_data.py
python insert_data.py
```

- `clean_data.py` reads the CSV files in `dataset/`, cleans them and saves the result as `cleaned/movies.pkl` and `cleaned/ratings.pkl`. It prints the number of rows before and after each cleaning step.
- `insert_data.py` drops any existing `movies` and `ratings` collections, inserts the cleaned data, creates the indexes and prints the number of documents in each collection.

The `cleaned/` folder is listed in `.gitignore` and must not be pushed, since the cleaned ratings are several hundred MB. Each group member creates their own copy by running `clean_data.py`.

Inserting all 26 million ratings can take a while. Keep the computer plugged in and make sure Docker Desktop has enough memory and disk space (Settings → Resources). To test the scripts quickly first, set the test flag at the top of `clean_data.py` to use `ratings_small.csv` and `links_small.csv`, then run both scripts.

Check that the database was built correctly:

```
docker exec -it tdt4225-mongo mongosh -u oscar -p oscar123 --authenticationDatabase movies movies --eval "db.movies.countDocuments(); db.ratings.countDocuments()"
```

The database contains two collections:

| Collection | Content                                                                                                |
| ---------- | ------------------------------------------------------------------------------------------------------ |
| `movies`   | One document per movie, with `_id` = TMDB id, and genres, collection, cast, crew and keywords embedded |
| `ratings`  | One document per rating, with `userId`, `tmdbId`, `rating` and `timestamp`                             |

## Troubleshooting

| Error                                                  | Solution                                                                                            |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'pymongo'`       | Run `conda activate tdt4225`, then `python -m pip install -r requirements.txt`.                     |
| `Authentication failed`                                | Check that the values in `DbConnector.py` match the table under "Database settings".                |
| `ServerSelectionTimeoutError` or `Connection refused`  | The container is not running. Open Docker Desktop and run `docker start tdt4225-mongo`.             |
| `collection Person already exists`                     | An earlier run of `example.py` crashed before cleaning up. Run the command below.                   |
| `FileNotFoundError: cleaned/movies.pkl`                | Run `python clean_data.py` before `python insert_data.py`.                                          |
| The insertion stops or the computer runs out of memory | Close other programs, and check Docker Desktop's memory and disk limits under Settings → Resources. |

Delete a leftover Person collection:

```
docker exec -it tdt4225-mongo mongosh -u oscar -p oscar123 --authenticationDatabase movies movies --eval "db.Person.drop()"
```
