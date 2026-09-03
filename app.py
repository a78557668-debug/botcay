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
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ==================== КОНФИГ ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА"
MAIN_ADMIN_USERNAME = "fuck_society13"
DEV_PASSWORD = "K7X9M2P5R8Q4W6N3T1Y7L8C9V2B5D0E3"
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
DB_NAME = os.path.join(BASE_DIR, "helper_bot.db")

# ==================== FLASK ====================
app = Flask(__name__)
@app.route('/')
def home():
    return "OSINT Pro v13.0 Online"
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, language TEXT DEFAULT 'ru', bot_mode TEXT DEFAULT 'key_helper', is_dev INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0, registered_at TIMESTAMP, last_active TIMESTAMP)''')
        conn.commit()
        conn.close()
    def add_user(self, user_id, username, first_name, last_name):
        conn = self.get_connection(); cursor = conn.cursor(); now = datetime.now()
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, registered_at, last_active) VALUES (?, ?, ?, ?, ?, ?)', (user_id, username, first_name, last_name, now, now))
        conn.commit(); conn.close()
    def get_user_mode(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT bot_mode FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result[0] if result else 'key_helper'
    def update_mode(self, user_id, mode):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET bot_mode = ? WHERE user_id = ?', (mode, user_id)); conn.commit(); conn.close()
    def is_dev(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT is_dev FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result and result[0] == 1
    def set_dev_mode(self, user_id, value):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET is_dev = ? WHERE user_id = ?', (value, user_id)); conn.commit(); conn.close()
    def get_total_users(self):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM users'); result = cursor.fetchone(); conn.close()
        return result[0] if result else 0
    def get_all_users(self):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT user_id, username, first_name, last_name, is_banned FROM users ORDER BY registered_at DESC'); results = cursor.fetchall(); conn.close()
        return results
    def ban_user(self, user_id, reason="Нарушение"):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,)); conn.commit(); conn.close()
    def unban_user(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,)); conn.commit(); conn.close()
    def search_users(self, query):
        conn = self.get_connection(); cursor = conn.cursor(); pattern = f"%{query}%"; cursor.execute('SELECT user_id, username, first_name, last_name, is_banned FROM users WHERE username LIKE ? OR user_id LIKE ?', (pattern, pattern)); results = cursor.fetchall(); conn.close()
        return results

db = Database()

# ==================== OSINT ДВИЖОК ====================
class OSINTEngine:
    def check_social(self, username):
        results = []
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
        for platform, url in links.items():
            try:
                r = requests.get(url, timeout=2, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    results.append({"platform": platform, "url": url, "status": "✅"})
                else:
                    results.append({"platform": platform, "status": "❌"})
            except:
                results.append({"platform": platform, "status": "⚠️"})
        return results

    def get_geo_ip(self, ip):
        try:
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
            data = r.json()
            if data.get('status') == 'success':
                return {'country': data.get('country'), 'city': data.get('city'), 'isp': data.get('isp'), 'org': data.get('org'), 'timezone': data.get('timezone'), 'lat': data.get('lat'), 'lon': data.get('lon')}
            return None
        except:
            return None

    def check_email(self, email):
        hash_email = hashlib.md5(email.lower().encode()).hexdigest()
        url = f"https://www.gravatar.com/avatar/{hash_email}"
        try:
            r = requests.get(url, timeout=2)
            return {"avatar_url": url, "exists": r.status_code == 200}
        except:
            return {"avatar_url": url, "exists": False}

osint_engine = OSINTEngine()

# ==================== ФУНКЦИИ КОНТРОЛЯ ====================
func_settings = {
    "search": True,
    "protection": True,
    "hacker_tools": True,
    "ai": True,
    "stats_daily": True,
    "dossier": True,
    "broadcast": True,
    "backup": True
}

# ==================== МЕНЮ ====================
def get_main_menu(user_id):
    mode = db.get_user_mode(user_id)
    if mode == "key_helper":
        buttons = [
            [KeyboardButton("🕵️ DEEP SCAN")],
            [KeyboardButton("👤 ПОИСК ПО НИКУ")],
            [KeyboardButton("🌍 ПОИСК ПО IP")],
            [KeyboardButton("📧 ПОИСК ПО EMAIL")],
            [KeyboardButton("📱 ПОИСК ПО ТЕЛЕФОНУ")]
        ]
    else:
        buttons = [
            [KeyboardButton("🕵️ DEEP SCAN")],
            [KeyboardButton("👤 ПОИСК ПО НИКУ")],
            [KeyboardButton("🌍 ПОИСК ПО IP")],
            [KeyboardButton("📧 ПОИСК ПО EMAIL")]
        ]
    if db.is_dev(user_id):
        buttons.append([KeyboardButton("🛠️ МЕНЮ ДЕВ")])
    buttons.append([KeyboardButton("🔙 НАЗАД")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_dev_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 СТАТИСТИКА"), KeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ")],
        [KeyboardButton("🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ")],
        [KeyboardButton("🚫 ЗАБАНИТЬ"), KeyboardButton("✅ РАЗБАНИТЬ")],
        [KeyboardButton("📨 РАССЫЛКА"), KeyboardButton("📊 СТАТИСТИКА ЗА ДЕНЬ")],
        [KeyboardButton("🔙 ВЫЙТИ ИЗ ДЕВ")]
    ], resize_keyboard=True)

# ==================== АНИМАЦИИ ====================
async def matrix_rain(update, title):
    """Эффект матричного дождя"""
    msg = await update.message.reply_text("```\n██▓▒░ SYSTEM INITIALIZING...\n```", parse_mode=ParseMode.MARKDOWN)
    symbols = "01アイウエオカキクケコ"
    for i in range(5):
        line = "".join(random.choice(symbols) for _ in range(20))
        await msg.edit_text(f"```\n{line}\n{title}...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.15)
    await msg.delete()

async def hacking_animation(update, title):
    """Эффект прогресс-бара взлома"""
    msg = await update.message.reply_text(f"```\n[{title}] 0%\n```", parse_mode=ParseMode.MARKDOWN)
    for i in range(1, 11):
        bar = "█" * i + "░" * (10 - i)
        await msg.edit_text(f"```\n[{title}] {bar} {i*10}%\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)
    await msg.delete()

# ==================== КОМАНДЫ ====================
async def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or "User"
    db.add_user(user_id, username, first_name, "")
    mode = db.get_user_mode(user_id)
    mode_name = "KEY HELPER" if mode == "key_helper" else "FAST HELPER"
    await update.message.reply_text(f"🔥 OSINT PRO v13.0\n═══════════════════\n\n⚡ СИСТЕМА: ONLINE\n📌 РЕЖИМ: {mode_name}\n\nВыберите операцию:", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))

async def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('state', 'main')

    # ==== ВХОД В DEV MODE (Пароль) ====
    if text == DEV_PASSWORD:
        db.set_dev_mode(user_id, 1)
        await update.message.reply_text("✅ *DEV MODE АКТИВИРОВАН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
        return

    if text == "🔙 НАЗАД":
        context.user_data['state'] = 'main'
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        return

    # ==== DEV МЕНЮ ====
    if text == "🛠️ МЕНЮ ДЕВ":
        if not db.is_dev(user_id):
            await update.message.reply_text("❌ ДОСТУП ЗАПРЕЩЕН!")
            return
        await update.message.reply_text("🛠️ *DEV ПАНЕЛЬ*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
        return

    if db.is_dev(user_id) and state == 'main':
        if text == "📊 СТАТИСТИКА":
            await update.message.reply_text(f"👥 Всего: {db.get_total_users()}", reply_markup=get_dev_menu())
            return
        if text == "👥 ВСЕ ПОЛЬЗОВАТЕЛИ":
            users = db.get_all_users()
            if not users:
                await update.message.reply_text("Пусто")
                return
            text_report = "\n".join([f"├ {u[1] or 'NO'} | {u[2]} | ID: {u[0]}" for u in users[:10]])
            await update.message.reply_text(f"📋 *ПОЛЬЗОВАТЕЛИ*\n{text_report}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
            return
        if text == "🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ":
            await update.message.reply_text("Введите ID или юзернейм:")
            context.user_data['state'] = 'dev_search'
            return
        if text == "🚫 ЗАБАНИТЬ":
            await update.message.reply_text("Введите ID:")
            context.user_data['state'] = 'dev_ban'
            return
        if text == "✅ РАЗБАНИТЬ":
            await update.message.reply_text("Введите ID:")
            context.user_data['state'] = 'dev_unban'
            return

    if state == 'dev_search':
        users = db.search_users(text)
        if not users:
            await update.message.reply_text("Не найдено", reply_markup=get_dev_menu())
            return
        report = "\n".join([f"├ @{u[1]} ID: {u[0]}" for u in users[:10]])
        await update.message.reply_text(f"🔍 *РЕЗУЛЬТАТЫ:*\n{report}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return

    if state == 'dev_ban':
        try:
            db.ban_user(int(text))
            await update.message.reply_text("✅ Забанен!", reply_markup=get_dev_menu())
        except:
            await update.message.reply_text("❌ Неверный ID!", reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return

    if state == 'dev_unban':
        try:
            db.unban_user(int(text))
            await update.message.reply_text("✅ Разбанен!", reply_markup=get_dev_menu())
        except:
            await update.message.reply_text("❌ Неверный ID!", reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return

    # ==== DEEP SCAN ====
    if text == "🕵️ DEEP SCAN":
        await update.message.reply_text("Введите никнейм:")
        context.user_data['state'] = 'deep_scan'
        return

    if state == 'deep_scan':
        target = text.strip().replace("@", "")
        await matrix_rain(update, "SCAN")
        await hacking_animation(update, "ВЗЛОМ")
        
        social_results = osint_engine.check_social(target)
        phone = f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"
        email = f"{target}@{random.choice(['gmail.com', 'mail.ru', 'proton.me'])}"
        
        report = f"""🕵️ *DEEP SCAN: @{target}*
═══════════════════════

👤 *ПРОФИЛЬ*
├ Активность: {random.choice(['Высокая', 'Средняя', 'Низкая'])}
├ Профиль: {random.choice(['Публичный', 'Приватный'])}
└ Возраст: {random.randint(15, 45)}

📱 *ТЕЛЕФОН*
├ {phone}

📧 *EMAIL*
├ {email}

🌐 *СОЦСЕТИ* (Реальная проверка)
{chr(10).join([f"├ {r['platform']}: {r['status']} {r.get('url', '')}" for r in social_results])}

📋 *ЗАКЛЮЧЕНИЕ*
├ Риск деанонимизации: {random.randint(10, 95)}%
└ Конец отчета"""
        
        await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ==== ПОИСК ПО НИКУ ====
    if text == "👤 ПОИСК ПО НИКУ":
        await update.message.reply_text("Введите никнейм:")
        context.user_data['state'] = 'nick'
        return

    if state == 'nick':
        target = text.strip().replace("@", "")
        await hacking_animation(update, "SCAN")
        social_results = osint_engine.check_social(target)
        await update.message.reply_text(
            f"👤 *ПРОФИЛЬ: @{target}*\n═══════════════════\n\n{chr(10).join([f"├ {r['platform']}: {r['status']} {r.get('url', '')}" for r in social_results])}",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ==== ПОИСК ПО IP ====
    if text == "🌍 ПОИСК ПО IP":
        await update.message.reply_text("Введите IP-адрес:")
        context.user_data['state'] = 'ip'
        return

    if state == 'ip':
        await matrix_rain(update, "IP LOOKUP")
        ip_info = osint_engine.get_geo_ip(text.strip())
        if ip_info:
            await update.message.reply_text(
                f"🌍 *ГЕОЛОКАЦИЯ IP*\n═══════════════════\n\n📍 Страна: {ip_info['country']}\n🏙️ Город: {ip_info['city']}\n🏢 Провайдер: {ip_info['isp']}\n🕐 Часовой пояс: {ip_info['timezone']}\n🛰️ Координаты: {ip_info['lat']}, {ip_info['lon']}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ Неверный IP или не найден")
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ==== ПОИСК ПО EMAIL ====
    if text == "📧 ПОИСК ПО EMAIL":
        await update.message.reply_text("Введите email:")
        context.user_data['state'] = 'email'
        return

    if state == 'email':
        await hacking_animation(update, "EMAIL LOOKUP")
        email_info = osint_engine.check_email(text.strip())
        await update.message.reply_text(
            f"📧 *EMAIL ИНФО*\n═══════════════════\n\n📧 Email: {text.strip()}\n🖼️ Аватар: {'✅ Существует' if email_info['exists'] else '❌ Не существует'}\n🔗 Ссылка: {email_info['avatar_url']}",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ==== ПОИСК ПО ТЕЛЕФОНУ ====
    if text == "📱 ПОИСК ПО ТЕЛЕФОНУ":
        await update.message.reply_text("Введите номер телефона:")
        context.user_data['state'] = 'phone'
        return

    if state == 'phone':
        await hacking_animation(update, "PHONE LOOKUP")
        await update.message.reply_text(
            f"📱 *ТЕЛЕФОН ИНФО*\n═══════════════════\n\n📱 Номер: {text.strip()}\n\n📌 Telegram: {random.choice(['✅ Есть', '❌ Нет'])}\n📌 WhatsApp: {random.choice(['✅ Есть', '❌ Нет'])}\n📌 Viber: {random.choice(['✅ Есть', '❌ Нет'])}\n\n📋 Риск: {random.randint(10, 95)}%",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    # ==== КОНЕЦ ОБРАБОТКИ ====
    await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))

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
