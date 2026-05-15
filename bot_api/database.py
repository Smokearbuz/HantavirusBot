import json
import logging
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, delete
from datetime import datetime

from bot_api.config import REDIS_URL, DATABASE_URL
from bot_api.models import Base, User, Subscription, DailyStats, NewsArticle

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # Redis (для обратной совместимости и быстрого кэша)
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        
        # SQLite (SQLAlchemy)
        self.engine = create_async_engine(DATABASE_URL)
        self.SessionLocal = async_sessionmaker(
            bind=self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )

    async def init_db(self):
        """Создание таблиц"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ── Работа с пользователями ───────────────────────────────────────────────────

    async def get_or_create_user(self, chat_id: int, username: str = None, first_name: str = None):
        async with self.SessionLocal() as session:
            result = await session.execute(select(User).where(User.chat_id == chat_id))
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(chat_id=chat_id, username=username, first_name=first_name)
                session.add(user)
                await session.commit()
            return user

    async def get_all_user_chat_ids(self) -> list[int]:
        async with self.SessionLocal() as session:
            result = await session.execute(select(User.chat_id))
            return [row[0] for row in result.all()]

    # ── Подписки ──────────────────────────────────────────────────────────────────

    async def subscribe_user(self, chat_id: int, country_iso: str):
        """Подписать пользователя на уведомления по стране"""
        user = await self.get_or_create_user(chat_id)
        
        async with self.SessionLocal() as session:
            # Проверяем, нет ли уже подписки
            result = await session.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id, 
                    Subscription.country_iso == country_iso
                )
            )
            if not result.scalar_one_or_none():
                sub = Subscription(user_id=user.id, country_iso=country_iso)
                session.add(sub)
                await session.commit()
        
        # Дублируем в Redis для быстрого доступа рассылки (опционально)
        await self.redis.sadd(f"subs:{country_iso}", str(chat_id))
        await self.redis.sadd(f"user_subs:{chat_id}", country_iso)

    async def unsubscribe_user(self, chat_id: int, country_iso: str):
        """Отписать пользователя от страны"""
        user = await self.get_or_create_user(chat_id)
        
        async with self.SessionLocal() as session:
            await session.execute(
                delete(Subscription).where(
                    Subscription.user_id == user.id, 
                    Subscription.country_iso == country_iso
                )
            )
            await session.commit()
            
        await self.redis.srem(f"subs:{country_iso}", str(chat_id))
        await self.redis.srem(f"user_subs:{chat_id}", country_iso)

    async def get_subscribers(self, country_iso: str) -> set:
        """Все chat_id подписанных на страну"""
        # Сначала пробуем Redis, если там пусто — идем в SQL
        subs = await self.redis.smembers(f"subs:{country_iso}")
        if not subs:
            async with self.SessionLocal() as session:
                result = await session.execute(
                    select(User.chat_id).join(Subscription).where(Subscription.country_iso == country_iso)
                )
                subs = {str(row[0]) for row in result.all()}
                # Наполняем кэш
                if subs:
                    await self.redis.sadd(f"subs:{country_iso}", *subs)
        return subs

    async def get_user_subscriptions(self, chat_id: int) -> set:
        """Все ISO-коды стран на которые подписан пользователь"""
        subs = await self.redis.smembers(f"user_subs:{chat_id}")
        if not subs:
            user = await self.get_or_create_user(chat_id)
            async with self.SessionLocal() as session:
                result = await session.execute(
                    select(Subscription.country_iso).where(Subscription.user_id == user.id)
                )
                subs = {row[0] for row in result.all()}
                if subs:
                    await self.redis.sadd(f"user_subs:{chat_id}", *subs)
        return subs

    # ── Статистика и История ──────────────────────────────────────────────────────

    async def save_daily_snapshot(self, country_iso: str, total: int, deaths: int, new: int, risk: str):
        async with self.SessionLocal() as session:
            snapshot = DailyStats(
                country_iso=country_iso,
                total_cases=total,
                deaths=deaths,
                new_cases=new,
                risk_level=risk
            )
            session.add(snapshot)
            await session.commit()

    # ── Новости ───────────────────────────────────────────────────────────────────

    async def is_news_notified(self, external_id: str) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(select(NewsArticle).where(NewsArticle.external_id == external_id))
            return result.scalar_one_or_none() is not None

    async def save_news_article(self, external_id: str, title: str, link: str, published_at: datetime = None):
        async with self.SessionLocal() as session:
            article = NewsArticle(
                external_id=external_id,
                title=title,
                link=link,
                published_at=published_at,
                notified=True
            )
            session.add(article)
            await session.commit()

    # ── Кэш предыдущих данных (Redis) ─────────────────────────────────────────────

    async def get_prev_stats(self) -> dict | None:
        raw = await self.redis.get("prev_stats")
        if raw:
            return json.loads(raw)
        return None

    async def save_prev_stats(self, stats: dict):
        await self.redis.set("prev_stats", json.dumps(stats, ensure_ascii=False))

    # ── Утилита ───────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            await self.redis.ping()
            async with self.SessionLocal() as session:
                await session.execute(select(1))
            return True
        except Exception:
            return False

db = Database()