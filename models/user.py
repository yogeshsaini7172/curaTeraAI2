from pymongo import MongoClient

# Re-use the local MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["schemeDatabase"]
users_collection = db["users"]
