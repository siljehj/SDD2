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
