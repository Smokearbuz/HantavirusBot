import asyncio
import json
import logging

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
        "• Push-уведомления при новых случаях\n\n"
        "Нажми кнопку ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )


# ── /mystats — подписки юзера ─────────────────────────────────────────────────

@dp.message(Command("mystats"))
async def mystats_handler(message: types.Message):
    subs = await db.get_user_subscriptions(message.chat.id)
    if not subs:
        await message.answer("У тебя пока нет активных подписок.\nОткрой бот и нажми 🔔 Следить у нужной страны.")
        return

    text = "🔔 <b>Твои подписки:</b>\n\n" + "\n".join(f"• {iso}" for iso in sorted(subs))
    text += "\n\nДля отмены — открой бот и нажми ✅ Подписан."
    await message.answer(text, parse_mode="HTML")


# ── WebApp data — сюда приходят данные от фронтенда ──────────────────────────
# Фронтенд вызывает: Telegram.WebApp.sendData(JSON.stringify({action, iso, country_name}))

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
                f"Буду уведомлять о новых случаях: <b>{country_name}</b>\n"
                f"Данные обновляются каждые 6 часов.",
                parse_mode="HTML"
            )

        elif action == "unsubscribe":
            await db.unsubscribe_user(chat_id, iso)
            await message.answer(
                f"🔕 Ты отписался от уведомлений: <b>{country_name}</b>",
                parse_mode="HTML"
            )

        else:
            logger.warning(f"Неизвестный action от WebApp: {action}")

    except json.JSONDecodeError:
        logger.error(f"Невалидный JSON от WebApp: {message.web_app_data.data}")
    except Exception as e:
        logger.error(f"Ошибка в webapp_data_handler: {e}")


# ── Функция рассылки уведомлений (вызывается из main.py) ──────────────────────

async def send_notifications(stats: dict):
    """
    Сравнивает текущие stats с предыдущими, находит страны с новыми случаями,
    рассылает уведомления подписчикам.
    """
    prev = await db.get_prev_stats()

    if not prev:
        # Первый запуск — просто сохраняем без рассылки
        await db.save_prev_stats(stats)
        logger.info("Первый запуск — сохранили baseline, рассылки нет.")
        return

    # Строим словарь предыдущих данных по ISO
    prev_by_iso = {c["iso"]: c for c in prev.get("countries", [])}

    notifications_sent = 0

    for country in stats.get("countries", []):
        iso = country["iso"]
        curr_total = country["total"]
        prev_total = prev_by_iso.get(iso, {}).get("total", curr_total)
        delta = curr_total - prev_total

        if delta <= 0:
            continue

        subscribers = await db.get_subscribers(iso)
        if not subscribers:
            continue

        # Формируем текст уведомления
        cfr_str = f"{country['cfr']}%" if country.get("cfr") else "—"
        deaths_delta = country["deaths"] - prev_by_iso.get(iso, {}).get("deaths", country["deaths"])
        
        is_hotspot = country['name'] in stats['global'].get('hotspots', [])
        risk_level = stats['global'].get('risk_level', 'Moderate')

        text = (
            f"{country['flag']} <b>Новые случаи: {country['name']}</b>\n\n"
            f"📈 Новых за обновление: <b>+{delta}</b>\n"
            f"📊 Всего случаев: <b>{curr_total}</b>\n"
        )
        if deaths_delta > 0:
            text += f"💀 Новых летальных: <b>+{deaths_delta}</b>\n"
        
        text += f"⚠️ Летальность (CFR): <b>{cfr_str}</b>\n"
        
        if is_hotspot:
            text += "🔥 <b>ВНИМАНИЕ: Горячая точка!</b>\n"
        
        text += (
            f"📊 Глобальный риск: <b>{risk_level}</b>\n\n"
            f"🔗 Источник: Global.health / Hondius 2026"
        )

        for chat_id in subscribers:
            try:
                await bot.send_message(
                    int(chat_id),
                    text,
                    parse_mode="HTML"
                )
                notifications_sent += 1
                await asyncio.sleep(0.05)  # избегаем flood limit
            except Exception as e:
                logger.warning(f"Не удалось отправить {chat_id}: {e}")

    # Сохраняем текущие как новые "предыдущие"
    await db.save_prev_stats(stats)
    logger.info(f"Рассылка завершена. Отправлено уведомлений: {notifications_sent}")


# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    logger.info("🚀 HantaTracker Bot запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🔴 Бот выключен")