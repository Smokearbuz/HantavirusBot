import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

from bot_api.config import STATS_PATH, NEWS_PATH, WEBHOOK_SECRET
from bot_api.database import db

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте: инициализируем БД
    try:
        await db.init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    yield
    # При выключении: закрываем соединения если нужно

app = FastAPI(title="HantaTracker API", version="1.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Эндпоинты данных ──────────────────────────────────────────────────────────

@app.get("/stats")
async def get_stats():
    path = Path(STATS_PATH)
    if not path.exists():
        raise HTTPException(status_code=503, detail="Данные ещё не загружены")
    with open(path, encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))

@app.get("/stats/{iso}")
async def get_country_stats(iso: str):
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

@app.get("/news")
async def get_news():
    path = Path(NEWS_PATH)
    if not path.exists():
        raise HTTPException(status_code=503, detail="Новости ещё не загружены")
    with open(path, encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))

# ── Подписки ──────────────────────────────────────────────────────────────────

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
    secret = request.headers.get("X-Webhook-Secret", "")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Читаем статс
    s_path = Path(STATS_PATH)
    if not s_path.exists():
        raise HTTPException(status_code=503, detail="stats.json не найден")
    with open(s_path, encoding="utf-8") as f:
        stats = json.load(f)

    # Читаем новости (для рассылки новых новостей)
    n_path = Path(NEWS_PATH)
    news = []
    if n_path.exists():
        with open(n_path, encoding="utf-8") as f:
            news = json.load(f)

    # Запускаем рассылку асинхронно
    from bot_api.bot import process_updates
    asyncio.create_task(process_updates(stats, news))

    return {"status": "ok", "total": stats["global"]["total"]}

# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    db_ok = await db.ping()
    return {
        "status": "ok",
        "database": db_ok,
        "stats_file": Path(STATS_PATH).exists(),
    }

app.mount("/", StaticFiles(directory="webapp-static", html=True), name="static")