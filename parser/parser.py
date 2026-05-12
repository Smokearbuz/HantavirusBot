import pandas as pd
import requests
import json
import os

# Ссылки на репозиторий Hondius 2026
CSV_URL = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/linelist/2026_hantavirus.csv"
NEWS_URL = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/news%20sources/hantavirus_results.json"

def process_data():
    try:
        # 1. Загрузка основного списка случаев
        df = pd.read_csv(CSV_URL)
        
        # 2. Глобальная статистика
        stats = {
            "global": {
                "total": len(df),
                "confirmed": int(len(df[df['status'] == 'confirmed'])),
                "suspected": int(len(df[df['status'] == 'suspected'])),
                "deaths": int(len(df[df['outcome'] == 'deceased'])),
                "last_update": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
            },
            "countries": {}
        }

        # 3. Статистика по странам
        countries = df['country'].unique()
        for country in countries:
            c_df = df[df['country'] == country]
            stats["countries"][country] = {
                "total": len(c_df),
                "confirmed": int(len(c_df[c_df['status'] == 'confirmed'])),
                "deaths": int(len(c_df[c_df['outcome'] == 'deceased']))
            }

        # 4. Новости (берем последние 10 записей)
        news_res = requests.get(NEWS_URL)
        if news_res.status_code == 200:
            all_news = news_res.json()
            # Сортируем по дате (если есть) и берем свежие
            stats["latest_news"] = all_news[:10] 

        # 5. Сохраняем результат в папку data
        os.makedirs('data', exist_ok=True)
        with open('data/stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
            
        print("✅ Данные успешно обновлены в data/stats.json")

    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")

if __name__ == "__main__":
    process_data()