import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta

CSV_URL = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/linelist/2026_hantavirus.csv"
NEWS_URL = "https://raw.githubusercontent.com/kraemer-lab/Hondius_hantavirus_h2026/main/data/news%20sources/hantavirus_results.json"

# Расширенный маппинг национальностей и стран в флаги и ISO
COUNTRY_DATA = {
    "Argentina": {"iso": "AR", "flag": "🇦🇷"},
    "argentinian": {"iso": "AR", "flag": "🇦🇷"},
    "Chile": {"iso": "CL", "flag": "🇨🇱"},
    "Brazil": {"iso": "BR", "flag": "🇧🇷"},
    "Bolivia": {"iso": "BO", "flag": "🇧🇴"},
    "Paraguay": {"iso": "PY", "flag": "🇵🇾"},
    "Uruguay": {"iso": "UY", "flag": "🇺🇾"},
    "Peru": {"iso": "PE", "flag": "🇵🇪"},
    "Switzerland": {"iso": "CH", "flag": "🇨🇭"},
    "swiss": {"iso": "CH", "flag": "🇨🇭"},
    "Germany": {"iso": "DE", "flag": "🇩🇪"},
    "german": {"iso": "DE", "flag": "🇩🇪"},
    "France": {"iso": "FR", "flag": "🇫🇷"},
    "french": {"iso": "FR", "flag": "🇫🇷"},
    "United States": {"iso": "US", "flag": "🇺🇸"},
    "USA": {"iso": "US", "flag": "🇺🇸"},
    "american": {"iso": "US", "flag": "🇺🇸"},
    "Netherlands": {"iso": "NL", "flag": "🇳🇱"},
    "dutch": {"iso": "NL", "flag": "🇳🇱"},
    "United Kingdom": {"iso": "GB", "flag": "🇬🇧"},
    "british": {"iso": "GB", "flag": "🇬🇧"},
    "Spain": {"iso": "ES", "flag": "🇪🇸"},
    "spanish": {"iso": "ES", "flag": "🇪🇸"},
    "Singapore": {"iso": "SG", "flag": "🇸🇬"},
    "singaporean": {"iso": "SG", "flag": "🇸🇬"},
    "Colombia": {"iso": "CO", "flag": "🇨🇴"},
    "Venezuela": {"iso": "VE", "flag": "🇻🇪"},
    "Ecuador": {"iso": "EC", "flag": "🇪🇨"},
}

def get_country_info(name):
    name_clean = str(name).lower().strip()
    # Прямое совпадение
    if name in COUNTRY_DATA: return COUNTRY_DATA[name]
    # Поиск по ключам (lowercased)
    for key, info in COUNTRY_DATA.items():
        if key.lower() == name_clean: return info
    # Заглушка
    return {"iso": name[:2].upper() if name else "??", "flag": "🏳️"}

def process_data():
    try:
        print(f"📥 Загрузка данных из {CSV_URL}...")
        df = pd.read_csv(CSV_URL)
        df.columns = [c.lower().strip() for c in df.columns]

        # Превращаем 'nationality' в 'country' для агрегации, если 'country' пуст
        if 'nationality' in df.columns:
            df['mapped_country'] = df['nationality'].apply(lambda x: x.split(' ')[0] if isinstance(x, str) else x)
        else:
            df['mapped_country'] = df['country'] if 'country' in df.columns else 'Unknown'

        # Даты
        date_col = next((c for c in ["symptom_onset", "confirmation_date", "date"] if c in df.columns), None)
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        
        now = datetime.utcnow()
        
        def count_delta(df_sub, days):
            if not date_col: return 0
            cutoff = now - timedelta(days=days)
            return int((df_sub[date_col] >= cutoff).sum())

        total = len(df)
        confirmed = int(len(df[df['status'] == "confirmed"])) if 'status' in df.columns else 0
        deaths = int(len(df[df['outcome'] == "died"])) if 'outcome' in df.columns else 0
        
        # Демография
        age_groups = {"0-18": 0, "19-45": 0, "46-65": 0, "66+": 0, "Unknown": 0}
        gender_stats = {"male": 0, "female": 0, "unknown": 0}
        
        if 'age' in df.columns:
            for age in df['age'].dropna():
                try:
                    a = float(age)
                    if a <= 18: age_groups["0-18"] += 1
                    elif a <= 45: age_groups["19-45"] += 1
                    elif a <= 65: age_groups["46-65"] += 1
                    else: age_groups["66+"] += 1
                except: pass
            age_groups["Unknown"] = total - sum(age_groups.values())

        if 'sex' in df.columns:
            genders = df['sex'].str.lower().value_counts().to_dict()
            gender_stats["male"] = int(genders.get("male", 0))
            gender_stats["female"] = int(genders.get("female", 0))
            gender_stats["unknown"] = total - gender_stats["male"] - gender_stats["female"]

        # Расчет риска
        new_7d = count_delta(df, 7)
        growth_rate = round((new_7d / (total - new_7d) * 100), 1) if (total - new_7d) > 0 else 0
        
        risk_level = "Low"
        if growth_rate > 20 or new_7d > 10: risk_level = "High"
        elif growth_rate > 5 or new_7d > 2: risk_level = "Moderate"

        stats = {
            "global": {
                "total": total,
                "confirmed": confirmed,
                "deaths": deaths,
                "cfr": round((deaths / confirmed * 100), 1) if confirmed > 0 else 0.0,
                "new_24h": count_delta(df, 1),
                "new_7d": new_7d,
                "growth_rate": growth_rate,
                "risk_level": risk_level,
                "last_update": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "demographics": {
                    "age": age_groups,
                    "gender": gender_stats
                },
                "hotspots": []
            },
            "countries": []
        }

        # Группировка по странам
        countries_list = []
        for country_name in df['mapped_country'].dropna().unique():
            sub = df[df['mapped_country'] == country_name]
            info = get_country_info(country_name)
            
            c_total = len(sub)
            c_new_7d = count_delta(sub, 7)
            
            countries_list.append({
                "name": info.get("name", country_name).capitalize(),
                "iso": info["iso"],
                "flag": info["flag"],
                "total": c_total,
                "deaths": int(len(sub[sub['outcome'] == "died"])) if 'outcome' in df.columns else 0,
                "new_7d": c_new_7d,
                "growth": round((c_new_7d / c_total * 100), 1) if c_total > 0 else 0
            })

        # Сортировка и хотспоты
        countries_list.sort(key=lambda x: x["total"], reverse=True)
        stats["countries"] = countries_list
        stats["global"]["hotspots"] = [c["name"] for c in sorted(countries_list, key=lambda x: x["growth"], reverse=True)[:3] if c["growth"] > 0]

        # Сохранение
        os.makedirs("data", exist_ok=True)
        with open("data/stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        print(f"🚀 data/stats.json обновлён! Риск: {risk_level}, Хотспоты: {stats['global']['hotspots']}")
        return stats

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    process_data()



if __name__ == "__main__":
    process_data()