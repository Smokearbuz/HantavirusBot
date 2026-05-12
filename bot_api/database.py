import json
import redis.asyncio as redis
from bot_api.config import REDIS_URL


class Database:
    def __init__(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)

    # ── Подписки ──────────────────────────────────────────────────────────────

    async def subscribe_user(self, chat_id: int, country_iso: str):
        """Подписать пользователя на уведомления по стране (ISO-код)"""
        await self.redis.sadd(f"subs:{country_iso}", str(chat_id))
        # Запомнить список стран юзера (для страницы "Мои подписки")
        await self.redis.sadd(f"user_subs:{chat_id}", country_iso)

    async def unsubscribe_user(self, chat_id: int, country_iso: str):
        """Отписать пользователя от страны"""
        await self.redis.srem(f"subs:{country_iso}", str(chat_id))
        await self.redis.srem(f"user_subs:{chat_id}", country_iso)

    async def get_subscribers(self, country_iso: str) -> set:
        """Все chat_id подписанных на страну"""
        return await self.redis.smembers(f"subs:{country_iso}")

    async def get_user_subscriptions(self, chat_id: int) -> set:
        """Все ISO-коды стран на которые подписан пользователь"""
        return await self.redis.smembers(f"user_subs:{chat_id}")

    async def is_subscribed(self, chat_id: int, country_iso: str) -> bool:
        """Проверить подписку"""
        return await self.redis.sismember(f"subs:{country_iso}", str(chat_id))

    # ── Кэш предыдущих данных (для отслеживания дельты) ───────────────────────

    async def get_prev_stats(self) -> dict | None:
        """Получить предыдущий снимок stats.json для сравнения"""
        raw = await self.redis.get("prev_stats")
        if raw:
            return json.loads(raw)
        return None

    async def save_prev_stats(self, stats: dict):
        """Сохранить текущий снимок как 'предыдущий' после рассылки"""
        await self.redis.set("prev_stats", json.dumps(stats, ensure_ascii=False))

    # ── Утилита ───────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            return await self.redis.ping()
        except Exception:
            return False


db = Database()