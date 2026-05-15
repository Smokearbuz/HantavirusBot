import asyncio
import json
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

from bot_api.config import BOT_TOKEN, WEBAPP_URL
from bot_api.database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ── /start ────────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # Регистрируем юзера в БД
    await db.get_or_create_user(
        chat_id=message.chat.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🦠 Открыть HantaTracker",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "🔬 <b>HantaTracker</b> — мониторинг вспышки хантавируса 2026.\n\n"
        "• Глобальная статистика в реальном времени\n"
        "• Данные по каждой стране\n"
        "• Push-уведомления при новых случаях и новостях\n\n"
        "Нажми кнопку ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ── /mystats ──────────────────────────────────────────────────────────────────

@dp.message(Command("mystats"))
async def mystats_handler(message: types.Message):
    subs = await db.get_user_subscriptions(message.chat.id)
    if not subs:
        await message.answer("У тебя пока нет активных подписок.\nОткрой бот и нажми 🔔 Следить у нужной страны.")
        return

    text = "🔔 <b>Твои подписки:</b>\n\n" + "\n".join(f"• {iso}" for iso in sorted(subs))
    text += "\n\nДля отмены — открой бот и нажми ✅ Подписан."
    await message.answer(text, parse_mode="HTML")

# ── WebApp data ───────────────────────────────────────────────────────────────

@dp.message(F.web_app_data)
async def webapp_data_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        iso = data.get("iso", "").upper()
        country_name = data.get("country_name", iso)
        chat_id = message.chat.id

        if action == "subscribe":
            await db.subscribe_user(chat_id, iso)
            await message.answer(
                f"✅ Подписка оформлена!\n\n"
                f"Буду уведомлять о новых случаях и новостях: <b>{country_name}</b>",
                parse_mode="HTML"
            )
        elif action == "unsubscribe":
            await db.unsubscribe_user(chat_id, iso)
            await message.answer(
                f"🔕 Ты отписался от уведомлений: <b>{country_name}</b>",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка в webapp_data_handler: {e}")

# ── Рассылка обновлений ───────────────────────────────────────────────────────

async def process_updates(stats: dict, news: list):
    """Главный цикл обработки обновлений: статистика + новости"""
    await _handle_stats_update(stats)
    await _handle_news_update(news)

async def _handle_stats_update(stats: dict):
    prev = await db.get_prev_stats()
    if not prev:
        await db.save_prev_stats(stats)
        return

    prev_by_iso = {c["iso"]: c for c in prev.get("countries", [])}
    risk_level = stats['global'].get('risk_level', 'Moderate')
    
    # Сверяем риск уровень (глобальный)
    prev_risk = prev['global'].get('risk_level', 'Moderate')
    if risk_level != prev_risk:
        # Уведомляем всех о смене уровня риска? (Пока опустим или сделаем broadcast)
        pass

    for country in stats.get("countries", []):
        iso = country["iso"]
        curr_total = country["total"]
        prev_data = prev_by_iso.get(iso, {"total": curr_total, "deaths": country["deaths"], "growth": 0})
        delta = curr_total - prev_data["total"]

        # Сохраняем в историю (SQL)
        await db.save_daily_snapshot(
            country_iso=iso,
            total=curr_total,
            deaths=country["deaths"],
            new=delta,
            risk=risk_level
        )

        if delta <= 0:
            continue

        subscribers = await db.get_subscribers(iso)
        if not subscribers:
            continue

        text = (
            f"{country['flag']} <b>Новые случаи: {country['name']}</b>\n\n"
            f"📈 Новых: <b>+{delta}</b>\n"
            f"📊 Всего: <b>{curr_total}</b>\n"
            f"📊 Риск: <b>{risk_level}</b>\n\n"
            f"🔗 <a href='{WEBAPP_URL}'>Подробнее в приложении</a>"
        )

        for chat_id in subscribers:
            try:
                await bot.send_message(int(chat_id), text, parse_mode="HTML")
                await asyncio.sleep(0.05)
            except Exception: pass

    await db.save_prev_stats(stats)

async def _handle_news_update(news: list):
    """Рассылка новых новостей"""
    for item in news[:5]: # Проверяем последние 5
        link = item.get("link")
        if not link: continue
        
        # Генерируем ID для дедупликации (если нет)
        ext_id = item.get("id", link)
        
        if await db.is_news_notified(ext_id):
            continue

        # Уведомляем (например, всех или по странам? Пока всех кто подписан хоть на что-то?)
        # Для простоты — рассылаем всем, кто подписан на Глобальную статистику (или просто всем пользователям)
        # Но лучше — всем активным пользователям.
        
        text = (
            f"📰 <b>Свежие новости:</b>\n\n"
            f"<b>{item.get('title')}</b>\n\n"
            f"🔗 <a href='{link}'>Читать источник</a>"
        )
        
        # Получаем всех пользователей (Chat ID)
        chat_ids = await db.get_all_user_chat_ids()
        
        for chat_id in chat_ids:
            try:
                await bot.send_message(int(chat_id), text, parse_mode="HTML")
                await asyncio.sleep(0.05)
            except Exception: pass
            
        await db.save_news_article(ext_id, item.get('title'), link)

# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    await db.init_db()
    logger.info("🚀 HantaTracker Bot запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())