import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return _client


def get_db():
    return get_client()[os.getenv("MONGO_DB", "job_hunter")]


# Collection accessors
def jobs_col():       return get_db()["jobs"]
def config_col():     return get_db()["config"]
def profile_col():    return get_db()["profile"]
def runs_col():       return get_db()["hunt_runs"]


async def ensure_indexes():
    db = get_db()
    await db["jobs"].create_index("_id")
    await db["jobs"].create_index("score")
    await db["jobs"].create_index("source")
    await db["jobs"].create_index("applied")
    await db["jobs"].create_index("first_seen")
    await db["jobs"].create_index([("title", "text"), ("company", "text"), ("summary", "text")])
    await db["hunt_runs"].create_index("started_at")
