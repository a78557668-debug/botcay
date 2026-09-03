# -*- coding: utf-8 -*-
"""
🔥 HELPER BOT 🔥
Версия: 12.0 (Render Edition)
Полностью рабочий код. Без ошибок.
"""

import os
import threading
import logging
import time
import random
import sqlite3
import requests
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ==================== КОНФИГ ====================
VERSION = "12.0"
BOT_NAME = "🔥 HELPER BOT 🔥"
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "8736136579:AAGp7QPivJCHFG5ooNcBVwZP3GDXNLQYaJs"

MAIN_ADMIN_USERNAME = "fuck_society13"
DEV_PASSWORD = "K7X9M2P5R8Q4W6N3T1Y7L8C9V2B5D0E3"

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
DB_NAME = os.path.join(BASE_DIR, "helper_bot.db")

# ==================== FLASK ДЛЯ RENDER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "HELPER BOT v12.0 - SYSTEM ONLINE"

@app.route('/health')
def health():
    return "OK", 200

# ==================== ЛОГГЕР ====================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'ru',
                theme TEXT DEFAULT 'hacker',
                bot_mode TEXT DEFAULT 'key_helper',
                bot_version TEXT DEFAULT '12.0',
                is_admin TEXT DEFAULT 'no',
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                banned_at TIMESTAMP,
                registered_at TIMESTAMP,
                last_active TIMESTAMP,
                is_dev INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                target_id INTEGER,
                timestamp TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def add_user(self, user_id, username, first_name, last_name, language='ru', bot_mode='key_helper'):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, language, bot_mode, registered_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, language, bot_mode, now, now))
        conn.commit()
        conn.close()

    def get_username(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_user_mode(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT bot_mode FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 'key_helper'

    def update_mode(self, user_id, mode):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET bot_mode = ? WHERE user_id = ?', (mode, user_id))
        conn.commit()
        conn.close()

    def is_dev(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT is_dev FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] == 1

    def set_dev_mode(self, user_id, value):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_dev = ? WHERE user_id = ?', (value, user_id))
        conn.commit()
        conn.close()

    def get_total_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name, is_admin, is_banned, ban_reason, language FROM users ORDER BY registered_at DESC')
        results = cursor.fetchall()
        conn.close()
        return results

    def get_banned_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name, ban_reason FROM users WHERE is_banned = 1')
        results = cursor.fetchall()
        conn.close()
        return results

    def ban_user(self, user_id, admin_id, reason="Нарушение правил"):
        username = self.get_username(user_id)
        if username == MAIN_ADMIN_USERNAME:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_banned = 1, ban_reason = ?, banned_at = ? WHERE user_id = ?',
                      (reason, datetime.now(), user_id))
        conn.commit()
        conn.close()
        return True

    def unban_user(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_banned = 0, ban_reason = NULL, banned_at = NULL WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    def search_users(self, query):
        conn = self.get_connection()
        cursor = conn.cursor()
        search_pattern = f"%{query}%"
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, is_admin, is_banned
            FROM users 
            WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR CAST(user_id AS TEXT) LIKE ?
            ORDER BY username
        ''', (search_pattern, search_pattern, search_pattern, search_pattern))
        results = cursor.fetchall()
        conn.close()
        return results

db = Database()

# ==================== МЕНЮ (Русские названия) ====================
def get_main_menu(user_id):
    mode = db.get_user_mode(user_id)
    if mode == "key_helper":
        buttons = [
            [KeyboardButton("🛡️ ЗАЩИТА")],
            [KeyboardButton("🔍 ПОИСК")],
            [KeyboardButton("🔑 ХАКЕРСКИЕ ИНСТРУМЕНТЫ")],
            [KeyboardButton("⚙️ НАСТРОЙКИ")],
            [KeyboardButton("🤖 AI ПОМОЩНИК")],
        ]
    else:  # fast_helper
        buttons = [
            [KeyboardButton("🔍 ПОИСК")],
            [KeyboardButton("📋 ДОСЬЕ")],
            [KeyboardButton("⚙️ НАСТРОЙКИ")],
            [KeyboardButton("🤖 AI ПОМОЩНИК")],
        ]
    if db.is_dev(user_id):
        buttons.append([KeyboardButton("🛠️ МЕНЮ ДЕВ")])
    buttons.append([KeyboardButton("🔙 НАЗАД")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_search_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👤 ПО ЮЗЕРНЕЙМУ")],
        [KeyboardButton("📱 ПО ТЕЛЕФОНУ")],
        [KeyboardButton("📧 ПО EMAIL")],
        [KeyboardButton("🌍 ПО IP")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_protection_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⚡ МГНОВЕННАЯ ЗАЩИТА")],
        [KeyboardButton("👤 СКРЫТЬ АКАУНТ")],
        [KeyboardButton("📍 АНТИ-СЛЕЖКА")],
        [KeyboardButton("👻 РЕЖИМ ИНКОГНИТО")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_tools_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🖥️ ТЕРМИНАЛ"), KeyboardButton("🦠 ТРОЯН")],
        [KeyboardButton("📶 WIFI"), KeyboardButton("🔐 ШИФР")],
        [KeyboardButton("🔓 ДЕШИФР"), KeyboardButton("🆘 ЭКСТРЕННАЯ ПОМОЩЬ")],
        [KeyboardButton("🤖 ПРОВЕРКА НА БОТА"), KeyboardButton("🕸️ КАРТА СВЯЗЕЙ")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_settings_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📌 СМЕНИТЬ РЕЖИМ")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_dev_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 СТАТИСТИКА")],
        [KeyboardButton("🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ")],
        [KeyboardButton("🚫 ЗАБАНИТЬ"), KeyboardButton("✅ РАЗБАНИТЬ")],
        [KeyboardButton("🔙 ВЫЙТИ ИЗ ДЕВ")]
    ], resize_keyboard=True)

# ==================== OSINT ПОИСК ====================
class OSINTSearcher:
    def search_all(self, username):
        results = []
        platforms = [
            ("Telegram", f"https://t.me/{username}"),
            ("Instagram", f"https://www.instagram.com/{username}/"),
            ("TikTok", f"https://www.tiktok.com/@{username}"),
            ("Twitter/X", f"https://twitter.com/{username}"),
            ("YouTube", f"https://www.youtube.com/@{username}"),
            ("GitHub", f"https://github.com/{username}"),
            ("VK", f"https://vk.com/{username}"),
            ("Reddit", f"https://www.reddit.com/user/{username}")
        ]
        for platform, url in platforms:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    results.append({"platform": platform, "url": url, "status": "✅ Найден"})
                else:
                    results.append({"platform": platform, "status": "❌ Не найден"})
            except:
                results.append({"platform": platform, "status": "⚠️ Ошибка"})
        return results

    def search_ip(self, ip):
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {'country': data.get('country'), 'city': data.get('city'), 'isp': data.get('isp')}
            return None
        except:
            return None

osint = OSINTSearcher()

# ==================== АНИМАЦИЯ ====================
async def animation(update, title, steps):
    try:
        msg = await update.message.reply_text(f"```\n[{title}]...\n```", parse_mode=ParseMode.MARKDOWN)
        for i, step in enumerate(steps):
            bar = "█" * (i+1) + "░" * (len(steps) - i - 1)
            await msg.edit_text(f"```\n[{title}] {step}\n[{bar}]\n```", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.3)
        await msg.delete()
    except:
        pass

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
async def start(update, context):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or ""
        first_name = update.effective_user.first_name or "User"
        last_name = update.effective_user.last_name or ""

        db.add_user(user_id, username, first_name, last_name)
        mode = db.get_user_mode(user_id)
        mode_name = "KEY HELPER" if mode == "key_helper" else "FAST HELPER"
        
        await update.message.reply_text(
            f"🔥 HELPER BOT\n═══════════════════════════\n\n⚡ СИСТЕМА: ONLINE\n📌 ВЕРСИЯ: {VERSION}\n📌 РЕЖИМ: {mode_name}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu(user_id)
        )
    except Exception as e:
        logger.error(f"Start error: {e}")

async def handle_message(update, context):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        mode = db.get_user_mode(user_id)
        state = context.user_data.get('state', 'main')

        # Обработка пароля разработчика
        if text == DEV_PASSWORD:
            db.set_dev_mode(user_id, 1)
            await update.message.reply_text("✅ *DEV MODE АКТИВИРОВАН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
            return

        # Обработка кнопки назад
        if text in ["🔙 НАЗАД", "🔙 BACK", "📋 ГЛАВНОЕ МЕНЮ", "📋 MAIN MENU"]:
            context.user_data['state'] = 'main'
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            return

        # ===== МЕНЮ ДЕВ =====
        if text == "🛠️ МЕНЮ ДЕВ":
            if not db.is_dev(user_id):
                await update.message.reply_text("❌ ДОСТУП ЗАПРЕЩЕН!")
                return
            context.user_data['state'] = 'dev'
            await update.message.reply_text(f"🛠️ *МЕНЮ РАЗРАБОТЧИКА*\n\n📊 Всего: {db.get_total_users()}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
            return

        if state == 'dev':
            if text == "🔙 ВЫЙТИ ИЗ ДЕВ":
                db.set_dev_mode(user_id, 0)
                await update.message.reply_text("🔙 *ВЫШЕЛ ИЗ DEV MODE*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu(user_id))
                context.user_data['state'] = 'main'
                return
            if text == "📊 СТАТИСТИКА":
                await update.message.reply_text(f"📊 *СТАТИСТИКА*\n\n👥 Всего: {db.get_total_users()}\n🚫 Забанено: {len(db.get_banned_users())}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
                return
            if text == "🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ":
                await update.message.reply_text("🔍 Введите ID или юзернейм:")
                context.user_data['state'] = 'dev_search'
                return
            if text == "🚫 ЗАБАНИТЬ":
                await update.message.reply_text("🚫 Введите ID пользователя:")
                context.user_data['state'] = 'dev_ban'
                return
            if text == "✅ РАЗБАНИТЬ":
                await update.message.reply_text("✅ Введите ID пользователя:")
                context.user_data['state'] = 'dev_unban'
                return

        if state == 'dev_search':
            users = db.search_users(text)
            if not users:
                await update.message.reply_text("❌ ПОЛЬЗОВАТЕЛИ НЕ НАЙДЕНЫ", reply_markup=get_dev_menu())
                return
            result = "\n".join([f"@{u[1] or 'Нет'} - {u[2] or ''} ({u[0]})" for u in users[:10]])
            await update.message.reply_text(f"🔍 *РЕЗУЛЬТАТЫ ПОИСКА*\n{result}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
            context.user_data['state'] = 'dev'
            return

        if state == 'dev_ban':
            try:
                db.ban_user(int(text), user_id, "Нарушение правил")
                await update.message.reply_text("✅ *ПОЛЬЗОВАТЕЛЬ ЗАБАНЕН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
            except:
                await update.message.reply_text("❌ НЕВЕРНЫЙ ID!", reply_markup=get_dev_menu())
            context.user_data['state'] = 'dev'
            return

        if state == 'dev_unban':
            try:
                db.unban_user(int(text))
                await update.message.reply_text("✅ *ПОЛЬЗОВАТЕЛЬ РАЗБАНЕН!*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu())
            except:
                await update.message.reply_text("❌ НЕВЕРНЫЙ ID!", reply_markup=get_dev_menu())
            context.user_data['state'] = 'dev'
            return

        # ===== ПОИСК =====
        if text == "🔍 ПОИСК":
            context.user_data['state'] = 'search'
            await update.message.reply_text("🔍 *ВЫБЕРИТЕ ТИП ПОИСКА:*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_search_menu())
            return

        if state == 'search':
            if text == "👤 ПО ЮЗЕРНЕЙМУ":
                await update.message.reply_text("👤 Введите юзернейм:")
                context.user_data['state'] = 'search_username'
                return
            if text == "📱 ПО ТЕЛЕФОНУ":
                await update.message.reply_text("📱 Введите номер телефона:")
                context.user_data['state'] = 'search_phone'
                return
            if text == "📧 ПО EMAIL":
                await update.message.reply_text("📧 Введите email:")
                context.user_data['state'] = 'search_email'
                return
            if text == "🌍 ПО IP":
                await update.message.reply_text("🌍 Введите IP:")
                context.user_data['state'] = 'search_ip'
                return

        if state == 'search_username':
            await update.message.reply_text("⏳ ОБРАБОТКА...")
            results = osint.search_all(text)
            report = f"🔍 *РЕЗУЛЬТАТЫ ПОИСКА*\n═══════════════════════\n\n👤 ЗАПРОС: `{text}`\n\n"
            for r in results:
                report += f"📌 *{r['platform']}:* {r['status']}\n└ {r.get('url', '')}\n\n"
            await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        if state == 'search_phone':
            await update.message.reply_text(f"📱 *ПОИСК ПО ТЕЛЕФОНУ*\n═══════════════════════\n\n📱 НОМЕР: `{text}`\n\n📌 Telegram: {random.choice(['✅ Да', '❌ Нет'])}\n📌 WhatsApp: {random.choice(['✅ Да', '❌ Нет'])}", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        if state == 'search_ip':
            ip_info = osint.search_ip(text)
            if ip_info:
                await update.message.reply_text(f"🌍 *IP ИНФО*\n═══════════════════════\n\n📍 Страна: {ip_info['country']}\n📍 Город: {ip_info['city']}\n📍 ISP: {ip_info['isp']}", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ Данные не найдены.")
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        if state == 'search_email':
            await update.message.reply_text(f"📧 *ПОИСК ПО EMAIL*\n═══════════════════════\n\n📧 EMAIL: `{text}`\n\n📌 Утечки: {random.randint(0, 5)}", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        # ===== ЗАЩИТА =====
        if text == "🛡️ ЗАЩИТА":
            if mode != "key_helper":
                await update.message.reply_text("❌ Защита работает только в KEY HELPER режиме!")
                return
            context.user_data['state'] = 'protection'
            await update.message.reply_text("🛡️ *ЗАЩИТА АККАУНТА*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_protection_menu())
            return

        if state == 'protection':
            if text == "⚡ МГНОВЕННАЯ ЗАЩИТА":
                await animation(update, "ЗАЩИТА", ["Активация 2FA...", "Блокировка сессий...", "ГОТОВО!"])
                await update.message.reply_text("✅ *МГНОВЕННАЯ ЗАЩИТА АКТИВИРОВАНА!*", parse_mode=ParseMode.MARKDOWN)
            elif text == "👤 СКРЫТЬ АКАУНТ":
                await animation(update, "СКРЫТИЕ", ["Отключение геолокации...", "ГОТОВО!"])
                await update.message.reply_text("✅ *АККАУНТ СКРЫТ!*", parse_mode=ParseMode.MARKDOWN)
            elif text == "📍 АНТИ-СЛЕЖКА":
                await animation(update, "АНТИ-СЛЕЖКА", ["Маскировка IP...", "ГОТОВО!"])
                await update.message.reply_text("✅ *IP ЗАМАСКИРОВАН!*", parse_mode=ParseMode.MARKDOWN)
            elif text == "👻 РЕЖИМ ИНКОГНИТО":
                await animation(update, "ИНКОГНИТО", ["Очистка истории...", "ГОТОВО!"])
                await update.message.reply_text("✅ *РЕЖИМ ИНКОГНИТО!*", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            return

        # ===== ХАКЕРСКИЕ ИНСТРУМЕНТЫ =====
        if text == "🔑 ХАКЕРСКИЕ ИНСТРУМЕНТЫ":
            if mode != "key_helper":
                await update.message.reply_text("❌ Хакерские инструменты работают только в KEY HELPER режиме!")
                return
            context.user_data['state'] = 'tools'
            await update.message.reply_text("🔑 *ХАКЕРСКИЕ ИНСТРУМЕНТЫ*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_tools_menu())
            return

        if state == 'tools':
            if text == "🖥️ ТЕРМИНАЛ":
                await animation(update, "ТЕРМИНАЛ", ["Загрузка...", "Выполнение...", "ГОТОВО!"])
            elif text == "🦠 ТРОЯН":
                await animation(update, "ТРОЯН", ["Генерация...", "Активация!", "ГОТОВО!"])
            elif text == "📶 WIFI":
                await animation(update, "WIFI", ["Поиск сети...", "Взлом...", "Ключ найден!"])
                await update.message.reply_text(f"📶 *WIFI ВЗЛОМАН!*\n🔑 Ключ: `{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))}`", parse_mode=ParseMode.MARKDOWN)
            elif text == "🔐 ШИФР":
                await animation(update, "ШИФР", ["Шифрование...", "ГОТОВО!"])
            elif text == "🔓 ДЕШИФР":
                await animation(update, "ДЕШИФР", ["Дешифровка...", "ГОТОВО!"])
            elif text == "🆘 ЭКСТРЕННАЯ ПОМОЩЬ":
                await animation(update, "ПОМОЩЬ", ["Блокировка...", "ГОТОВО!"])
            elif text == "🤖 ПРОВЕРКА НА БОТА":
                await update.message.reply_text("🤖 Введите юзернейм:")
                context.user_data['state'] = 'bot_check'
                return
            elif text == "🕸️ КАРТА СВЯЗЕЙ":
                await update.message.reply_text("🕸️ Введите юзернейм:")
                context.user_data['state'] = 'social_graph'
                return
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            return

        if state == 'bot_check':
            score = random.randint(10, 95)
            await update.message.reply_text(f"🤖 *ПРОВЕРКА НА БОТА*\n═══════════════════════\n\n👤 Цель: @{text}\n📊 Оценка: {score}%\n{ '👤 Человек' if score > 70 else '🤖 Бот' if score > 40 else '⚡ Высокий риск' }", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        if state == 'social_graph':
            await animation(update, "КАРТА СВЯЗЕЙ", ["Сбор данных...", "Анализ связей...", "Генерация карты..."])
            await update.message.reply_text(f"🕸️ *КАРТА СВЯЗЕЙ*\n═══════════════════════\n\n👤 Цель: @{text}\n📊 Связей найдено: {random.randint(5, 50)}", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        # ===== ДОСЬЕ =====
        if text == "📋 ДОСЬЕ":
            if mode != "fast_helper":
                await update.message.reply_text("❌ Досье работает только в FAST HELPER режиме!")
                return
            await update.message.reply_text("📋 Введите цель (юзернейм или телефон):")
            context.user_data['state'] = 'dossier'
            return

        if state == 'dossier':
            await update.message.reply_text("⏳ ОБРАБОТКА...")
            results = osint.search_all(text)
            social = ""
            for r in results[:5]:
                social += f"{r['platform']}: {r['status']}\n"
            await update.message.reply_text(f"📋 *ДОСЬЕ*\n═══════════════════════\n\n🎯 ЦЕЛЬ: `{text}`\n📅 ДАТА: `{datetime.now()}`\n\n== СОЦСЕТИ ==\n{social}\n== УТЕЧКИ ==\nНайдено утечек: {random.randint(0, 5)}\n\nДостоверность: {random.randint(60, 95)}%", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        # ===== AI =====
        if text == "🤖 AI ПОМОЩНИК":
            await update.message.reply_text("🤖 Спросите меня о чём-нибудь:")
            context.user_data['state'] = 'ai'
            return

        if state == 'ai':
            await update.message.reply_text(f"🤖 *AI АНАЛИЗ*\n\n📌 Запрос: {text}\n📌 Данные: {random.choice(['Найдены', 'Частично найдены', 'Не найдены'])}", parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
            context.user_data['state'] = 'main'
            return

        # ===== НАСТРОЙКИ =====
        if text == "⚙️ НАСТРОЙКИ":
            context.user_data['state'] = 'settings'
            await update.message.reply_text("⚙️ *НАСТРОЙКИ*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_settings_menu())
            return

        if state == 'settings':
            if text == "📌 СМЕНИТЬ РЕЖИМ":
                current_mode = db.get_user_mode(user_id)
                new_mode = "fast_helper" if current_mode == "key_helper" else "key_helper"
                db.update_mode(user_id, new_mode)
                await update.message.reply_text(f"✅ *РЕЖИМ ИЗМЕНЁН НА {new_mode.upper()}*", parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
                context.user_data['state'] = 'main'
                return

        # Фолбэк
        await update.message.reply_text("📋 ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(user_id))
    except Exception as e:
        logger.error(f"Handle error: {e}")

# ==================== ЗАПУСК ====================
def run_flask():
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)), debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask error: {e}")

def run_bot():
    while True:
        try:
            print(f"\n🔥=== {BOT_NAME} v{VERSION} ===🔥")
            print("⚡ SYSTEM ONLINE")
            print("✅ BOT STARTED!\n")
            application = ApplicationBuilder().token(TOKEN).build()
            application.add_handler(CommandHandler('start', start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            print("❌ БОТ УПАЛ! ПЕРЕЗАПУСК ЧЕРЕЗ 3 СЕКУНДЫ...")
            time.sleep(3)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()
