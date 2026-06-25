import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_DETAILS = os.getenv("MONGODB_URI", "")
MONGO_DB_NAME = os.getenv("MONGODB_DB_NAME", "hr_assistant_db")

client = AsyncIOMotorClient(MONGO_DETAILS)
db = client[MONGO_DB_NAME]

feedback_collection = db["feedbacks"]
search_logs_collection = db["search_logs"]
users_collection = db["users"]
tokens_collection = db["tokens"]
