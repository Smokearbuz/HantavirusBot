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
    # Register user in DB
    await db.get_or_create_user(
        chat_id=message.chat.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🦠 Open HantaTracker",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    await message.answer(
        f"Hello, {message.from_user.first_name}! 👋\n\n"
        "🔬 <b>HantaTracker</b> — monitoring the Hantavirus outbreak of 2026.\n\n"
        "• Real-time global statistics\n"
        "• Data for each country\n"
        "• Push notifications for new cases and news\n\n"
        "Click the button below to start:",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ── /mystats ──────────────────────────────────────────────────────────────────

@dp.message(Command("mystats"))
async def mystats_handler(message: types.Message):
    subs = await db.get_user_subscriptions(message.chat.id)
    if not subs:
        await message.answer("You don't have any active subscriptions yet.\nOpen the app and click 🔔 Follow on a country page.")
        return

    text = "🔔 <b>Your subscriptions:</b>\n\n" + "\n".join(f"• {iso}" for iso in sorted(subs))
    text += "\n\nTo cancel — open the app and click ✅ Subscribed."
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
                f"✅ Subscription active!\n\n"
                f"I will notify you about new cases and news in: <b>{country_name}</b>",
                parse_mode="HTML"
            )
        elif action == "unsubscribe":
            await db.unsubscribe_user(chat_id, iso)
            await message.answer(
                f"🔕 You have unsubscribed from: <b>{country_name}</b>",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error in webapp_data_handler: {e}")

# ── Update Broadcast ──────────────────────────────────────────────────────────

async def process_updates(stats: dict, news: list):
    """Main update processing loop: statistics + news"""
    await _handle_stats_update(stats)
    await _handle_news_update(news)

async def _handle_stats_update(stats: dict):
    prev = await db.get_prev_stats()
    if not prev:
        await db.save_prev_stats(stats)
        return

    prev_by_iso = {c["iso"]: c for c in prev.get("countries", [])}
    risk_level = stats['global'].get('risk_level', 'Moderate')
    
    for country in stats.get("countries", []):
        iso = country["iso"]
        curr_total = country["total"]
        prev_data = prev_by_iso.get(iso, {"total": curr_total, "deaths": country["deaths"], "growth": 0})
        delta = curr_total - prev_data["total"]

        # Save to history (SQL)
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
            f"{country['flag']} <b>New Cases: {country['name']}</b>\n\n"
            f"📈 New: <b>+{delta}</b>\n"
            f"📊 Total: <b>{curr_total}</b>\n"
            f"⚠️ Risk Level: <b>{risk_level}</b>\n\n"
            f"🔗 <a href='{WEBAPP_URL}'>View details in App</a>"
        )

        for chat_id in subscribers:
            try:
                await bot.send_message(int(chat_id), text, parse_mode="HTML")
                await asyncio.sleep(0.05)
            except Exception: pass

    await db.save_prev_stats(stats)

async def _handle_news_update(news: list):
    """Broadcast new news articles"""
    for item in news[:5]:
        link = item.get("link")
        if not link: continue
        
        ext_id = item.get("id", link)
        if await db.is_news_notified(ext_id):
            continue

        text = (
            f"📰 <b>Breaking News:</b>\n\n"
            f"<b>{item.get('title')}</b>\n\n"
            f"🔗 <a href='{link}'>Read more</a>"
        )
        
        chat_ids = await db.get_all_user_chat_ids()
        for chat_id in chat_ids:
            try:
                await bot.send_message(int(chat_id), text, parse_mode="HTML")
                await asyncio.sleep(0.05)
            except Exception: pass
            
        await db.save_news_article(ext_id, item.get('title'), link)

# ── Run ───────────────────────────────────────────────────────────────────────

async def main():
    await db.init_db()
    logger.info("🚀 HantaTracker Bot is running")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())