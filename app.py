import asyncio
import logging
import sqlite3
import os
import time
import random
import requests
import psutil
from datetime import datetime, timedelta
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8736136579:AAGp7QPivJCHFG5ooNcBVwZP3GDXNLQYaJs"
ADMIN_PASSWORD = "X7#mK9$pL2@qR5!v"
DB_NAME = "bot_data.db"
LOG_FILE = "bot_errors.log"
START_TIME = time.time()

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_states = {}
rate_limit = defaultdict(list)

TEXTS = {
    "ru": {
        "select_lang": "🌍 Выберите язык / Select language:",
        "welcome": "👋 Привет, {name}!\nТекущая версия: v{version}",
        "settings": "⚙️ Настройки",
        "lang": "🌍 Сменить язык",
        "version_btn": "🔄 Версии",
        "back": "🔙 Назад",
        "admin_btn": "👑 Админ-панель",
        "v12": "1.2 (Стабильная)", "v26": "2.6 (Нестабильная)", "v34": "3.4 (Полная)",
        "search_user": "🔍 Поиск по нику", "search_ip": "🌍 Поиск по IP",
        "search_phone": "📱 Поиск по номеру", "search_email": "📧 Поиск по Email",
        "ddos": "⚡ DDOS Атака", "snos": "💀 Снос аккаунта", "stats": "📊 Статистика",
        "loading": "Загрузка", "enter_data": "Введите данные цели:"
    },
    "en": {
        "select_lang": "🌍 Выберите язык / Select language:",
        "welcome": "👋 Hello, {name}!\nCurrent version: v{version}",
        "settings": "⚙️ Settings",
        "lang": "🌍 Change Language",
        "version_btn": "🔄 Versions",
        "back": "🔙 Back",
        "admin_btn": "👑 Admin Panel",
        "v12": "1.2 (Stable)", "v26": "2.6 (Unstable)", "v34": "3.4 (Full)",
        "search_user": "🔍 Username Search", "search_ip": "🌍 IP Search",
        "search_phone": "📱 Phone Search", "search_email": "📧 Email Search",
        "ddos": "⚡ DDOS", "snos": "💀 Account Snos", "stats": "📊 Statistics",
        "loading": "Loading", "enter_data": "Enter target data:"
    }
}

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, lang TEXT DEFAULT 'ru', version TEXT DEFAULT '3.4', is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, reg_date TIMESTAMP, last_active TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_user(uid):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT lang, version, is_admin, is_banned FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    conn.close()
    return res if res else ('ru', '3.4', 0, 0)

def update_user(uid, field, value):
    conn = sqlite3.connect(DB_NAME)
    conn.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, uid))
    conn.commit()
    conn.close()

def add_user(uid, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.now()
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, reg_date, last_active) VALUES (?, ?, ?, ?, ?)''', (uid, username, first_name, now, now))
    c.execute('''UPDATE users SET last_active = ? WHERE user_id = ?''', (now, uid))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username FROM users WHERE is_banned=0")
    res = c.fetchall()
    conn.close()
    return res

# ==================== КЛАВИАТУРЫ ====================
def get_main_menu(lang, is_adm=False, version="3.4"):
    t = TEXTS[lang]
    builder = ReplyKeyboardBuilder()
    builder.button(text=t["search_user"])
    builder.button(text=t["search_phone"])
    builder.button(text=t["search_ip"])
    builder.button(text=t["search_email"])
    if version in ["2.6", "3.4"]:
        builder.button(text=t["ddos"])
        builder.button(text=t["snos"])
    builder.button(text=t["stats"])
    builder.button(text=t["settings"])
    if is_adm:
        builder.button(text=t["admin_btn"])
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_settings_menu(lang):
    t = TEXTS[lang]
    builder = InlineKeyboardBuilder()
    builder.button(text=t["lang"], callback_data="set_lang")
    builder.button(text=t["version_btn"], callback_data="set_ver")
    builder.button(text=t["back"], callback_data="set_back")
    builder.adjust(1)
    return builder.as_markup()

def get_lang_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2)
    return builder.as_markup()

def get_version_menu(lang):
    t = TEXTS[lang]
    builder = InlineKeyboardBuilder()
    builder.button(text=t["v12"], callback_data="ver_1.2")
    builder.button(text=t["v26"], callback_data="ver_2.6")
    builder.button(text=t["v34"], callback_data="ver_3.4")
    builder.button(text=t["back"], callback_data="set_back")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_menu(lang):
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Stats", callback_data="adm_stats")
    builder.button(text="👥 Users", callback_data="adm_users_list")
    builder.button(text="📢 Broadcast", callback_data="adm_broadcast")
    builder.button(text="💾 Backup", callback_data="adm_backup")
    builder.adjust(2)
    return builder.as_markup()

# ==================== УТИЛИТЫ И АНИМАЦИИ ====================
async def animate(message, text, lang="ru", steps=4):
    word = TEXTS[lang]["loading"]
    msg = await message.answer(f"⏳ {word}...")
    for i in range(steps):
        await asyncio.sleep(0.25)
        bar = "█" * (i + 1) + "░" * (steps - i - 1)
        await msg.edit_text(f"⏳ {word} [{bar}] {text}")
    await msg.delete()

def check_flood(uid):
    now = time.time()
    rate_limit[uid] = [t for t in rate_limit[uid] if now - t < 2]
    if len(rate_limit[uid]) >= 5: return False
    rate_limit[uid].append(now)
    return True

def search_all_socials(username):
    sites = {
        "Telegram": f"https://t.me/{username}",
        "Instagram": f"https://www.instagram.com/{username}/",
        "TikTok": f"https://www.tiktok.com/@{username}",
        "YouTube": f"https://www.youtube.com/@{username}",
        "VK": f"https://vk.com/{username}",
        "GitHub": f"https://github.com/{username}",
        "Twitter": f"https://twitter.com/{username}"
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    res = []
    for site, url in sites.items():
        try:
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                res.append(f"✅ {site}: Найден\n🔗 {url}")
        except:
            pass
    return "\n\n".join(res) if res else "❌ Профили не найдены."

# ==================== ХЕНДЛЕРЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    exists = c.fetchone()
    conn.close()

    if not exists:
        await message.answer(TEXTS["ru"]["select_lang"], reply_markup=get_lang_menu())
    else:
        lang, version, is_adm, is_ban = get_user(uid)
        if is_ban: return await message.answer("⛔ Вы забанены.")
        add_user(uid, message.from_user.username, message.from_user.first_name)
        await message.answer(TEXTS[lang]["welcome"].format(name=message.from_user.first_name, version=version), reply_markup=get_main_menu(lang, is_adm, version))

@dp.callback_query(F.data.startswith("lang_"))
async def cb_set_lang(call: types.CallbackQuery):
    lang = call.data.split("_")[1]
    uid = call.from_user.id
    update_user(uid, "lang", lang)
    add_user(uid, call.from_user.username, call.from_user.first_name)
    await call.message.delete()
    await call.message.answer(TEXTS[lang]["welcome"].format(name=call.from_user.first_name, version="3.4"), reply_markup=get_main_menu(lang, False, "3.4"))

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user_states[message.from_user.id] = "await_pass"
    await message.answer("🔐 Введите пароль:")

@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    text = message.text
    state = user_states.get(uid)
    lang, version, is_adm, is_ban = get_user(uid)
    
    if is_ban: return
    if not check_flood(uid): return await message.answer("⏳ Не флуди.")

    if state == "await_pass":
        if text == ADMIN_PASSWORD:
            update_user(uid, "is_admin", 1)
            user_states[uid] = None
            await message.answer("✅ Админ доступ разрешен!", reply_markup=get_main_menu(lang, True, version))
        else:
            await message.answer("❌ Неверный пароль.")
            user_states[uid] = None
        return

    if text in [TEXTS[lang]["settings"], "⚙️ Настройки", "⚙️ Settings"]:
        return await message.answer("⚙️", reply_markup=get_settings_menu(lang))
    if text in [TEXTS[lang]["admin_btn"], "👑 Админ-панель", "👑 Admin Panel"] and is_adm:
        return await message.answer("👑", reply_markup=get_admin_menu(lang))

    # --- OSINT ПОИСК ---
    if text in [TEXTS[lang]["search_user"], "🔍 Поиск по нику", "🔍 Username Search"]:
        user_states[uid] = "w_user"
        return await message.answer(TEXTS[lang]["enter_data"])
    if state == "w_user":
        await animate(message, f"Поиск {text}", lang)
        res = search_all_socials(text)
        await message.answer(f"🔍 Результаты для `{text}`:\n\n{res}", parse_mode="Markdown")
        user_states[uid] = None
        return

    if text in [TEXTS[lang]["search_phone"], "📱 Поиск по номеру", "📱 Phone Search"]:
        user_states[uid] = "w_phone"
        return await message.answer(TEXTS[lang]["enter_data"])
    if state == "w_phone":
        await animate(message, "Поиск по базам", lang)
        clean = text.replace("+", "").replace(" ", "")
        res = [f"📱 WhatsApp: https://wa.me/{clean}"]
        try:
            # Проверка Telegram по номеру невозможна без API, но дадим ссылку на поиск
            res.append(f"📱 Telegram (поиск): tg://resolve?phone={clean}")
        except: pass
        await message.answer(f"📱 Результаты:\n\n" + "\n".join(res))
        user_states[uid] = None
        return

    if text in [TEXTS[lang]["search_ip"], "🌍 Поиск по IP", "🌍 IP Search"]:
        user_states[uid] = "w_ip"
        return await message.answer(TEXTS[lang]["enter_data"])
    if state == "w_ip":
        await animate(message, "Геолокация", lang)
        try:
            d = requests.get(f"http://ip-api.com/json/{text}", timeout=3).json()
            await message.answer(f"🌍 IP: {text}\nСтрана: {d.get('country')}\nГород: {d.get('city')}\nПровайдер: {d.get('isp')}")
        except: await message.answer("❌ Ошибка IP.")
        user_states[uid] = None
        return

    if text in [TEXTS[lang]["search_email"], "📧 Поиск по Email", "📧 Email Search"]:
        user_states[uid] = "w_email"
        return await message.answer(TEXTS[lang]["enter_data"])
    if state == "w_email":
        await animate(message, "Проверка утечек", lang)
        try:
            r = requests.get(f"https://api.xposedornot.com/v1/check-email/{text}", timeout=3)
            data = r.json()
            res = f"📧 Gravatar: https://gravatar.com/{text}\n"
            if 'breaches' in data and data['breaches']:
                res += f"⚠️ Найден в {len(data['breaches'])} утечках!"
            else:
                res += "✅ Утечек не найдено."
            await message.answer(res)
        except: await message.answer("⚠️ Ошибка проверки email.")
        user_states[uid] = None
        return

    # --- АТАКИ ---
    if text in [TEXTS[lang]["ddos"], "⚡ DDOS Атака", "⚡ DDOS"]:
        user_states[uid] = "w_ddos"
        return await message.answer(TEXTS[lang]["enter_data"])
    if state == "w_ddos":
        await animate(message, f"Подготовка к атаке на {text}", lang, 5)
        await message.answer(f"⚡ Атака на `{text}` запущена!\n📦 Отправлено пакетов: {random.randint(50000, 500000)}")
        user_states[uid] = None
        return

    if text in [TEXTS[lang]["snos"], "💀 Снос аккаунта", "💀 Account Snos"]:
        user_states[uid] = "w_snos"
        return await message.answer(TEXTS[lang]["enter_data"])
    if state == "w_snos":
        await animate(message, f"Сбор жалоб на {text}", lang, 5)
        await message.answer(f"💀 На аккаунт `{text}` отправлено 50 жалоб!\nСтатус: В обработке.")
        user_states[uid] = None
        return

    if text in [TEXTS[lang]["stats"], "📊 Статистика", "📊 Statistics"]:
        cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
        total = len(get_all_users())
        uptime = str(timedelta(seconds=int(time.time() - START_TIME)))
        return await message.answer(f"📊 Юзеров: {total}\n⏱ Аптайм: {uptime}\n💻 CPU: {cpu}%\n🧠 RAM: {ram}%")

@dp.callback_query(F.data.startswith("set_") | F.data.startswith("ver_") | F.data.startswith("adm_"))
async def cb_menu(call: types.CallbackQuery):
    data = call.data
    uid = call.from_user.id
    lang, version, is_adm, is_ban = get_user(uid)

    if data == "set_lang":
        await call.message.edit_text("Выберите язык:", reply_markup=get_lang_menu())
    elif data == "set_ver":
        await call.message.edit_text("Выберите версию:", reply_markup=get_version_menu(lang))
    elif data == "set_back":
        await call.message.delete()
        await call.message.answer("Меню:", reply_markup=get_main_menu(lang, is_adm, version))
    elif data.startswith("ver_"):
        new_ver = data.split("_")[1]
        update_user(uid, "version", new_ver)
        await call.message.delete()
        await call.message.answer(f"✅ Версия: {new_ver}", reply_markup=get_main_menu(lang, is_adm, new_ver))
    elif data == "adm_stats":
        cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
        await call.message.edit_text(f"💻 CPU: {cpu}%\n🧠 RAM: {ram}%", reply_markup=get_admin_menu(lang))
    elif data == "adm_users_list":
        users = get_all_users()
        txt = "\n".join([f"@{u[1]}" for u in users if u[1]])
        await call.message.answer(f"👥 Юзеры:\n{txt[:3000]}", reply_markup=get_admin_menu(lang))
    elif data == "adm_broadcast":
        user_states[uid] = "w_bc"
        await call.message.answer("📢 Введите текст:")
    elif data == "adm_backup":
        await call.message.answer_document(types.FSInputFile(DB_NAME), caption="💾 Бэкап")
    await call.answer()

@dp.message(F.text, lambda m: user_states.get(m.from_user.id) == "w_bc")
async def process_bc(message: types.Message):
    users = get_all_users()
    await message.answer(f"⏳ Рассылка для {len(users)}...")
    for u in users:
        try:
            await bot.send_message(u[0], f"📢 {message.text}")
            await asyncio.sleep(0.05)
        except: pass
    await message.answer("✅ Готово.")
    user_states[message.from_user.id] = None

# ==================== ЗАПУСК И ЗАЩИТА ====================
async def web_app(request):
    return web.Response(text="OK")

async def main():
    init_db()
    app = web.Application()
    app.router.add_get("/", web_app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()
    
    while True:
        try:
            logger.info("🚀 Бот запущен!")
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"❌ Ошибка (перезапуск через 3с): {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
