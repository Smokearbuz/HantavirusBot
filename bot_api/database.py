import redis.asyncio as redis
from bot_api.config import REDIS_URL

class Database:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)

    async def subscribe_user(self, chat_id, country):
        """Подписать пользователя на уведомления по стране"""
        await self.redis.sadd(f"subs:{country}", chat_id)

    async def unsubscribe_user(self, chat_id, country):
        """Отписать пользователя"""
        await self.redis.srem(f"subs:{country}", chat_id)

    async def get_subscribers(self, country):
        """Получить список ID всех подписанных на страну"""
        return await self.redis.smembers(f"subs:{country}")

db = Database()