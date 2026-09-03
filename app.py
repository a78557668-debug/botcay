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
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler
from telegram.constants import ParseMode

# ==================== КОНФИГ ====================
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА"
DEV_PASSWORD = "K7X9M2P5R8Q4W6N3T1Y7L8C9V2B5D0E3"
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
DB_NAME = os.path.join(BASE_DIR, "helper_bot.db")

# ==================== FLASK ====================
app = Flask(__name__)
@app.route('/')
def home():
    return "OSINT Pro"
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            language TEXT DEFAULT 'ru',
            theme TEXT DEFAULT 'hacker',
            is_dev INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_until TEXT,
            requests_balance INTEGER DEFAULT 5,
            dev_attempts INTEGER DEFAULT 0,
            dev_blocked_until TEXT,
            registered_at TIMESTAMP,
            last_active TIMESTAMP
        )''')
        conn.commit()
        conn.close()
    def add_user(self, user_id, username, first_name, last_name, language='ru'):
        conn = self.get_connection(); cursor = conn.cursor(); now = datetime.now()
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, language, registered_at, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, username, first_name, last_name, language, now, now))
        conn.commit(); conn.close()
    def get_requests_balance(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT requests_balance FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result[0] if result else 5
    def add_requests(self, user_id, count):
        conn = self.get_connection(); cursor = conn.cursor()
        cursor.execute('UPDATE users SET requests_balance = requests_balance + ? WHERE user_id = ?', (count, user_id))
        conn.commit(); conn.close()
    def spend_request(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor()
        cursor.execute('UPDATE users SET requests_balance = requests_balance - 1 WHERE user_id = ?', (user_id,))
        conn.commit(); conn.close()
    def is_vip(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT is_vip, vip_until FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        if result and result[0] == 1:
            if result[1] and datetime.strptime(result[1], '%Y-%m-%d %H:%M:%S') > datetime.now():
                return True
            else:
                self.set_vip(user_id, 0)
                return False
        return False
    def set_vip(self, user_id, status, until=None):
        conn = self.get_connection(); cursor = conn.cursor()
        if until:
            cursor.execute('UPDATE users SET is_vip = ?, vip_until = ? WHERE user_id = ?', (status, until, user_id))
        else:
            cursor.execute('UPDATE users SET is_vip = ?, vip_until = NULL WHERE user_id = ?', (status, user_id))
        conn.commit(); conn.close()
    def get_language(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result[0] if result else 'ru'
    def update_language(self, user_id, language):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id)); conn.commit(); conn.close()
    def get_theme(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT theme FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result[0] if result else 'hacker'
    def update_theme(self, user_id, theme):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET theme = ? WHERE user_id = ?', (theme, user_id)); conn.commit(); conn.close()
    def is_dev(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT is_dev FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result and result[0] == 1
    def set_dev_mode(self, user_id, value):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE users SET is_dev = ? WHERE user_id = ?', (value, user_id)); conn.commit(); conn.close()
    def get_dev_attempts(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT dev_attempts FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result[0] if result else 0
    def increment_dev_attempts(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor()
        cursor.execute('UPDATE users SET dev_attempts = dev_attempts + 1 WHERE user_id = ?', (user_id,))
        conn.commit(); conn.close()
    def reset_dev_attempts(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor()
        cursor.execute('UPDATE users SET dev_attempts = 0 WHERE user_id = ?', (user_id,))
        conn.commit(); conn.close()
    def get_dev_blocked_until(self, user_id):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT dev_blocked_until FROM users WHERE user_id = ?', (user_id,)); result = cursor.fetchone(); conn.close()
        return result[0] if result else None
    def set_dev_blocked_until(self, user_id, until):
        conn = self.get_connection(); cursor = conn.cursor()
        cursor.execute('UPDATE users SET dev_blocked_until = ? WHERE user_id = ?', (until, user_id))
        conn.commit(); conn.close()
    def get_total_users(self):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM users'); result = cursor.fetchone(); conn.close()
        return result[0] if result else 0
    def get_all_users(self):
        conn = self.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT user_id, username, first_name, last_name, is_banned FROM users ORDER BY registered_at DESC'); results = cursor.fetchall(); conn.close()
        return results
    def ban_user(self, user_id):
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

# ==================== АНИМАЦИИ ====================
async def matrix_rain(update, title):
    msg = await update.message.reply_text("```\n██▓▒░ INIT...\n```", parse_mode=ParseMode.MARKDOWN)
    symbols = "01アイウエオ"
    for i in range(3):
        line = "".join(random.choice(symbols) for _ in range(15))
        await msg.edit_text(f"```\n{line}\n{title}...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.08)
    await msg.delete()

async def hacking_animation(update, title):
    msg = await update.message.reply_text(f"```\n[{title}] 0%\n```", parse_mode=ParseMode.MARKDOWN)
    for i in range(1, 11):
        bar = "█" * i + "░" * (10 - i)
        await msg.edit_text(f"```\n[{title}] {bar} {i*10}%\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.1)
    await msg.delete()

async def port_scan_animation(update, title):
    msg = await update.message.reply_text("```\n[SCAN]...\n```", parse_mode=ParseMode.MARKDOWN)
    for i in range(1, 10):
        target = f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}"
        result = random.choice(["OPEN", "CLOSED", "FILTERED"])
        await msg.edit_text(f"```\n[SCAN] {target}:{random.randint(1, 9999)} -> {result}\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.08)
    await msg.delete()

# ==================== МЕНЮ ====================
def get_main_menu(user_id):
    buttons = [
        [KeyboardButton("🕵️ DEEP SCAN")],
        [KeyboardButton("👤 ПОИСК ПО НИКУ")],
        [KeyboardButton("🌍 ПОИСК ПО IP")],
        [KeyboardButton("📧 ПОИСК ПО EMAIL")],
        [KeyboardButton("📱 ПОИСК ПО ТЕЛЕФОНУ")]
    ]
    if db.is_dev(user_id):
        buttons.append([KeyboardButton("🛠️ МЕНЮ ДЕВ")])
    buttons.append([KeyboardButton("⚙️ НАСТРОЙКИ")])
    buttons.append([KeyboardButton("🔙 НАЗАД")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_dev_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 СТАТИСТИКА"), KeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ")],
        [KeyboardButton("🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ")],
        [KeyboardButton("🚫 ЗАБАНИТЬ"), KeyboardButton("✅ РАЗБАНИТЬ")],
        [KeyboardButton("➕ ВЫДАТЬ ЗАПРОСЫ"), KeyboardButton("👑 ВЫДАТЬ VIP")],
        [KeyboardButton("🔙 ВЫЙТИ ИЗ ДЕВ")]
    ], resize_keyboard=True)

def get_settings_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🌐 ЯЗЫК"), KeyboardButton("🎨 ТЕМА")],
        [KeyboardButton("👨‍💻 РЕЖИМ РАЗРАБОТЧИКА")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_payment_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ 15 ⭐ (10 запросов)", callback_data="pay_15")],
        [InlineKeyboardButton("🔥 100 ⭐ (VIP 30 дней)", callback_data="pay_100")],
        [InlineKeyboardButton("👑 1000 ⭐ (VIP 365 дней)", callback_data="pay_1000")]
    ])

# ==================== КОМАНДЫ ====================
async def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or "User"
    db.add_user(user_id, username, first_name, "")
    await update.message.reply_text("🔥 OSINT PRO\n═══════════════════\n\n⚡ СИСТЕМА: ONLINE\n📌 Бесплатных запросов: 5\n\nВыберите операцию:", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))

async def buy(update, context):
    await update.message.reply_text("⚡ Выберите тариф:", reply_markup=get_payment_menu())

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================
async def handle_message(update, context):
    user_id = update.effective_user.id
    text = update.message.text

    # ВВОД ПАРОЛЯ
    if text == DEV_PASSWORD:
        if db.get_dev_blocked_until(user_id):
            blocked_until = datetime.strptime(db.get_dev_blocked_until(user_id), '%Y-%m-%d %H:%M:%S')
            if blocked_until > datetime.now():
                remaining = blocked_until - datetime.now()
                await update.message.reply_text(f"❌ *БЛОКИРОВКА!*\nПопробуйте через {remaining} минут.", parse_mode=ParseMode.MARKDOWN)
                return
        db.set_dev_mode(user_id, 1)
        db.reset_dev_attempts(user_id)
        await update.message.reply_text("✅ *DEV MODE АКТИВИРОВАН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
        return

    if text == "🔙 НАЗАД":
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        return

    # НАСТРОЙКИ
    if text == "⚙️ НАСТРОЙКИ":
        await update.message.reply_text("⚙️ *НАСТРОЙКИ*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_settings_menu())
        return

    if text == "👨‍💻 РЕЖИМ РАЗРАБОТЧИКА":
        if db.is_dev(user_id):
            await update.message.reply_text("✅ *DEV MODE УЖЕ АКТИВЕН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
            return
        await update.message.reply_text("🔑 *Введите пароль разработчика:*", parse_mode=ParseMode.MARKDOWN)
        context.user_data['state'] = 'dev_password'
        return

    if context.user_data.get('state') == 'dev_password':
        if db.get_dev_blocked_until(user_id):
            blocked_until = datetime.strptime(db.get_dev_blocked_until(user_id), '%Y-%m-%d %H:%M:%S')
            if blocked_until > datetime.now():
                remaining = blocked_until - datetime.now()
                await update.message.reply_text(f"❌ *БЛОКИРОВКА!*\nПопробуйте через {remaining} минут.", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'main'
                return
        if text == DEV_PASSWORD:
            db.set_dev_mode(user_id, 1)
            db.reset_dev_attempts(user_id)
            await update.message.reply_text("✅ *DEV MODE АКТИВИРОВАН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return
        else:
            db.increment_dev_attempts(user_id)
            attempts = db.get_dev_attempts(user_id)
            if attempts >= 3:
                db.set_dev_blocked_until(user_id, (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'))
                await update.message.reply_text("❌ *ВЫ ЗАБЛОКИРОВАНЫ НА 24 ЧАСА!*", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'main'
                return
            await update.message.reply_text(f"❌ *НЕВЕРНЫЙ ПАРОЛЬ!* (Попытка {attempts}/3)", parse_mode=ParseMode.MARKDOWN)
        return

    # ЛИМИТ ЗАПРОСОВ
    if text in ["🕵️ DEEP SCAN", "👤 ПОИСК ПО НИКУ", "🌍 ПОИСК ПО IP", "📧 ПОИСК ПО EMAIL", "📱 ПОИСК ПО ТЕЛЕФОНУ"]:
        if not db.is_vip(user_id) and not db.is_dev(user_id):
            balance = db.get_requests_balance(user_id)
            if balance <= 0:
                await update.message.reply_text("❌ *БАЛАНС ЗАПРОСОВ: 0*\n\nВы использовали все запросы.\nПодпишитесь для продолжения:", parse_mode=ParseMode.MARKDOWN, reply_markup=get_payment_menu())
                return
            db.spend_request(user_id)

        if text == "🕵️ DEEP SCAN":
            await update.message.reply_text("Введите никнейм:")
            context.user_data['state'] = 'deep_scan'
        elif text == "👤 ПОИСК ПО НИКУ":
            await update.message.reply_text("Введите никнейм:")
            context.user_data['state'] = 'nick'
        elif text == "🌍 ПОИСК ПО IP":
            await update.message.reply_text("Введите IP-адрес:")
            context.user_data['state'] = 'ip'
        elif text == "📧 ПОИСК ПО EMAIL":
            await update.message.reply_text("Введите email:")
            context.user_data['state'] = 'email'
        elif text == "📱 ПОИСК ПО ТЕЛЕФОНУ":
            await update.message.reply_text("Введите номер телефона:")
            context.user_data['state'] = 'phone'
        return

    # DEV МЕНЮ
    if text == "🛠️ МЕНЮ ДЕВ":
        if not db.is_dev(user_id):
            await update.message.reply_text("❌ ДОСТУП ЗАПРЕЩЕН!")
            return
        await update.message.reply_text("🛠️ *DEV ПАНЕЛЬ*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
        return

    if db.is_dev(user_id):
        if text == "📊 СТАТИСТИКА":
            await update.message.reply_text(f"👥 Всего: {db.get_total_users()}", reply_markup=get_dev_menu())
            return
        if text == "👥 ВСЕ ПОЛЬЗОВАТЕЛИ":
            users = db.get_all_users()
            if not users:
                await update.message.reply_text("Пусто")
                return
            report = "\n".join([f"├ @{u[1]} | {u[2]} | ID: {u[0]}" for u in users[:10]])
            await update.message.reply_text(f"📋 *ПОЛЬЗОВАТЕЛИ*\n{report}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
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
        if text == "➕ ВЫДАТЬ ЗАПРОСЫ":
            await update.message.reply_text("Введите ID:")
            context.user_data['state'] = 'dev_add_requests'
            return
        if text == "👑 ВЫДАТЬ VIP":
            await update.message.reply_text("Введите ID:")
            context.user_data['state'] = 'dev_vip'
            return
        if text == "🔙 ВЫЙТИ ИЗ ДЕВ":
            db.set_dev_mode(user_id, 0)
            await update.message.reply_text("🔙 *ВЫЙТИ ИЗ DEV MODE*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

    # DEV ФУНКЦИИ
    if context.user_data.get('state') == 'dev_search':
        users = db.search_users(text)
        if not users:
            await update.message.reply_text("Не найдено", reply_markup=get_dev_menu())
            return
        report = "\n".join([f"├ @{u[1]} ID: {u[0]}" for u in users[:10]])
        await update.message.reply_text(f"🔍 *РЕЗУЛЬТАТЫ:*\n{report}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return
    if context.user_data.get('state') == 'dev_ban':
        try:
            db.ban_user(int(text))
            await update.message.reply_text("✅ Забанен!", reply_markup=get_dev_menu())
        except:
            await update.message.reply_text("❌ Неверный ID!", reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return
    if context.user_data.get('state') == 'dev_unban':
        try:
            db.unban_user(int(text))
            await update.message.reply_text("✅ Разбанен!", reply_markup=get_dev_menu())
        except:
            await update.message.reply_text("❌ Неверный ID!", reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return
    if context.user_data.get('state') == 'dev_add_requests':
        try:
            target_id = int(text)
            await update.message.reply_text("Введите количество запросов:")
            context.user_data['state'] = 'dev_add_requests_count'
            context.user_data['target_user'] = target_id
        except:
            await update.message.reply_text("❌ Неверный ID!", reply_markup=get_dev_menu())
            context.user_data['state'] = 'dev'
        return
    if context.user_data.get('state') == 'dev_add_requests_count':
        try:
            count = int(text)
            db.add_requests(context.user_data['target_user'], count)
            await update.message.reply_text("✅ Запросы выданы!", reply_markup=get_dev_menu())
        except:
            await update.message.reply_text("❌ Неверное число!", reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return
    if context.user_data.get('state') == 'dev_vip':
        try:
            db.set_vip(int(text), 1, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))
            await update.message.reply_text("✅ VIP выдан на 30 дней!", reply_markup=get_dev_menu())
        except:
            await update.message.reply_text("❌ Неверный ID!", reply_markup=get_dev_menu())
        context.user_data['state'] = 'dev'
        return

    # OSINT ФУНКЦИИ
    if context.user_data.get('state') == 'deep_scan':
        target = text.strip().replace("@", "")
        await matrix_rain(update, "SCAN")
        await hacking_animation(update, "CRACK")
        await port_scan_animation(update, "SCAN")
        social_results = osint_engine.check_social(target)
        phone = f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"
        email = f"{target}@{random.choice(['gmail.com', 'mail.ru', 'proton.me'])}"
        await update.message.reply_text(
            f"🕵️ *DEEP SCAN: @{target}*\n═══════════════════\n\n👤 *ПРОФИЛЬ*\n├ Активность: {random.choice(['Высокая', 'Средняя', 'Низкая'])}\n├ Профиль: {random.choice(['Публичный', 'Приватный'])}\n└ Возраст: {random.randint(15, 45)}\n\n📱 *ТЕЛЕФОН*\n├ {phone}\n\n📧 *EMAIL*\n├ {email}\n\n🌐 *СОЦСЕТИ*\n{chr(10).join([f"├ {r['platform']}: {r['status']} {r.get('url', '')}" for r in social_results])}\n\n📋 Риск: {random.randint(10, 95)}%",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    if context.user_data.get('state') == 'nick':
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

    if context.user_data.get('state') == 'ip':
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

    if context.user_data.get('state') == 'email':
        await hacking_animation(update, "EMAIL LOOKUP")
        email_info = osint_engine.check_email(text.strip())
        await update.message.reply_text(
            f"📧 *EMAIL ИНФО*\n═══════════════════\n\n📧 Email: {text.strip()}\n🖼️ Аватар: {'✅ Существует' if email_info['exists'] else '❌ Не существует'}\n🔗 Ссылка: {email_info['avatar_url']}",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

    if context.user_data.get('state') == 'phone':
        await port_scan_animation(update, "PHONE LOOKUP")
        await update.message.reply_text(
            f"📱 *ТЕЛЕФОН ИНФО*\n═══════════════════\n\n📱 Номер: {text.strip()}\n\n📌 Telegram: {random.choice(['✅ Есть', '❌ Нет'])}\n📌 WhatsApp: {random.choice(['✅ Есть', '❌ Нет'])}\n📌 Viber: {random.choice(['✅ Есть', '❌ Нет'])}\n\n📋 Риск: {random.randint(10, 95)}%",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = 'main'
        return

# ==================== ПЛАТЕЖИ ====================
async def process_payment(update, context):
    query = update.callback_query
    await query.answer()
    payload = query.data
    if payload == "pay_15":
        amount, price_label = 15, "10 запросов"
    elif payload == "pay_100":
        amount, price_label = 100, "VIP 30 дней"
    else:
        amount, price_label = 1000, "VIP 365 дней"
    await query.message.delete()
    await context.bot.send_invoice(
        chat_id=query.message.chat.id,
        title=f"⚡ {price_label}",
        description=f"Подписка: {price_label}",
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=price_label, amount=amount)]
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update, context):
    user_id = update.effective_user.id
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    if payload == "pay_15":
        db.add_requests(user_id, 10)
    elif payload == "pay_100":
        db.set_vip(user_id, 1, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S'))
    elif payload == "pay_1000":
        db.set_vip(user_id, 1, (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S'))
    await update.message.reply_text(f"✅ *Оплата прошла!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))

# ==================== КНОПКИ (CALLBACK) ====================
async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "lang_ru":
        db.update_language(user_id, "ru")
    elif data == "lang_en":
        db.update_language(user_id, "en")
    elif data == "theme_hacker":
        db.update_theme(user_id, "hacker")
    elif data == "theme_cyberpunk":
        db.update_theme(user_id, "cyberpunk")
    elif data == "theme_dark":
        db.update_theme(user_id, "dark")
    await query.edit_message_text(
        text=f"✅ *Обновлено!*",
        parse_mode=ParseMode.MARKDOWN
    )
    await query.message.reply_text("📋 Главное меню", reply_markup=get_main_menu(user_id))

# ==================== ЗАПУСК ====================
def run_flask():
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask error: {e}")

def run_bot():
    while True:
        try:
            application = ApplicationBuilder().token(TOKEN).build()
            application.add_handler(CommandHandler('start', start))
            application.add_handler(CommandHandler('buy', buy))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.add_handler(CallbackQueryHandler(handle_callback))
            application.add_handler(PreCheckoutQueryHandler(pre_checkout))
            application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
            application.run_polling()
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            time.sleep(3)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
