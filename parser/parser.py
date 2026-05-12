import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta

CSV_URL = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/linelist/2026_hantavirus.csv"

# Флаги стран — расширяй по мере появления новых в данных
COUNTRY_FLAGS = {
    "Argentina": "🇦🇷",
    "Chile": "🇨🇱",
    "Brazil": "🇧🇷",
    "Bolivia": "🇧🇴",
    "Paraguay": "🇵🇾",
    "Uruguay": "🇺🇾",
    "Peru": "🇵🇪",
    "Switzerland": "🇨🇭",
    "Germany": "🇩🇪",
    "France": "🇫🇷",
    "United States": "🇺🇸",
    "USA": "🇺🇸",
    "Colombia": "🇨🇴",
    "Venezuela": "🇻🇪",
    "Ecuador": "🇪🇨",
}

def process_data():
    try:
        print(f"📥 Загрузка данных из {CSV_URL}...")
        df = pd.read_csv(CSV_URL)
        df.columns = [c.lower().strip() for c in df.columns]

        print(f"✅ Загружено строк: {len(df)}")
        print(f"   Колонки: {list(df.columns)}")

        # Ищем нужные колонки
        possible_country_cols = ["country", "location", "admin0", "country_name"]
        possible_date_cols = ["date_onset", "date_report", "date_confirmed", "date"]

        country_col = next((c for c in possible_country_cols if c in df.columns), None)
        status_col = "status" if "status" in df.columns else None
        outcome_col = "outcome" if "outcome" in df.columns else None
        date_col = next((c for c in possible_date_cols if c in df.columns), None)

        print(f"   Страна: {country_col}, Статус: {status_col}, Исход: {outcome_col}, Дата: {date_col}")

        # Парсим даты для дельты
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        now = datetime.utcnow()
        date_24h = now - timedelta(hours=24)
        date_7d = now - timedelta(days=7)

        def delta(df_sub, days):
            if not date_col:
                return 0
            cutoff = now - timedelta(days=days)
            return int((df_sub[date_col] >= cutoff).sum())

        total = len(df)
        confirmed = int(len(df[df[status_col] == "confirmed"])) if status_col else 0
        suspected = int(len(df[df[status_col] == "suspected"])) if status_col else 0
        deaths = int(len(df[df[outcome_col] == "deceased"])) if outcome_col else 0
        cfr = round((deaths / total * 100), 1) if total > 0 else 0.0

        stats = {
            "global": {
                "total": total,
                "confirmed": confirmed,
                "suspected": suspected,
                "deaths": deaths,
                "cfr": cfr,
                "new_24h": delta(df, 1),
                "new_7d": delta(df, 7),
                "countries_count": 0,  # заполним ниже
                "last_update": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_update_readable": now.strftime("%d.%m.%Y %H:%M UTC"),
            },
            "countries": []
        }

        if country_col:
            countries_dict = {}

            for country in df[country_col].dropna().unique():
                sub = df[df[country_col] == country]

                c_total = len(sub)
                c_confirmed = int(len(sub[sub[status_col] == "confirmed"])) if status_col else 0
                c_deaths = int(len(sub[sub[outcome_col] == "deceased"])) if outcome_col else 0
                c_cfr = round(c_deaths / c_total * 100, 1) if c_total > 0 else 0.0
                c_new_7d = delta(sub, 7)
                c_new_24h = delta(sub, 1)

                # ISO-код (упрощённый маппинг, расширяй)
                iso_map = {
                    "Argentina": "AR", "Chile": "CL", "Brazil": "BR",
                    "Bolivia": "BO", "Paraguay": "PY", "Uruguay": "UY",
                    "Peru": "PE", "Switzerland": "CH", "Germany": "DE",
                    "France": "FR", "United States": "US", "USA": "US",
                    "Colombia": "CO", "Venezuela": "VE", "Ecuador": "EC",
                }

                countries_dict[country] = {
                    "name": str(country),
                    "iso": iso_map.get(str(country), str(country)[:2].upper()),
                    "flag": COUNTRY_FLAGS.get(str(country), "🏳️"),
                    "total": c_total,
                    "confirmed": c_confirmed,
                    "suspected": c_total - c_confirmed,
                    "deaths": c_deaths,
                    "cfr": c_cfr,
                    "new_7d": c_new_7d,
                    "new_24h": c_new_24h,
                    "pct": round(c_total / total * 100, 1) if total > 0 else 0,
                }

            # Сортировка по убыванию
            sorted_countries = sorted(
                countries_dict.values(),
                key=lambda x: x["total"],
                reverse=True
            )

            # Нормализуем pct относительно лидера
            if sorted_countries:
                max_total = sorted_countries[0]["total"]
                for c in sorted_countries:
                    c["pct"] = round(c["total"] / max_total * 100, 1)

            stats["countries"] = sorted_countries
            stats["global"]["countries_count"] = len(sorted_countries)

        # Сохраняем
        os.makedirs("data", exist_ok=True)
        with open("data/stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"🚀 data/stats.json обновлён! Всего: {total}, стран: {stats['global']['countries_count']}")
        return stats

    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()

        # Заглушка чтобы фронт не падал
        os.makedirs("data", exist_ok=True)
        fallback = {
            "global": {
                "total": 0, "confirmed": 0, "suspected": 0,
                "deaths": 0, "cfr": 0.0, "new_24h": 0, "new_7d": 0,
                "countries_count": 0,
                "last_update": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_update_readable": "Ошибка загрузки данных",
            },
            "countries": []
        }
        with open("data/stats.json", "w", encoding="utf-8") as f:
            json.dump(fallback, f)
        return fallback


if __name__ == "__main__":
    process_data()