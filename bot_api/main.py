import json
import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bot_api.config import STATS_PATH, WEBHOOK_SECRET
from bot_api.database import db

logger = logging.getLogger(__name__)

app = FastAPI(title="HantaTracker API", version="1.0.0")

# CORS — разрешаем фронтенду на Cloudflare Pages делать запросы
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # в проде замени на ["https://hantavirus-bot.pages.dev"]
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Эндпоинты данных ──────────────────────────────────────────────────────────

@app.get("/stats")
async def get_stats():
    """Отдаёт весь stats.json фронтенду"""
    path = Path(STATS_PATH)
    if not path.exists():
        raise HTTPException(status_code=503, detail="Данные ещё не загружены")
    with open(path, encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.get("/stats/{iso}")
async def get_country_stats(iso: str):
    """Данные по конкретной стране"""
    path = Path(STATS_PATH)
    if not path.exists():
        raise HTTPException(status_code=503, detail="Данные ещё не загружены")
    with open(path, encoding="utf-8") as f:
        stats = json.load(f)
    iso_upper = iso.upper()
    country = next((c for c in stats.get("countries", []) if c["iso"] == iso_upper), None)
    if not country:
        raise HTTPException(status_code=404, detail=f"Страна {iso} не найдена")
    return JSONResponse(content=country)


# ── Подписки (fallback если WebApp data не работает) ─────────────────────────

class SubscribeRequest(BaseModel):
    user_id: int
    country_iso: str
    country_name: str = ""
    subscribed: bool


@app.post("/subscribe")
async def subscribe(req: SubscribeRequest):
    if req.subscribed:
        await db.subscribe_user(req.user_id, req.country_iso.upper())
        return {"status": "subscribed", "country": req.country_iso}
    else:
        await db.unsubscribe_user(req.user_id, req.country_iso.upper())
        return {"status": "unsubscribed", "country": req.country_iso}


@app.get("/subscriptions/{user_id}")
async def get_subscriptions(user_id: int):
    subs = await db.get_user_subscriptions(user_id)
    return {"user_id": user_id, "subscriptions": list(subs)}


# ── Webhook от GitHub Actions ─────────────────────────────────────────────────

@app.post("/webhook/update")
async def webhook_update(request: Request):
    """
    GitHub Actions вызывает этот эндпоинт после обновления stats.json.
    Бот читает новые данные и рассылает уведомления.
    """
    # Простая защита секретом
    secret = request.headers.get("X-Webhook-Secret", "")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    path = Path(STATS_PATH)
    if not path.exists():
        raise HTTPException(status_code=503, detail="stats.json не найден")

    with open(path, encoding="utf-8") as f:
        stats = json.load(f)

    # Запускаем рассылку асинхронно (не блокируем ответ)
    from bot_api.bot import send_notifications
    asyncio.create_task(send_notifications(stats))

    return {"status": "ok", "total": stats["global"]["total"]}


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    redis_ok = await db.ping()
    path = Path(STATS_PATH)
    return {
        "status": "ok",
        "redis": redis_ok,
        "stats_file": path.exists(),
    }