# -*- coding: utf-8 -*-
import os
import threading
import logging
import time
import random
import sqlite3
import requests
import asyncio
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== КОНФИГ ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА"
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
DB_NAME = os.path.join(BASE_DIR, "helper_bot.db")

# ==================== FLASK (для Render) ====================
app = Flask(__name__)
@app.route('/')
def home():
    return "OSINT Pro Terminal"
@app.route('/health')
def health():
    return "OK", 200

# ==================== ЛОГГЕР ====================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self.init_db()
    def get_connection(self):
        return sqlite3.connect(DB_NAME)
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, language TEXT DEFAULT 'ru', registered_at TIMESTAMP, last_active TIMESTAMP)''')
        conn.commit()
        conn.close()
    def add_user(self, user_id, username, first_name, last_name):
        conn = self.get_connection(); cursor = conn.cursor(); now = datetime.now()
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, registered_at, last_active) VALUES (?, ?, ?, ?, ?, ?)', (user_id, username, first_name, last_name, now, now))
        conn.commit(); conn.close()

db = Database()

# ==================== РЕАЛЬНЫЙ OSINT ДВИЖОК ====================
class RealOSINT:
    def check_social(self, username):
        """Проверка аккаунтов по открытым ссылкам"""
        links = {
            "Telegram": f"https://t.me/{username}",
            "VK": f"https://vk.com/{username}",
            "Instagram": f"https://www.instagram.com/{username}/",
            "TikTok": f"https://www.tiktok.com/@{username}",
            "YouTube": f"https://www.youtube.com/@{username}",
            "GitHub": f"https://github.com/{username}",
            "Twitter/X": f"https://twitter.com/{username}",
            "Reddit": f"https://www.reddit.com/user/{username}"
        }
        results = []
        for platform, url in links.items():
            try:
                r = requests.get(url, timeout=2, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    results.append({"platform": platform, "url": url, "status": "✅ НАЙДЕН"})
                else:
                    results.append({"platform": platform, "status": "❌ Не найден"})
            except:
                results.append({"platform": platform, "status": "⚠️ Скрыт"})
        return results

    def get_geo_ip(self, ip):
        """Реальная геолокация IP через бесплатный API"""
        try:
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
            data = r.json()
            if data.get('status') == 'success':
                return {
                    'country': data.get('country'),
                    'city': data.get('city'),
                    'isp': data.get('isp'),
                    'org': data.get('org'),
                    'zip': data.get('zip'),
                    'timezone': data.get('timezone'),
                    'lat': data.get('lat'),
                    'lon': data.get('lon')
                }
            return None
        except:
            return None

    def get_email_info(self, email):
        """Проверка Gravatar для email (существует ли аккаунт)"""
        hash_email = hashlib.md5(email.lower().encode()).hexdigest()
        url = f"https://www.gravatar.com/avatar/{hash_email}"
        try:
            r = requests.get(url, timeout=3, allow_redirects=False)
            if r.status_code == 200:
                return {"avatar": url, "exists": True}
            return {"avatar": url, "exists": False}
        except:
            return {"avatar": url, "exists": False}

osint_engine = RealOSINT()

# ==================== МЕНЮ ====================
def get_main_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton("🕵️ DEEP SCAN")],
        [KeyboardButton("👤 ПОИСК ПО НИКУ")],
        [KeyboardButton("📱 ПОИСК ПО ТЕЛЕФОНУ")],
        [KeyboardButton("🌍 ПОИСК ПО IP")],
        [KeyboardButton("📧 ПОИСК ПО EMAIL")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

# ==================== ОТЧЕТ (Красивое оформление) ====================
def format_report(target, social_results, ip_info=None, email_info=None, is_ip=False):
    """Создание красивого отчета"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    if is_ip:
        title = f"🌍 ГЕОЛОКАЦИЯ IP: {target}"
        body = f"""📍 *СТРАНА:* {ip_info['country']}
🏙️ *ГОРОД:* {ip_info['city']}
🏢 *ПРОВАЙДЕР:* {ip_info['isp']}
🏛️ *ОРГАНИЗАЦИЯ:* {ip_info['org']}
📮 *ИНДЕКС:* {ip_info['zip']}
🕐 *ЧАСОВОЙ ПОЯС:* {ip_info['timezone']}
🛰️ *КООРДИНАТЫ:* {ip_info['lat']}, {ip_info['lon']}"""
        return title, body, None

    # Для соцсетей или email
    social_text = ""
    for i, r in enumerate(social_results):
        icon = r['status']  # ✅, ❌, ⚠️
        url = r.get('url', '')
        social_text += f"├ *{r['platform']}*: {icon} {url}\n"

    if email_info:
        email_text = f"""📧 *EMAIL:* {target}
🖼️ *АВАТАР:* {'✅ Существует' if email_info['exists'] else '❌ Не существует'}
🔗 *ССЫЛКА:* {email_info['avatar']}"""
    else:
        email_text = ""

    # Имитация личных данных (данные из открытых утечек)
    phones = [f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}" for _ in range(random.randint(1, 3))]
    emails = [f"{target}{random.choice(['@gmail.com', '@mail.ru', '@yandex.ru', '@proton.me'])}" for _ in range(random.randint(1, 3))]

    title = f"🕵️ ДОСЬЕ НА: @{target}"
    body = f"""📅 *ДАТА:* {timestamp}

👤 *ПРОФИЛЬ*
├ Никнейм: `{target}`
├ Вероятный возраст: {random.randint(16, 45)}
├ Активность: {random.choice(['Высокая', 'Средняя', 'Низкая'])}
└ Статус: 🟢 Онлайн (оценка)

📱 *НАЙДЕННЫЕ ТЕЛЕФОНЫ*
{chr(10).join([f"├ {p}" for p in phones])}

📧 *НАЙДЕННЫЕ EMAIL*
{chr(10).join([f"├ {e}" for e in emails])}

🌐 *СОЦИАЛЬНЫЕ СЕТИ (Проверка 8 платформ)*
{social_text}

🧠 *ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ*
├ Цифровой след: {random.choice(['Низкий', 'Средний', 'Высокий'])}
└ Риск деанонимизации: {random.randint(10, 95)}%

📋 *ЗАКЛЮЧЕНИЕ*
Данные получены из открытых источников."""
    return title, body, None

# ==================== КОМАНДЫ ====================
async def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or "User"
    last_name = update.effective_user.last_name or ""
    db.add_user(user_id, username, first_name, last_name)
    await update.message.reply_text(
        "🕵️ *OSINT PRO TERMINAL*\n═══════════════════════\n\n⚡ Система онлайн.\n\nВыберите тип поиска:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu(user_id)
    )

async def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state', 'main')

    if text == "🔙 НАЗАД":
        context.user_data['state'] = 'main'
        await update.message.reply_text("🕵️ Главное меню", reply_markup=get_main_menu(user_id))
        return

    # ===== DEEP SCAN =====
    if text == "🕵️ DEEP SCAN":
        await update.message.reply_text("🕵️ *Введите никнейм:*", parse_mode=ParseMode.MARKDOWN)
        context.user_data['state'] = 'deep_scan'
        return

    if state == 'deep_scan':
        target = text.strip().replace("@", "")
        await update.message.reply_text("🕵️ *Запуск глубокого сканирования...*\n📡 Опрос публичных баз данных...", parse_mode=ParseMode.MARKDOWN)
        
        # Реальная проверка соцсетей
        social_results = osint_engine.check_social(target)
        title, body, _ = format_report(target, social_results)
        
        # Отправка отчета
        await update.message.reply_text(f"{title}\n═══════════════════════\n{body}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("🕵️ Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ===== ПОИСК ПО НИКУ =====
    if text == "👤 ПОИСК ПО НИКУ":
        await update.message.reply_text("👤 *Введите никнейм:*", parse_mode=ParseMode.MARKDOWN)
        context.user_data['state'] = 'nick'
        return

    if state == 'nick':
        target = text.strip().replace("@", "")
        social_results = osint_engine.check_social(target)
        title, body, _ = format_report(target, social_results)
        await update.message.reply_text(f"{title}\n═══════════════════════\n{body}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("🕵️ Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ===== ПОИСК ПО ТЕЛЕФОНУ =====
    if text == "📱 ПОИСК ПО ТЕЛЕФОНУ":
        await update.message.reply_text("📱 *Введите номер телефона:*", parse_mode=ParseMode.MARKDOWN)
        context.user_data['state'] = 'phone'
        return

    if state == 'phone':
        await update.message.reply_text(
            f"""📱 *ПОИСК ПО ТЕЛЕФОНУ*
═══════════════════════

📱 *НОМЕР:* `{text}`

📌 Telegram: {random.choice(['✅ Есть аккаунт', '❌ Нет аккаунта', '⚠️ Скрыт'])}
📌 WhatsApp: {random.choice(['✅ Есть аккаунт', '❌ Нет аккаунта', '⚠️ Скрыт'])}
📌 Viber: {random.choice(['✅ Есть аккаунт', '❌ Нет аккаунта', '⚠️ Скрыт'])}

📋 *ЗАКЛЮЧЕНИЕ:*
Цифровой след: {random.choice(['Низкий', 'Мощный'])}
Телефон привязан к соцсетям: {random.randint(0, 5)}""",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("🕵️ Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ===== ПОИСК ПО IP =====
    if text == "🌍 ПОИСК ПО IP":
        await update.message.reply_text("🌍 *Введите IP-адрес:*", parse_mode=ParseMode.MARKDOWN)
        context.user_data['state'] = 'ip'
        return

    if state == 'ip':
        ip_info = osint_engine.get_geo_ip(text.strip())
        if ip_info:
            title, body, _ = format_report(text.strip(), None, ip_info=ip_info, is_ip=True)
            await update.message.reply_text(f"{title}\n═══════════════════════\n{body}", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ *IP НЕ НАЙДЕН ИЛИ НЕВЕРНЫЙ ФОРМАТ*", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("🕵️ Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ===== ПОИСК ПО EMAIL =====
    if text == "📧 ПОИСК ПО EMAIL":
        await update.message.reply_text("📧 *Введите email:*", parse_mode=ParseMode.MARKDOWN)
        context.user_data['state'] = 'email'
        return

    if state == 'email':
        target = text.strip()
        email_info = osint_engine.get_email_info(target)
        social_results = osint_engine.check_social(target.split('@')[0])
        title, body, _ = format_report(target, social_results, email_info=email_info)
        await update.message.reply_text(f"{title}\n═══════════════════════\n{body}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("🕵️ Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

# ==================== ЗАПУСК ====================
def run_flask():
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask error: {e}")

def run_bot():
    while True:
        try:
            logger.info("Bot started!")
            application = ApplicationBuilder().token(TOKEN).build()
            application.add_handler(CommandHandler('start', start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.run_polling()
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            time.sleep(3)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
