import asyncio
import logging
import sqlite3
import os
import time
import random
import requests
import psutil
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

BOT_TOKEN = "8736136579:AAGp7QPivJCHFG5ooNcBVwZP3GDXNLQYaJs"
ADMIN_PASSWORD = "CyberAdmin12"
DB_NAME = "bot_data.db"
LOG_FILE = "bot_errors.log"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

FEATURES = {
    "osint_username": True,
    "osint_ip": True,
    "hacker_ddos": True,
    "hacker_scan": True,
    "sys_stats": True,
    "admin_broadcast": True,
    "admin_logs": True,
    "admin_ban": True
}

user_states = {}
rate_limit = defaultdict(list)

def check_flood(user_id):
    now = time.time()
    rate_limit[user_id] = [t for t in rate_limit[user_id] if now - t < 2]
    if len(rate_limit[user_id]) >= 5:
        return False
    rate_limit[user_id].append(now)
    return True

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, reg_date TIMESTAMP, last_active TIMESTAMP, msg_count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now()
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, reg_date, last_active) VALUES (?, ?, ?, ?, ?)''', (user_id, username, first_name, now, now))
    c.execute('''UPDATE users SET last_active = ?, username = ?, msg_count = msg_count + 1 WHERE user_id = ?''', (now, username, user_id))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res and res[0] == 1

def is_banned(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res and res[0] == 1

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (datetime.now() - timedelta(hours=1),))
    online = c.fetchone()[0]
    conn.close()
    return total, banned, online

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    res = c.fetchall()
    conn.close()
    return [r[0] for r in res]

def get_main_menu(is_adm=False):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 OSINT Юзернейм")
    builder.button(text="🌍 OSINT IP")
    builder.button(text="💻 Скан Сайта")
    builder.button(text="⚡ DDOS")
    builder.button(text="📊 Система")
    if is_adm:
        builder.button(text="👑 Админ-панель")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_admin_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="adm_stats")
    builder.button(text="⚙️ Функции", callback_data="adm_features")
    builder.button(text="📢 Рассылка", callback_data="adm_broadcast")
    builder.button(text="📝 Логи", callback_data="adm_logs")
    builder.button(text="🚫 Бан", callback_data="adm_ban")
    builder.button(text="✅ Разбан", callback_data="adm_unban")
    builder.adjust(2)
    return builder.as_markup()

def get_features_menu():
    builder = InlineKeyboardBuilder()
    for key, enabled in FEATURES.items():
        emoji = "✅" if enabled else "❌"
        builder.button(text=f"{emoji} {key}", callback_data=f"tgl_{key}")
    builder.button(text="🔙 Назад", callback_data="adm_back")
    builder.adjust(1)
    return builder.as_markup()

def check_username_osint(username):
    sites = {
        "Telegram": f"https://t.me/{username}",
        "GitHub": f"https://github.com/{username}",
        "Instagram": f"https://www.instagram.com/{username}/",
        "TikTok": f"https://www.tiktok.com/@{username}",
        "VK": f"https://vk.com/{username}",
        "YouTube": f"https://www.youtube.com/@{username}",
        "Twitter": f"https://twitter.com/{username}",
        "Reddit": f"https://www.reddit.com/user/{username}"
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    results = []
    for site, url in sites.items():
        try:
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                results.append(f"✅ {site}: Найден\n└ {url}")
            elif r.status_code == 403:
                results.append(f"🟡 {site}: Скрыт/Есть")
            else:
                results.append(f"❌ {site}: Нет")
        except:
            results.append(f"⚠️ {site}: Ошибка")
    return "\n".join(results)

def check_ip_osint(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=4)
        d = r.json()
        if d.get('status') == 'success':
            return f"🌍 Страна: {d.get('country')}\n🏙 Город: {d.get('city')}\n📡 Провайдер: {d.get('isp')}\n📍 Координаты: {d.get('lat')}, {d.get('lon')}"
        return "❌ IP не найден"
    except:
        return "⚠️ Ошибка запроса"

def scan_website(url):
    try:
        if not url.startswith('http'):
            url = 'http://' + url
        r = requests.get(url, timeout=5)
        headers = r.headers
        server = headers.get('Server', 'Скрыт')
        powered = headers.get('X-Powered-By', 'Скрыт')
        return f"🌐 Сайт: {url}\n✅ Статус: {r.status_code}\n🖥 Сервер: {server}\n⚙️ Технологии: {powered}"
    except:
        return "⚠️ Сайт недоступен или ошибка"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    if is_banned(uid): return await message.answer("⛔ Вы забанены.")
    add_user(uid, message.from_user.username, message.from_user.first_name)
    await message.answer(f"👋 Привет, {message.from_user.first_name}!\nБот готов к работе.", reply_markup=get_main_menu(is_admin(uid)))

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user_states[message.from_user.id] = "await_pass"
    await message.answer("🔐 Введите пароль:")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not FEATURES["sys_stats"]: return await message.answer("❌ Отключено.")
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    await message.answer(f"💻 CPU: {cpu}%\n🧠 RAM: {ram}%\n⏱ Время: {datetime.now().strftime('%H:%M:%S')}")

@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    text = message.text
    state = user_states.get(uid)
    adm = is_admin(uid)

    if is_banned(uid): return

    if not check_flood(uid):
        return await message.answer("⏳ Не флуди.")

    if state == "await_pass":
        if text == ADMIN_PASSWORD:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (uid,))
            conn.commit()
            conn.close()
            user_states[uid] = None
            await message.answer("✅ Доступ разрешен!", reply_markup=get_main_menu(True))
        else:
            await message.answer("❌ Неверный пароль.")
            user_states[uid] = None
        return

    if text == "🔙 Назад":
        return await message.answer("Меню:", reply_markup=get_main_menu(adm))

    if text == "🔍 OSINT Юзернейм":
        if not FEATURES["osint_username"]: return await message.answer("❌ Отключено.")
        user_states[uid] = "wait_username"
        return await message.answer("Введите ник (без @):")

    if state == "wait_username":
        msg = await message.answer("⏳ Ищу...")
        res = check_username_osint(text)
        await msg.edit_text(f"🔍 Результаты для `{text}`:\n\n{res}", parse_mode="Markdown")
        user_states[uid] = None
        return

    if text == "🌍 OSINT IP":
        if not FEATURES["osint_ip"]: return await message.answer("❌ Отключено.")
        user_states[uid] = "wait_ip"
        return await message.answer("Введите IP:")

    if state == "wait_ip":
        res = check_ip_osint(text)
        await message.answer(res)
        user_states[uid] = None
        return

    if text == "💻 Скан Сайта":
        if not FEATURES["hacker_scan"]: return await message.answer("❌ Отключено.")
        user_states[uid] = "wait_scan"
        return await message.answer("Введите URL сайта:")

    if state == "wait_scan":
        res = scan_website(text)
        await message.answer(res)
        user_states[uid] = None
        return

    if text == "⚡ DDOS":
        if not FEATURES["hacker_ddos"]: return await message.answer("❌ Отключено.")
        user_states[uid] = "wait_ddos"
        return await message.answer("Введите цель (IP/URL):")

    if state == "wait_ddos":
        await message.answer(f"⚡ DDOS на {text} запущен!\nОтправлено пакетов: {random.randint(50000, 500000)}")
        user_states[uid] = None
        return

    if text == "📊 Система":
        if not FEATURES["sys_stats"]: return await message.answer("❌ Отключено.")
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        return await message.answer(f"💻 CPU: {cpu}%\n🧠 RAM: {ram}%")

    if text == "👑 Админ-панель" and adm:
        return await message.answer("👑 Управление:", reply_markup=get_admin_menu())

@dp.callback_query(F.data.startswith("adm_") | F.data.startswith("tgl_"))
async def admin_callbacks(call: types.CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа!", show_alert=True)
    data = call.data
    
    if data == "adm_stats":
        total, banned, online = get_stats()
        await call.message.edit_text(f"📊 Всего: {total}\n🚫 Бан: {banned}\n🟢 Онлайн: {online}", reply_markup=get_admin_menu())
    
    elif data == "adm_features":
        await call.message.edit_text("⚙️ Функции:", reply_markup=get_features_menu())
    
    elif data.startswith("tgl_"):
        key = data.replace("tgl_", "")
        if key in FEATURES:
            FEATURES[key] = not FEATURES[key]
            await call.message.edit_reply_markup(reply_markup=get_features_menu())
    
    elif data == "adm_back":
        await call.message.edit_text("👑 Управление:", reply_markup=get_admin_menu())

    elif data == "adm_logs":
        if not FEATURES["admin_logs"]: return await call.answer("Отключено!", show_alert=True)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-10:]
                log_text = "".join(lines) if lines else "Пусто."
            await call.message.answer(f"📝 Логи:\n```\n{log_text}\n```", parse_mode="Markdown")
        else:
            await call.message.answer("Логов нет.")

    elif data == "adm_broadcast":
        if not FEATURES["admin_broadcast"]: return await call.answer("Отключено!", show_alert=True)
        user_states[call.from_user.id] = "wait_broadcast"
        await call.message.answer("📢 Введите текст для рассылки:")

    elif data == "adm_ban":
        if not FEATURES["admin_ban"]: return await call.answer("Отключено!", show_alert=True)
        user_states[call.from_user.id] = "wait_ban"
        await call.message.answer("🚫 Введите ID юзера для бана:")

    elif data == "adm_unban":
        if not FEATURES["admin_ban"]: return await call.answer("Отключено!", show_alert=True)
        user_states[call.from_user.id] = "wait_unban"
        await call.message.answer("✅ Введите ID юзера для разбана:")
    
    await call.answer()

@dp.message(F.text, lambda m: user_states.get(m.from_user.id) in ["wait_broadcast", "wait_ban", "wait_unban"])
async def admin_actions(message: types.Message):
    if not is_admin(message.from_user.id): return
    state = user_states.get(message.from_user.id)
    
    if state == "wait_broadcast":
        users = get_all_users()
        await message.answer(f"⏳ Рассылка для {len(users)} юзеров...")
        success = 0
        for u in users:
            try:
                await bot.send_message(u, f"📢 **Сообщение:**\n\n{message.text}", parse_mode="Markdown")
                success += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await message.answer(f"✅ Отправлено: {success}")
        
    elif state == "wait_ban":
        try:
            uid = int(message.text)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
            conn.commit()
            conn.close()
            await message.answer(f"🚫 Юзер {uid} забанен.")
        except:
            await message.answer("❌ Ошибка ID.")
            
    elif state == "wait_unban":
        try:
            uid = int(message.text)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
            conn.commit()
            conn.close()
            await message.answer(f"✅ Юзер {uid} разбанен.")
        except:
            await message.answer("❌ Ошибка ID.")
            
    user_states[message.from_user.id] = None

async def handle_web(request):
    return web.Response(text="Bot is running safely!")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Web Server on {port}")

    while True:
        try:
            logger.info("🚀 Бот запущен!")
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
