import os

from pymongo import MongoClient
from pymongo.database import Database


def connect() -> Database:
    client = MongoClient(
        os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )
    return client[os.getenv("MONGO_DB_NAME", "stocks_portfolio")]
