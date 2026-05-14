"""
news_parser.py — парсер новостей для HantaTracker
Источники: GDELT (агрегатор мировых СМИ) + WHO DON RSS
Запускается GitHub Actions каждые 6 часов
Сохраняет data/news.json
"""

import json
import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

# ── Настройки ─────────────────────────────────────────────────────────────────

MAX_ARTICLES = 30  # максимум статей в итоговом файле

SOURCES = {

    # GDELT — агрегирует тысячи СМИ по всему миру, бесплатный JSON API
    "GDELT": {
        "name": "Global News (GDELT)",
        "url": (
            "https://api.gdeltproject.org/api/v2/doc/doc"
            "?query=hantavirus"
            "&mode=artlist"
            "&maxrecords=25"
            "&format=json"
            "&timespan=7d"          # новости за последние 7 дней
            "&sort=DateDesc"
        ),
        "type": "gdelt",
    },

    # WHO Disease Outbreak News — официальный RSS ВОЗ
    "WHO": {
        "name": "WHO Disease Outbreak News",
        "url": "https://www.who.int/feeds/entity/csr/don/en/rss.xml",
        "type": "rss",
        "filter": "hantavirus",     # берём только статьи с этим словом
    },
}

# Иконки источников для фронтенда
SOURCE_ICONS = {
    "CDC": "🇺🇸",
    "WHO": "🌍",
    "GDELT": "📡",
    "Reuters": "📰",
    "BBC": "📺",
    "CNN": "📺",
    "Al Jazeera": "📰",
    "default": "📰",
}


# ── Парсеры ───────────────────────────────────────────────────────────────────

def fetch_gdelt() -> list[dict]:
    """GDELT отдаёт JSON с агрегированными статьями из мировых СМИ"""
    articles = []
    try:
        resp = requests.get(SOURCES["GDELT"]["url"], timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("articles", []):
            title = item.get("title", "").strip()
            if not title or "hantavirus" not in title.lower():
                continue

            source_name = item.get("domain", "Unknown")
            articles.append({
                "source_code": "GDELT",
                "source_name": source_name,
                "icon": get_icon(source_name),
                "title": title,
                "url": item.get("url", ""),
                "published_raw": item.get("seendate", ""),
                "published": format_date(item.get("seendate", "")),
                "lang": item.get("language", "English"),
                "country": item.get("sourcecountry", ""),
                "image": item.get("socialimage", ""),
            })

        print(f"  GDELT: получено {len(articles)} статей")
    except Exception as e:
        print(f"  ❌ GDELT ошибка: {e}")

    return articles


def fetch_who_rss() -> list[dict]:
    """WHO Disease Outbreak News RSS — только статьи про хантавирус"""
    articles = []
    try:
        resp = requests.get(SOURCES["WHO"]["url"], timeout=15)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # WHO использует Atom формат
        for entry in root.findall(".//item"):
            title = (entry.findtext("title") or "").strip()
            link = (entry.findtext("link") or "").strip()
            pub = (entry.findtext("pubDate") or "").strip()
            desc = (entry.findtext("description") or "").strip()

            # Фильтруем только по хантавирусу
            combined = (title + " " + desc).lower()
            if "hantavirus" not in combined and "hanta" not in combined:
                continue

            articles.append({
                "source_code": "WHO",
                "source_name": "WHO Disease Outbreak News",
                "icon": "🌍",
                "title": title,
                "url": link,
                "published_raw": pub,
                "published": format_date_rss(pub),
                "lang": "English",
                "country": "Global",
                "image": "",
            })

        print(f"  WHO RSS: получено {len(articles)} статей")
    except Exception as e:
        print(f"  ❌ WHO RSS ошибка: {e}")

    return articles


# ── Утилиты ───────────────────────────────────────────────────────────────────

def get_icon(source_name: str) -> str:
    for key, icon in SOURCE_ICONS.items():
        if key.lower() in source_name.lower():
            return icon
    return SOURCE_ICONS["default"]


def format_date(gdelt_date: str) -> str:
    """GDELT формат: 20260511T120000Z"""
    try:
        dt = datetime.strptime(gdelt_date, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    except Exception:
        return gdelt_date


def format_date_rss(rss_date: str) -> str:
    """RSS формат: Mon, 11 May 2026 12:00:00 +0000"""
    try:
        dt = datetime.strptime(rss_date, "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    except Exception:
        return rss_date


def deduplicate(articles: list[dict]) -> list[dict]:
    """Убираем дубликаты по URL и похожим заголовкам"""
    seen_urls = set()
    seen_titles = set()
    result = []

    for a in articles:
        url = a.get("url", "")
        # Нормализуем заголовок для сравнения
        title_key = re.sub(r"[^a-z0-9]", "", a.get("title", "").lower())[:60]

        if url in seen_urls or title_key in seen_titles:
            continue

        seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        result.append(a)

    return result


# ── Главная функция ───────────────────────────────────────────────────────────

def fetch_repo_news() -> list[dict]:
    """Извлекает новости из репозитория kraemer-lab (результаты работы LLM по статьям)"""
    articles = []
    repo_news_url = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/news%20sources/hantavirus_results.json"
    try:
        resp = requests.get(repo_news_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data:
            if item.get("status") != "success": continue
            res = item.get("result", {})
            desc = res.get("description", "")
            if not desc:
                # Если описания нет в exposures, попробуем взять из первого exposure
                exposures = res.get("exposures", [])
                if exposures: desc = exposures[0].get("description", "")
            
            if not desc: continue

            source_url = item.get("url", "")
            source_name = source_url.split("/")[2].replace("www.", "")

            articles.append({
                "source_code": "REPO",
                "source_name": source_name,
                "icon": "🔬",
                "title": desc[:150] + "..." if len(desc) > 150 else desc,
                "url": source_url,
                "published_raw": res.get("reporting_window") or "",
                "published": res.get("reporting_window") or "May 2026",
                "lang": "English",
                "country": res.get("country", "Global"),
                "image": "",
            })
        print(f"  Repo News: получено {len(articles)} статей")
    except Exception as e:
        print(f"  ❌ Repo News ошибка: {e}")
    return articles

# ── Главная функция ───────────────────────────────────────────────────────────

def fetch_news():
    print("📰 Загрузка новостей...")

    all_articles = []

    # 1. WHO — официальный источник, приоритет
    all_articles.extend(fetch_who_rss())

    # 2. Repo News — научный анализ
    all_articles.extend(fetch_repo_news())

    # 3. GDELT — мировые СМИ
    all_articles.extend(fetch_gdelt())

    # Дедупликация
    all_articles = deduplicate(all_articles)

    # Сортировка: WHO и REPO вперёд
    def sort_key(a):
        priority = 0 if a["source_code"] == "WHO" else (1 if a["source_code"] == "REPO" else 2)
        return (priority, a.get("published_raw", ""))

    all_articles.sort(key=sort_key)
    
    # Свежие новости
    final = all_articles[:MAX_ARTICLES]

    result = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_readable": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        "total": len(final),
        "articles": final,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ data/news.json сохранён. Статей: {len(final)}")
    return result


if __name__ == "__main__":
    fetch_news()
