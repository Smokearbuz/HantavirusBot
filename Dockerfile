FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание папки для данных (SQLite)
RUN mkdir -p data

# Открытие порта для FastAPI
EXPOSE 8000

# Команда запуска: сначала запускаем бота в фоне, затем API
# В продакшене лучше использовать supervisor или отдельные контейнеры, 
# но для простоты в одном контейнере:
CMD ["sh", "-c", "python -m bot_api.bot & uvicorn bot_api.main:app --host 0.0.0.0 --port 8000"]
