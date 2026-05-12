import pandas as pd
import requests
import json
import os

CSV_URL = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/linelist/2026_hantavirus.csv"

def process_data():
    try:
        print(f"📥 Загрузка данных из {CSV_URL}...")
        df = pd.read_csv(CSV_URL)
        
        # Приводим названия колонок к нижнему регистру, чтобы избежать ошибок 'Country' vs 'country'
        df.columns = [c.lower() for c in df.columns]
        
        print(f"✅ Данные загружены. Строк: {len(df)}")
        print(f"Колонки в файле: {list(df.columns)}")

        # Проверяем наличие нужных колонок, если нет 'country' — ищем похожие
        possible_country_cols: list[str] = ['country', 'location', 'admin0', 'country_name']
        country_col = next((c for c in possible_country_cols if c in df.columns), None)
        status_col = 'status' if 'status' in df.columns else None
        outcome_col = 'outcome' if 'outcome' in df.columns else None

        stats = {
            "global": {
                "total": int(len(df)),
                "confirmed": int(len(df[df[status_col] == 'confirmed'])) if status_col else 0,
                "suspected": int(len(df[df[status_col] == 'suspected'])) if status_col else 0,
                "deaths": int(len(df[df[outcome_col] == 'deceased'])) if outcome_col else 0,
                "last_update": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
            },
            "countries": {}
        }

        if country_col:
            # Группировка по странам
            counts = df.groupby(country_col).size()
            deaths = df[df[outcome_col] == 'deceased'].groupby(country_col).size() if outcome_col else pd.Series()

            for country in counts.index:
                stats["countries"][str(country)] = {
                    "total": int(counts[country]),
                    "deaths": int(deaths.get(country, 0))
                }

        # Сохранение
        os.makedirs('data', exist_ok=True)
        with open('data/stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
            
        print("🚀 Файл data/stats.json успешно обновлен!")

    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")
        # Создаем структуру-заглушку, чтобы фронтенд не выдавал SyntaxError
        os.makedirs('data', exist_ok=True)
        with open('data/stats.json', 'w', encoding='utf-8') as f:
            json.dump({"global": {"total": 0, "deaths": 0, "last_update": "Ошибка данных"}, "countries": {}}, f)

if __name__ == "__main__":
    process_data()