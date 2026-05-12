from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from bot_api.config import STATS_PATH

app = FastAPI()

# Разрешаем запросы с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/stats")
async def get_stats():
    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/health")
async def health():
    return {"status": "ok"}