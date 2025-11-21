import motor.motor_asyncio
import os

MONGO_URL = os.environ.get("MONGO_URL")
cluster = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = cluster["ReferBotDB"]
users_collection = db["users"]

async def init_db():
    print("DB Connected")

async def add_user(user_id, referrer_id=None, refer_reward=0.05):
    user = await users_collection.find_one({"_id": user_id})
    if not user:
        new_user = {"_id": user_id, "referrer_id": referrer_id, "balance": 0.0, "referrals": 0, "task_done": 0}
        await users_collection.insert_one(new_user)
        if referrer_id:
            await users_collection.update_one({"_id": referrer_id}, {"$inc": {"balance": refer_reward, "referrals": 1}})
        return True
    return False

async def get_user_data(user_id):
    user = await users_collection.find_one({"_id": user_id})
    return (user["balance"], user["referrals"], user.get("task_done", 0)) if user else None

async def complete_task_reward(user_id, amount):
    user = await users_collection.find_one({"_id": user_id})
    if user and user.get("task_done", 0) == 0:
        await users_collection.update_one({"_id": user_id}, {"$inc": {"balance": amount}, "$set": {"task_done": 1}})
        return True
    return False

async def reduce_balance(user_id, amount):
    user = await users_collection.find_one({"_id": user_id})
    if user and user["balance"] >= amount:
        await users_collection.update_one({"_id": user_id}, {"$set": {"balance": user["balance"] - amount}})
        return user["balance"] - amount
    return None
