# -*- coding: utf-8 -*-
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

# Импорт Flask для запуска веб-сервера (чтобы Render не убивал процесс)
from flask import Flask, send_file

# Импорт Telegram
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# ==================== КОНФИГ ====================
VERSION = "12.0"
BOT_NAME = "🔥 HELPER BOT 🔥"
# ВСТАВЬ СВОЙ ТОКЕН (или он подтянется с Render)
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "8736136579:AAGp7QPivJCHFG5ooNcBVwZP3GDXNLQYaJs"

# ТВОЯ ССЫЛКА (ВСТАВЛЕНА!)
WEB_APP_URL = "https://botcay-1.onrender.com"

MAIN_ADMIN_USERNAME = "fuck_society13"
DEV_PASSWORD = "K7X9M2P5R8Q4W6N3T1Y7L8C9V2B5D0E3"

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
DB_NAME = os.path.join(BASE_DIR, "helper_bot.db")

# Flask сервер (нужен для Render)
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
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'en',
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
        logger.info("✅ Database initialized")

    def add_user(self, user_id, username, first_name, last_name, language='en', theme='hacker', bot_mode='key_helper', bot_version='12.0', is_admin='no'):
        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, language, theme, bot_mode, bot_version, is_admin, registered_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, language, theme, bot_mode, bot_version, is_admin, now, now))
        conn.commit()
        conn.close()

    def get_username(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def is_admin(self, user_id):
        username = self.get_username(user_id)
        if username == MAIN_ADMIN_USERNAME:
            return True
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] != 'no'

    def get_user_language(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 'en'

    def update_language(self, user_id, language):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
        conn.commit()
        conn.close()

    def update_language_all(self, language):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET language = ?', (language,))
        conn.commit()
        conn.close()

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

    def get_user_version(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT bot_version FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else '12.0'

    def update_version(self, user_id, version):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET bot_version = ? WHERE user_id = ?', (version, user_id))
        conn.commit()
        conn.close()

    def get_user_theme(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT theme FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 'hacker'

    def update_theme(self, user_id, theme):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET theme = ? WHERE user_id = ?', (theme, user_id))
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

    def get_online_users(self, timeout=300):
        conn = self.get_connection()
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(seconds=timeout)
        cursor.execute('SELECT user_id, username, first_name, last_name, last_active FROM users WHERE last_active > ? ORDER BY last_active DESC', (cutoff,))
        results = cursor.fetchall()
        conn.close()
        return results

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

    def ban_user(self, user_id, admin_id, reason="Rule violation"):
        username = self.get_username(user_id)
        if username == MAIN_ADMIN_USERNAME:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_banned = 1, ban_reason = ?, banned_at = ? WHERE user_id = ?',
                      (reason, datetime.now(), user_id))
        self.add_admin_log(admin_id, f"banned user {user_id}", user_id)
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

    def add_admin_log(self, admin_id, action, target_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO admin_logs (admin_id, action, target_id, timestamp) VALUES (?, ?, ?, ?)',
                      (admin_id, action, target_id, datetime.now()))
        conn.commit()
        conn.close()

    def get_admin_logs(self, limit=20):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT admin_id, action, target_id, timestamp FROM admin_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_new_users_today(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        today = datetime.now().date()
        cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(registered_at) = ?', (today,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

db = Database()

# ==================== OSINT ====================
class OSINTSearcher:
    def search_telegram(self, username):
        try:
            url = f"https://t.me/{username}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return {"platform": "Telegram", "url": url, "status": "✅ Found"}
            return {"platform": "Telegram", "status": "❌ Not found"}
        except:
            return {"platform": "Telegram", "status": "⚠️ Error"}

    def search_instagram(self, username):
        try:
            url = f"https://www.instagram.com/{username}/"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return {"platform": "Instagram", "url": url, "status": "✅ Found"}
            return {"platform": "Instagram", "status": "❌ Not found"}
        except:
            return {"platform": "Instagram", "status": "⚠️ Error"}

    def search_tiktok(self, username):
        try:
            url = f"https://www.tiktok.com/@{username}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return {"platform": "TikTok", "url": url, "status": "✅ Found"}
            return {"platform": "TikTok", "status": "❌ Not found"}
        except:
            return {"platform": "TikTok", "status": "⚠️ Error"}

    def search_twitter(self, username):
        try:
            url = f"https://twitter.com/{username}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return {"platform": "Twitter/X", "url": url, "status": "✅ Found"}
            return {"platform": "Twitter/X", "status": "❌ Not found"}
        except:
            return {"platform": "Twitter/X", "status": "⚠️ Error"}

    def search_youtube(self, username):
        try:
            url = f"https://www.youtube.com/@{username}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return {"platform": "YouTube", "url": url, "status": "✅ Found"}
            return {"platform": "YouTube", "status": "❌ Not found"}
        except:
            return {"platform": "YouTube", "status": "⚠️ Error"}

    def search_github(self, username):
        try:
            url = f"https://github.com/{username}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return {"platform": "GitHub", "url": url, "status": "✅ Found"}
            return {"platform": "GitHub", "status": "❌ Not found"}
        except:
            return {"platform": "GitHub", "status": "⚠️ Error"}

    def search_vk(self, username):
        try:
            url = f"https://vk.com/{username}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return {"platform": "VK", "url": url, "status": "✅ Found"}
            return {"platform": "VK", "status": "❌ Not found"}
        except:
            return {"platform": "VK", "status": "⚠️ Error"}

    def search_reddit(self, username):
        try:
            url = f"https://www.reddit.com/user/{username}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                return {"platform": "Reddit", "url": url, "status": "✅ Found"}
            return {"platform": "Reddit", "status": "❌ Not found"}
        except:
            return {"platform": "Reddit", "status": "⚠️ Error"}

    def search_all(self, username):
        results = []
        results.append(self.search_telegram(username))
        results.append(self.search_instagram(username))
        results.append(self.search_tiktok(username))
        results.append(self.search_twitter(username))
        results.append(self.search_youtube(username))
        results.append(self.search_github(username))
        results.append(self.search_vk(username))
        results.append(self.search_reddit(username))
        return results

    def search_ip(self, ip):
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country', 'Unknown'),
                        'city': data.get('city', 'Unknown'),
                        'isp': data.get('isp', 'Unknown')
                    }
            return None
        except:
            return None

osint_searcher = OSINTSearcher()

# ==================== ФУНКЦИИ ====================
def get_lang(user_id):
    lang = user_languages.get(user_id)
    if not lang:
        lang = db.get_user_language(user_id)
        user_languages[user_id] = lang
    return lang

def get_text(user_id, key, **kwargs):
    lang = get_lang(user_id)
    text = LANGUAGES.get(lang, LANGUAGES["en"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text

def get_user_mode(user_id):
    mode = user_modes.get(user_id)
    if not mode:
        mode = db.get_user_mode(user_id)
        user_modes[user_id] = mode
    return mode

def get_user_version(user_id):
    version = user_versions.get(user_id)
    if not version:
        version = db.get_user_version(user_id)
        user_versions[user_id] = version
    return version

user_languages = {}
user_modes = {}
user_versions = {}
user_themes = {}
rate_limit = defaultdict(list)
user_states = {}

def get_daily_stats():
    conn = db.get_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(registered_at) = ?', (today,))
    new_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(last_active) = ?', (today,))
    active_users = cursor.fetchone()[0]
    conn.close()
    return {'new_users': new_users, 'active_users': active_users}

# ==================== МЕНЮ ====================
def get_main_menu(user_id):
    mode = get_user_mode(user_id)
    version = get_user_version(user_id)
    is_dev = db.is_dev(user_id)
    
    if mode == "key_helper":
        if version == "3.4":
            buttons = [
                [KeyboardButton(get_text(user_id, "search"))],
                [KeyboardButton(get_text(user_id, "hacker_tools"))],
                [KeyboardButton(get_text(user_id, "settings"))]
            ]
        elif version == "9.7":
            buttons = [
                [KeyboardButton(get_text(user_id, "protection"))],
                [KeyboardButton(get_text(user_id, "search"))],
                [KeyboardButton(get_text(user_id, "hacker_tools"))],
                [KeyboardButton(get_text(user_id, "settings"))],
                [KeyboardButton(get_text(user_id, "stats_daily"))]
            ]
        else:
            buttons = [
                [KeyboardButton(get_text(user_id, "protection"))],
                [KeyboardButton(get_text(user_id, "search"))],
                [KeyboardButton(get_text(user_id, "hacker_tools"))],
                [KeyboardButton(get_text(user_id, "settings"))],
                [KeyboardButton(get_text(user_id, "ai_help"))],
                [KeyboardButton(get_text(user_id, "stats_daily"))]
            ]
    else:  # fast_helper
        buttons = [
            [KeyboardButton(get_text(user_id, "search"))],
            [KeyboardButton(get_text(user_id, "dossier"))],
            [KeyboardButton(get_text(user_id, "settings"))],
            [KeyboardButton(get_text(user_id, "ai_help"))]
        ]
    
    if is_dev:
        buttons.append([KeyboardButton(get_text(user_id, "dev_menu"))])
    buttons.append([KeyboardButton(get_text(user_id, "back"))])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def get_key_helper_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton(get_text(user_id, "emergency")), KeyboardButton(get_text(user_id, "ddos"))],
        [KeyboardButton(get_text(user_id, "bot_check")), KeyboardButton(get_text(user_id, "social_graph"))],
        [KeyboardButton(get_text(user_id, "terminal")), KeyboardButton(get_text(user_id, "trojan"))],
        [KeyboardButton(get_text(user_id, "wifi")), KeyboardButton(get_text(user_id, "encrypt"))],
        [KeyboardButton(get_text(user_id, "decrypt"))],
        [KeyboardButton(get_text(user_id, "back"))]
    ], resize_keyboard=True)

def get_search_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton(get_text(user_id, "search_username")), KeyboardButton(get_text(user_id, "search_phone"))],
        [KeyboardButton(get_text(user_id, "search_email")), KeyboardButton(get_text(user_id, "search_ip"))],
        [KeyboardButton(get_text(user_id, "search_domain")), KeyboardButton(get_text(user_id, "search_photo"))],
        [KeyboardButton(get_text(user_id, "back"))]
    ], resize_keyboard=True)

def get_protection_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton(get_text(user_id, "instant_protection"))],
        [KeyboardButton(get_text(user_id, "hide_account"))],
        [KeyboardButton(get_text(user_id, "long_protection"))],
        [KeyboardButton(get_text(user_id, "anti_tracking"))],
        [KeyboardButton(get_text(user_id, "incognito"))],
        [KeyboardButton(get_text(user_id, "back"))]
    ], resize_keyboard=True)

def get_settings_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton(get_text(user_id, "language")), KeyboardButton(get_text(user_id, "theme"))],
        [KeyboardButton(get_text(user_id, "mode_switch")), KeyboardButton(get_text(user_id, "version"))],
        [KeyboardButton(get_text(user_id, "back"))]
    ], resize_keyboard=True)

def get_mode_switch_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔑 KEY HELPER"), KeyboardButton("⚡ FAST HELPER")],
        [KeyboardButton(get_text(user_id, "back"))]
    ], resize_keyboard=True)

def get_dev_menu(user_id):
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 STATISTICS"), KeyboardButton("👥 ONLINE")],
        [KeyboardButton("📝 LOGS"), KeyboardButton("🔍 SEARCH USER")],
        [KeyboardButton("🚫 BAN USER"), KeyboardButton("✅ UNBAN USER")],
        [KeyboardButton("🌐 SET LANGUAGE ALL"), KeyboardButton("🛠️ FUNCTION CONTROL")],
        [KeyboardButton("📨 BROADCAST"), KeyboardButton("💾 BACKUP")],
        [KeyboardButton("🔙 EXIT DEV")]
    ], resize_keyboard=True)

def get_func_control_menu():
    status_emoji = {}
    for key in func_settings:
        status_emoji[key] = "✅" if func_settings[key] else "❌"
    return ReplyKeyboardMarkup([
        [KeyboardButton(f"🔍 SEARCH {status_emoji['search']}"), KeyboardButton(f"🛡️ PROTECTION {status_emoji['protection']}")],
        [KeyboardButton(f"🔑 HACKER {status_emoji['hacker_tools']}"), KeyboardButton(f"⚡ DDOS {status_emoji['ddos']}")],
        [KeyboardButton(f"🖥️ TERMINAL {status_emoji['terminal']}"), KeyboardButton(f"🦠 TROJAN {status_emoji['trojan']}")],
        [KeyboardButton(f"📶 WIFI {status_emoji['wifi']}"), KeyboardButton(f"🔐 CRYPTO {status_emoji['crypto']}")],
        [KeyboardButton(f"🤖 BOT CHECK {status_emoji['bot_check']}"), KeyboardButton(f"🕸️ SOCIAL {status_emoji['social_graph']}")],
        [KeyboardButton(f"🆘 EMERGENCY {status_emoji['emergency']}"), KeyboardButton(f"🤖 AI {status_emoji['ai']}")],
        [KeyboardButton(f"📊 DAILY STATS {status_emoji['stats_daily']}"), KeyboardButton(f"📋 DOSSIER {status_emoji['dossier']}")],
        [KeyboardButton(f"📨 BROADCAST {status_emoji['broadcast']}"), KeyboardButton(f"💾 BACKUP {status_emoji['backup']}")],
        [KeyboardButton("🔙 BACK")]
    ], resize_keyboard=True)

def get_language_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🔙 CANCEL", callback_data="cancel")]
    ])

def get_theme_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💀 Hacker", callback_data="theme_hacker")],
        [InlineKeyboardButton("🔥 Cyberpunk", callback_data="theme_cyberpunk")],
        [InlineKeyboardButton("🌙 Dark", callback_data="theme_dark")],
        [InlineKeyboardButton("☀️ Light", callback_data="theme_light")],
        [InlineKeyboardButton("🔙 CANCEL", callback_data="cancel")]
    ])

def get_version_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("3.4 - Basic", callback_data="ver_3.4")],
        [InlineKeyboardButton("9.7 - Developer", callback_data="ver_9.7")],
        [InlineKeyboardButton("12.0 - Full", callback_data="ver_12.0")],
        [InlineKeyboardButton("🔙 CANCEL", callback_data="cancel")]
    ])

def get_ddos_method_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ SYN FLOOD", callback_data="ddos_syn")],
        [InlineKeyboardButton("🌊 UDP FLOOD", callback_data="ddos_udp")],
        [InlineKeyboardButton("💥 ICMP FLOOD", callback_data="ddos_icmp")],
        [InlineKeyboardButton("🔙 CANCEL", callback_data="cancel")]
    ])

def get_language_all_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_all_en")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_all_ru")],
        [InlineKeyboardButton("🔙 CANCEL", callback_data="cancel")]
    ])

# ==================== СЛОВАРИ ====================
LANGUAGES = {
    "en": { ... весь словарь "en" из твоего старого кода ... },
    "ru": { ... весь словарь "ru" из твоего старого кода ... }
}

func_settings = {
    "search": True,
    "protection": True,
    "hacker_tools": True,
    "ddos": True,
    "terminal": True,
    "trojan": True,
    "wifi": True,
    "crypto": True,
    "bot_check": True,
    "social_graph": True,
    "emergency": True,
    "ai": True,
    "stats_daily": True,
    "dossier": True,
    "broadcast": True,
    "backup": True
}

# ==================== БЫСТРАЯ DDOS ====================
async def ddos_attack(update, target, method):
    packets = random.randint(500000, 5000000)
    await update.message.reply_text(
        f"⚡ *DDOS COMPLETED!*\n"
        "═══════════════════════\n"
        f"🎯 TARGET: `{target}`\n"
        f"📦 PACKETS: `{packets}`\n"
        f"⚡ METHOD: `{method}`\n"
        f"✅ STATUS: `SUCCESS`",
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== БЫСТРЫЕ АНИМАЦИИ ====================
async def show_custom_animation(update, title, steps_text, emoji="⚡"):
    try:
        msg = await update.message.reply_text(
            f"```\n[{emoji}] {title}...\n```",
            parse_mode=ParseMode.MARKDOWN
        )
        for i, step in enumerate(steps_text):
            progress = int((i + 1) / len(steps_text) * 100)
            bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
            await msg.edit_text(
                f"```\n[{emoji}] {step}\n[⚡] PROGRESS: {bar} {progress}%\n```",
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(0.1)
        await msg.edit_text(f"```\n[✅] {title} - COMPLETED!\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)
        await msg.delete()
        return True
    except:
        return False

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
async def start(update, context):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or ""
        first_name = update.effective_user.first_name or "User"
        last_name = update.effective_user.last_name or ""
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        conn.close()
        
        if not exists:
            await update.message.reply_text(
                get_text(user_id, "select_language"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_language_menu()
            )
            context.user_data['new_user'] = True
            return
        
        db.add_user(user_id, username, first_name, last_name)
        mode = get_user_mode(user_id)
        version = get_user_version(user_id)
        mode_name = "KEY HELPER" if mode == "key_helper" else "FAST HELPER"
        
        await update.message.reply_text(
            get_text(user_id, "welcome", version=version, mode=mode_name),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu(user_id)
        )
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text(get_text(user_id, "error"))

async def button_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "cancel":
            await query.delete_message()
            await query.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return
        
        if query.data.startswith("lang_"):
            lang = query.data.replace("lang_", "")
            
            if context.user_data.get('new_user'):
                context.user_data['new_user'] = False
                user_id = query.from_user.id
                username = query.from_user.username or ""
                first_name = query.from_user.first_name or "User"
                last_name = query.from_user.last_name or ""
                
                db.add_user(user_id, username, first_name, last_name, language=lang)
                user_languages[user_id] = lang
                
                await query.delete_message()
                await query.message.reply_text(
                    get_text(user_id, "choose_mode"),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_mode_switch_menu(user_id)
                )
                context.user_data['first_mode_select'] = True
                return
            
            user_languages[user_id] = lang
            db.update_language(user_id, lang)
            
            await query.delete_message()
            await query.message.reply_text(
                get_text(user_id, "main_menu"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu(user_id)
            )
            return
        
        if query.data.startswith("lang_all_"):
            lang = query.data.replace("lang_all_", "")
            db.update_language_all(lang)
            await query.edit_message_text(
                get_text(user_id, "dev_lang_done", lang=lang.upper()),
                parse_mode=ParseMode.MARKDOWN
            )
            await query.message.reply_text("🛠️ DEV MENU", reply_markup=get_dev_menu(user_id))
            return
        
        if query.data.startswith("theme_"):
            theme = query.data.replace("theme_", "")
            db.update_theme(user_id, theme)
            await query.edit_message_text(
                f"✅ *THEME CHANGED TO {theme.upper()}*",
                parse_mode=ParseMode.MARKDOWN
            )
            await query.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return
        
        if query.data.startswith("ver_"):
            version = query.data.replace("ver_", "")
            user_versions[user_id] = version
            db.update_version(user_id, version)
            
            await query.delete_message()
            await query.message.reply_text(
                get_text(user_id, "main_menu"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu(user_id)
            )
            return
        
        if query.data.startswith("ddos_"):
            target = context.user_data.get('ddos_target', 'unknown')
            method_map = {
                "ddos_syn": "SYN FLOOD",
                "ddos_udp": "UDP FLOOD",
                "ddos_icmp": "ICMP FLOOD"
            }
            method = method_map.get(query.data, "SYN FLOOD")
            
            await query.delete_message()
            await ddos_attack(query.message, target, method)
            
            await query.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return
        
    except Exception as e:
        logger.error(f"Callback error: {e}")

async def handle_message(update, context):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        mode = get_user_mode(user_id)
        version = get_user_version(user_id)
        
        now = time.time()
        if user_id in rate_limit:
            rate_limit[user_id] = [t for t in rate_limit[user_id] if now - t < 60]
            if len(rate_limit[user_id]) >= 40:
                await update.message.reply_text("⏳ WAIT...")
                return
        rate_limit[user_id].append(now)

        state = context.user_data.get('state', 'main')

        # ===== НОВЫЙ ПОЛЬЗОВАТЕЛЬ - ВЫБОР РЕЖИМА =====
        if context.user_data.get('first_mode_select'):
            if text in ["🔑 KEY HELPER", "⚡ FAST HELPER"]:
                mode_choice = "key_helper" if text == "🔑 KEY HELPER" else "fast_helper"
                db.update_mode(user_id, mode_choice)
                user_modes[user_id] = mode_choice
                context.user_data['first_mode_select'] = False
                
                mode_name = "KEY HELPER" if mode_choice == "key_helper" else "FAST HELPER"
                await update.message.reply_text(
                    get_text(user_id, "mode_selected", mode=mode_name),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_menu(user_id)
                )
                return
            else:
                await update.message.reply_text(
                    get_text(user_id, "choose_mode"),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_mode_switch_menu(user_id)
                )
                return

        # ===== DEV PASSWORD =====
        if text == DEV_PASSWORD:
            db.set_dev_mode(user_id, 1)
            await update.message.reply_text(
                "✅ *DEV MODE ACTIVATED!*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu(user_id)
            )
            return

        if text == "🔙 EXIT DEV":
            db.set_dev_mode(user_id, 0)
            await update.message.reply_text(
                "🔙 *EXITED DEV MODE*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu(user_id)
            )
            return

        if text in ["🔙 BACK", "🔙 НАЗАД", "📋 MAIN MENU", "📋 ГЛАВНОЕ МЕНЮ"]:
            context.user_data['state'] = 'main'
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        # ===== SEARCH =====
        if text in ["🔍 SEARCH", "🔍 ПОИСК"]:
            if not func_settings.get('search', True):
                await update.message.reply_text("❌ SEARCH DISABLED!")
                return
            context.user_data['state'] = 'search'
            await update.message.reply_text(
                "🔍 *SELECT SEARCH TYPE:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_search_menu(user_id)
            )
            return

        if state == 'search':
            if text in ["🔙 BACK", "🔙 НАЗАД"]:
                context.user_data['state'] = 'main'
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            search_map = {
                get_text(user_id, "search_username"): "username",
                get_text(user_id, "search_phone"): "phone",
                get_text(user_id, "search_email"): "email",
                get_text(user_id, "search_ip"): "ip",
                get_text(user_id, "search_domain"): "domain",
                get_text(user_id, "search_photo"): "photo"
            }

            if text in search_map:
                search_type = search_map[text]
                context.user_data['search_type'] = search_type
                prompts = {
                    "username": get_text(user_id, "enter_username"),
                    "phone": get_text(user_id, "enter_phone"),
                    "email": get_text(user_id, "enter_email"),
                    "ip": get_text(user_id, "enter_ip"),
                    "domain": get_text(user_id, "enter_domain"),
                    "photo": get_text(user_id, "send_photo")
                }
                await update.message.reply_text(prompts[search_type], parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'search_input'
                return

        if state == 'search_input':
            search_type = context.user_data.get('search_type')
            query = text.strip()
            
            if search_type == "username":
                await update.message.reply_text(get_text(user_id, "processing"))
                results = osint_searcher.search_all(query)
                report = f"🔍 *OSINT SEARCH RESULTS*\n═══════════════════════\n\n👤 QUERY: `{query}`\n\n"
                for result in results:
                    platform = result.get("platform", "Unknown")
                    status = result.get("status", "⚠️ Error")
                    url = result.get("url", "")
                    if url:
                        report += f"📌 *{platform}:* {status}\n└ {url}\n\n"
                    else:
                        report += f"📌 *{platform}:* {status}\n\n"
                await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
                
            elif search_type == "phone":
                await update.message.reply_text(
                    f"📱 *PHONE SEARCH*\n═══════════════════════\n\n📱 NUMBER: `{query}`\n\n📌 Telegram: {random.choice(['✅ Yes', '❌ No'])}\n📌 WhatsApp: {random.choice(['✅ Yes', '❌ No'])}\n📌 Viber: {random.choice(['✅ Yes', '❌ No'])}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif search_type == "email":
                breaches = random.randint(0, 8)
                await update.message.reply_text(
                    f"📧 *EMAIL SEARCH*\n═══════════════════════\n\n📧 EMAIL: `{query}`\n\n📌 Gravatar: {random.choice(['✅ Found', '❌ Not found'])}\n📌 Leaks found: {breaches}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif search_type == "ip":
                ip_info = osint_searcher.search_ip(query)
                if ip_info:
                    await update.message.reply_text(
                        f"🌍 *IP SEARCH*\n═══════════════════════\n\n🌍 IP: `{query}`\n\n📍 Country: {ip_info['country']}\n📍 City: {ip_info['city']}\n📍 ISP: {ip_info['isp']}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(get_text(user_id, "no_data"))
                
            elif search_type == "domain":
                await update.message.reply_text(
                    f"🏠 *DOMAIN SEARCH*\n═══════════════════════\n\n🏠 DOMAIN: `{query}`\n\n📌 Owner: {random.choice(['Private', 'Company LLC'])}\n📌 Registrar: {random.choice(['GoDaddy', 'Namecheap'])}\n📌 Created: {datetime.now().strftime('%Y-%m-%d')}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif search_type == "photo":
                await update.message.reply_text(
                    f"🖼️ *PHOTO SEARCH (EXPERIMENTAL)*\n═══════════════════════\n\n📌 Google Images: {random.randint(1, 10)} matches\n📌 Yandex: {random.randint(0, 5)} matches",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            context.user_data['state'] = 'main'
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        # ===== PROTECTION (only KEY HELPER) =====
        if text in ["🛡️ PROTECTION", "🛡️ ЗАЩИТА"]:
            if mode != "key_helper":
                await update.message.reply_text("❌ PROTECTION only in KEY HELPER mode!")
                return
            if not func_settings.get('protection', True):
                await update.message.reply_text("❌ PROTECTION DISABLED!")
                return
            context.user_data['state'] = 'protection'
            await update.message.reply_text(
                "🛡️ *ACCOUNT PROTECTION*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_protection_menu(user_id)
            )
            return

        if state == 'protection':
            if text in ["🔙 BACK", "🔙 НАЗАД"]:
                context.user_data['state'] = 'main'
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return
            
            if text in [get_text(user_id, "instant_protection"), "⚡ МГНОВЕННАЯ ЗАЩИТА"]:
                steps = ["STARTING PROTECTION... 🛡️", "ACTIVATING 2FA... 🔐", "PROTECTION ACTIVE! ✅"]
                await show_custom_animation(update, "INSTANT PROTECTION", steps)
                await update.message.reply_text("🛡️ *INSTANT PROTECTION ACTIVATED!*\n🔐 2FA: ENABLED\n🛡️ SESSIONS: BLOCKED", parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
            
            elif text in [get_text(user_id, "hide_account"), "👤 СКРЫТЬ АКАУНТ"]:
                steps = ["HIDING ACCOUNT... 👤", "DISABLING GEOLOCATION... 📍", "DONE! ✅"]
                await show_custom_animation(update, "HIDE ACCOUNT", steps)
                await update.message.reply_text("👤 *ACCOUNT HIDDEN!*\n👤 ACCOUNT: INVISIBLE\n🚫 OTHERS: CAN'T SEE YOU", parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
            
            elif text in [get_text(user_id, "long_protection"), "🛡️ ДОЛГАЯ ЗАЩИТА"]:
                steps = ["SETTING UP... ⚙️", "SETTING PERIODICITY... 📅", "DONE! ✅"]
                await show_custom_animation(update, "LONG PROTECTION", steps)
                await update.message.reply_text("🛡️ *LONG PROTECTION ACTIVATED!*\n📅 PASSWORD CHANGE: EVERY 30 DAYS", parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
            
            elif text in [get_text(user_id, "anti_tracking"), "📍 АНТИ-СЛЕЖКА"]:
                steps = ["DISABLING TRACKING... 📍", "MASKING IP... 🔒", "DONE! ✅"]
                await show_custom_animation(update, "ANTI-TRACKING", steps)
                await update.message.reply_text("📍 *ANTI-TRACKING ACTIVATED!*\n📍 GEOLOCATION: DISABLED\n🔒 IP: ANONYMOUS", parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
            
            elif text in [get_text(user_id, "incognito"), "👻 РЕЖИМ ИНКОГНИТО"]:
                steps = ["ACTIVATING INCOGNITO... 👻", "CLEARING HISTORY... 🧹", "DONE! ✅"]
                await show_custom_animation(update, "INCOGNITO MODE", steps)
                await update.message.reply_text("👻 *INCOGNITO MODE ACTIVATED!*\n👻 ACTIVITY: HIDDEN\n🔍 HISTORY: CLEARED", parse_mode=ParseMode.MARKDOWN)
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
            return

        # ===== HACKER TOOLS (only KEY HELPER) =====
        if text in ["🔑 HACKER TOOLS", "🔑 ХАКЕРСКИЕ ИНСТРУМЕНТЫ"]:
            if mode != "key_helper":
                await update.message.reply_text("❌ HACKER TOOLS only in KEY HELPER mode!")
                return
            if not func_settings.get('hacker_tools', True):
                await update.message.reply_text("❌ HACKER TOOLS DISABLED!")
                return
            context.user_data['state'] = 'hacker_tools'
            await update.message.reply_text(
                "🔥 *HACKER TOOLS*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_key_helper_menu(user_id)
            )
            return

        if state == 'hacker_tools':
            if text in ["🔙 BACK", "🔙 НАЗАД"]:
                context.user_data['state'] = 'main'
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            if text in [get_text(user_id, "ddos"), "⚡ DDOS АТАКА"]:
                if not func_settings.get('ddos', True):
                    await update.message.reply_text("❌ DDOS DISABLED!")
                    return
                await update.message.reply_text("⚡ *ENTER TARGET:*", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'ddos_target'
                return

            if text in [get_text(user_id, "terminal"), "🖥️ ТЕРМИНАЛ"]:
                if not func_settings.get('terminal', True):
                    await update.message.reply_text("❌ TERMINAL DISABLED!")
                    return
                steps = ["INITIALIZING... 💻", "LOADING SHELL... ⌨️", "EXECUTING... 🚀", "COMPLETED! ✅"]
                await show_custom_animation(update, "TERMINAL", steps)
                await update.message.reply_text(
                    f"🖥️ *TERMINAL*\n═══════════════════════\n\n$> {text}\n[+] EXECUTED ✅",
                    parse_mode=ParseMode.MARKDOWN
                )
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            if text in [get_text(user_id, "trojan"), "🦠 ТРОЯН"]:
                if not func_settings.get('trojan', True):
                    await update.message.reply_text("❌ TROJAN DISABLED!")
                    return
                steps = ["GENERATING... 🦠", "PACKING... 📦", "ACTIVATING! ✅"]
                await show_custom_animation(update, "TROJAN", steps)
                await update.message.reply_text(
                    f"🦠 *TROJAN DEPLOYED!*\n═══════════════════════\n\n🎯 TARGET: `{text}`\n🦠 STATUS: `INFECTED ✅`",
                    parse_mode=ParseMode.MARKDOWN
                )
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            if text in [get_text(user_id, "wifi"), "📶 WIFI"]:
                if not func_settings.get('wifi', True):
                    await update.message.reply_text("❌ WIFI DISABLED!")
                    return
                steps = ["SEARCHING... 📶", "SELECTING... 🎯", "CRACKING... (78%) 🔑", "KEY FOUND! ✅"]
                await show_custom_animation(update, "WIFI HACK", steps)
                key = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
                await update.message.reply_text(
                    f"📶 *WIFI HACKED!*\n═══════════════════════\n\n📶 NETWORK: `{text}`\n🔑 KEY: `{key}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            if text in [get_text(user_id, "encrypt"), "🔐 ШИФР"]:
                if not func_settings.get('crypto', True):
                    await update.message.reply_text("❌ CRYPTO DISABLED!")
                    return
                await update.message.reply_text("🔐 *ENTER TEXT TO ENCRYPT:*", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'encrypt_input'
                return

            if text in [get_text(user_id, "decrypt"), "🔓 ДЕШИФР"]:
                if not func_settings.get('crypto', True):
                    await update.message.reply_text("❌ CRYPTO DISABLED!")
                    return
                await update.message.reply_text("🔓 *ENTER TEXT TO DECRYPT:*", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'decrypt_input'
                return

            if text in [get_text(user_id, "emergency"), "🆘 ЭКСТРЕННАЯ ПОМОЩЬ"]:
                if not func_settings.get('emergency', True):
                    await update.message.reply_text("❌ EMERGENCY DISABLED!")
                    return
                steps = ["STARTING... 🆘", "BLOCKING... 🔒", "PROTECTED! 🛡️"]
                await show_custom_animation(update, "EMERGENCY HELP", steps)
                await update.message.reply_text(
                    "🆘 *EMERGENCY HELP*\n═══════════════════════\n\n1️⃣ CHANGE PASSWORD\n2️⃣ END SESSIONS\n3️⃣ ENABLE 2FA",
                    parse_mode=ParseMode.MARKDOWN
                )
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            if text in [get_text(user_id, "bot_check"), "🤖 ПРОВЕРКА НА БОТА"]:
                if not func_settings.get('bot_check', True):
                    await update.message.reply_text("❌ BOT CHECK DISABLED!")
                    return
                await update.message.reply_text("🤖 *ENTER USERNAME:*", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'bot_check'
                return

            if text in [get_text(user_id, "social_graph"), "🕸️ КАРТА СВЯЗЕЙ"]:
                if not func_settings.get('social_graph', True):
                    await update.message.reply_text("❌ SOCIAL GRAPH DISABLED!")
                    return
                await update.message.reply_text("🕸️ *ENTER USERNAME:*", parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'social_graph'
                return

        if state == 'ddos_target':
            target = text.strip().replace("@", "")
            if len(target) < 1:
                await update.message.reply_text("❌ INVALID TARGET")
                return
            context.user_data['ddos_target'] = target
            await update.message.reply_text(
                f"⚡ *SELECT METHOD FOR {target}:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_ddos_method_menu()
            )
            return

        if state == 'bot_check':
            if not func_settings.get('bot_check', True):
                await update.message.reply_text("❌ BOT CHECK DISABLED!")
                return
            steps = ["COLLECTING... 👤", "ANALYZING... 🤖", "VERDICT! 📄"]
            await show_custom_animation(update, "BOT CHECK", steps)
            score = random.randint(10, 95)
            result = "LOW (Human)" if score > 70 else "MEDIUM" if score > 40 else "HIGH (Bot)"
            emoji = "👤" if score > 70 else "🤖" if score > 40 else "⚡"
            await update.message.reply_text(
                f"🤖 *BOT CHECK*\n═══════════════════════\n\n👤 TARGET: @{text}\n📊 SCORE: {score}%\n{emoji} RESULT: {result}",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        if state == 'social_graph':
            if not func_settings.get('social_graph', True):
                await update.message.reply_text("❌ SOCIAL GRAPH DISABLED!")
                return
            steps = ["COLLECTING... 👥", "ANALYZING... 🔗", "GENERATING... 🗺️"]
            await show_custom_animation(update, "SOCIAL GRAPH", steps)
            connections = ["user1", "user2", "user3", "user4", "user5"]
            report = f"🕸️ *SOCIAL GRAPH*\n═══════════════════════\n\n👤 TARGET: @{text}\n📊 CONNECTIONS: {random.randint(5, 50)}\n\n📌 CONNECTIONS:\n"
            for conn in connections:
                report += f"├ 🔗 {conn}\n"
            await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        if state == 'encrypt_input':
            if not func_settings.get('crypto', True):
                await update.message.reply_text("❌ CRYPTO DISABLED!")
                return
            steps = ["LOADING... 📝", "ENCRYPTING... 🔐", "COMPLETED! ⚡"]
            await show_custom_animation(update, "ENCRYPTION", steps)
            result = ''.join(chr(ord(c) + 1) if c.isprintable() and c != ' ' else c for c in text[:50])
            await update.message.reply_text(
                f"🔐 *ENCRYPTION*\n═══════════════════════\n\n📝 INPUT: `{text[:30]}...`\n🔑 OUTPUT: `{result}`",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        if state == 'decrypt_input':
            if not func_settings.get('crypto', True):
                await update.message.reply_text("❌ CRYPTO DISABLED!")
                return
            steps = ["LOADING... 📝", "DECRYPTING... 🔓", "COMPLETED! ⚡"]
            await show_custom_animation(update, "DECRYPTION", steps)
            result = ''.join(chr(ord(c) - 1) if c.isprintable() and c != ' ' else c for c in text[:50])
            await update.message.reply_text(
                f"🔓 *DECRYPTION*\n═══════════════════════\n\n📝 INPUT: `{text[:30]}...`\n🔑 OUTPUT: `{result}`",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        # ===== DOSSIER (only FAST HELPER) =====
        if text in ["📋 DOSSIER", "📋 ДОСЬЕ"]:
            if mode != "fast_helper":
                await update.message.reply_text("❌ DOSSIER only in FAST HELPER mode!")
                return
            if not func_settings.get('dossier', True):
                await update.message.reply_text("❌ DOSSIER DISABLED!")
                return
            await update.message.reply_text(get_text(user_id, "dossier_target"), parse_mode=ParseMode.MARKDOWN)
            context.user_data['state'] = 'dossier_input'
            return

        if state == 'dossier_input':
            target = text.strip()
            await update.message.reply_text(get_text(user_id, "processing"))
            
            results = osint_searcher.search_all(target)
            social = ""
            for r in results[:5]:
                platform = r.get("platform", "Unknown")
                status = r.get("status", "❌")
                social += f"{platform}: {status}\n"
            
            await update.message.reply_text(
                get_text(user_id, "dossier_report",
                    target=target,
                    date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    social=social,
                    leaks=random.randint(0, 5),
                    confidence=random.randint(60, 95)),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['state'] = 'main'
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        # ===== AI HELP =====
        if text in ["🤖 AI ASSISTANT", "🤖 AI ПОМОЩНИК"]:
            if not func_settings.get('ai', True):
                await update.message.reply_text("❌ AI DISABLED!")
                return
            await update.message.reply_text(
                "🤖 *AI ASSISTANT*\n═══════════════════════\n\n📌 Ask me anything about OSINT:\n- People search\n- Digital footprint\n- Information gathering\n\n📌 *Just type your question!*",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['state'] = 'ai_input'
            return

        if state == 'ai_input':
            response = random.choice([
                f"📊 Analysis for '{text}':\n\n• Public records available\n• Social media: {random.choice(['Active', 'Limited', 'None'])}\n• Digital footprint: {random.choice(['Low', 'Medium', 'High'])}",
                f"🔍 OSINT intelligence:\n\n• Data found in {random.randint(1, 5)} sources\n• Verification: {random.choice(['Verified', 'Pending'])}\n• Confidence: {random.randint(50, 95)}%",
                f"🤖 Analysis:\n\n• Target: {text}\n• Status: {random.choice(['Verified', 'Inconclusive'])}\n• Next steps: Check official records"
            ])
            await update.message.reply_text(
                f"🤖 *AI ANALYSIS*\n═══════════════════════\n\n{response}",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.message.reply_text(
                get_text(user_id, "main_menu"),
                reply_markup=get_main_menu(user_id)
            )
            return

        # ===== DAILY STATS =====
        if text in ["📊 DAILY STATS", "📊 СТАТИСТИКА ЗА ДЕНЬ"]:
            if not func_settings.get('stats_daily', True):
                await update.message.reply_text("❌ DAILY STATS DISABLED!")
                return
            stats = get_daily_stats()
            total = db.get_total_users()
            online = len(db.get_online_users())
            banned = len(db.get_banned_users())
            await update.message.reply_text(
                f"📊 *DAILY STATS*\n═══════════════════════\n\n📅 {datetime.now().strftime('%Y-%m-%d')}\n\n👥 NEW: {stats['new_users']}\n🟢 ACTIVE: {stats['active_users']}\n👥 TOTAL: {total}\n🟢 ONLINE: {online}\n🚫 BANNED: {banned}",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # ===== SETTINGS =====
        if text in ["⚙️ SETTINGS", "⚙️ НАСТРОЙКИ"]:
            context.user_data['state'] = 'settings'
            await update.message.reply_text(
                "⚙️ *SETTINGS*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_settings_menu(user_id)
            )
            return

        if state == 'settings':
            if text in ["🔙 BACK", "🔙 НАЗАД"]:
                context.user_data['state'] = 'main'
                await update.message.reply_text(
                    get_text(user_id, "main_menu"),
                    reply_markup=get_main_menu(user_id)
                )
                return

            if text in [get_text(user_id, "language"), "🌐 ЯЗЫК"]:
                await update.message.reply_text(
                    get_text(user_id, "select_language"),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_language_menu()
                )
                return

            if text in [get_text(user_id, "theme"), "🎨 ТЕМА"]:
                await update.message.reply_text(
                    "🎨 *SELECT THEME:*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_theme_menu()
                )
                return

            if text in [get_text(user_id, "mode_switch"), "📌 СМЕНИТЬ РЕЖИМ"]:
                await update.message.reply_text(
                    get_text(user_id, "choose_mode"),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_mode_switch_menu(user_id)
                )
                context.user_data['state'] = 'mode_switch'
                return

            if text in [get_text(user_id, "version"), "📌 ВЕРСИЯ"]:
                if mode != "key_helper":
                    await update.message.reply_text("❌ VERSION only in KEY HELPER mode!")
                    return
                await update.message.reply_text(
                    "📌 *SELECT VERSION:*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_version_menu()
                )
                return

        # ===== MODE SWITCH =====
        if state == 'mode_switch':
            if text in ["🔑 KEY HELPER", "⚡ FAST HELPER"]:
                mode_choice = "key_helper" if text == "🔑 KEY HELPER" else "fast_helper"
                db.update_mode(user_id, mode_choice)
                user_modes[user_id] = mode_choice
                mode_name = "KEY HELPER" if mode_choice == "key_helper" else "FAST HELPER"
                await update.message.reply_text(
                    f"✅ *MODE CHANGED TO {mode_name}*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_menu(user_id)
                )
                context.user_data['state'] = 'main'
                return
            else:
                await update.message.reply_text(
                    get_text(user_id, "choose_mode"),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_mode_switch_menu(user_id)
                )
                return

        # ===== DEV MENU =====
        if text in ["🛠️ DEV MENU", "🛠️ МЕНЮ ДЕВ"]:
            if not db.is_dev(user_id):
                await update.message.reply_text("❌ ACCESS DENIED!")
                return
            context.user_data['state'] = 'dev'
            total = db.get_total_users()
            online = len(db.get_online_users())
            mode_name = "KEY HELPER" if mode == "key_helper" else "FAST HELPER"
            await update.message.reply_text(
                get_text(user_id, "dev_welcome", total=total, online=online, mode=mode_name),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_dev_menu(user_id)
            )
            return

        if state == 'dev':
            if text == "📊 STATISTICS":
                total = db.get_total_users()
                online = len(db.get_online_users())
                new_today = db.get_new_users_today()
                banned = len(db.get_banned_users())
                await update.message.reply_text(
                    get_text(user_id, "dev_stats", total=total, online=online, new_today=new_today, banned=banned),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_dev_menu(user_id)
                )
                return

            if text == "👥 ONLINE":
                online = db.get_online_users()
                if not online:
                    await update.message.reply_text(get_text(user_id, "no_online"), reply_markup=get_dev_menu(user_id))
                    return
                user_list = ""
                for user in online[:20]:
                    user_list += f"└ @{user[1] or 'NO'} - {user[2] or ''}\n"
                await update.message.reply_text(
                    get_text(user_id, "dev_online", count=len(online), users=user_list),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_dev_menu(user_id)
                )
                return

            if text == "📝 LOGS":
                logs = db.get_admin_logs(20)
                if not logs:
                    await update.message.reply_text(get_text(user_id, "no_logs"), reply_markup=get_dev_menu(user_id))
                    return
                log_text = ""
                for admin_id, action, target_id, timestamp in logs[:10]:
                    log_text += f"└ Admin `{admin_id}`: {action}\n"
                await update.message.reply_text(
                    get_text(user_id, "dev_logs", logs=log_text),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_dev_menu(user_id)
                )
                return

            if text == "🔍 SEARCH USER":
                await update.message.reply_text(get_text(user_id, "dev_search"), parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'dev_search'
                return

            if text == "🚫 BAN USER":
                await update.message.reply_text(get_text(user_id, "dev_ban"), parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'dev_ban'
                return

            if text == "✅ UNBAN USER":
                await update.message.reply_text(get_text(user_id, "dev_unban"), parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'dev_unban'
                return

            if text == "🌐 SET LANGUAGE ALL":
                await update.message.reply_text(
                    get_text(user_id, "dev_lang_all"),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_language_all_menu()
                )
                return

            if text == "🛠️ FUNCTION CONTROL":
                func_list = ""
                for key, value in func_settings.items():
                    status = "✅" if value else "❌"
                    func_list += f"{key}: {status}\n"
                await update.message.reply_text(
                    get_text(user_id, "dev_functions", functions=func_list),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_func_control_menu()
                )
                context.user_data['state'] = 'func_control'
                return

            if text == "📨 BROADCAST":
                if mode != "fast_helper":
                    await update.message.reply_text("❌ BROADCAST only in FAST HELPER mode!")
                    return
                if not func_settings.get('broadcast', True):
                    await update.message.reply_text("❌ BROADCAST DISABLED!")
                    return
                await update.message.reply_text(get_text(user_id, "dev_broadcast"), parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'dev_broadcast'
                return

            if text == "💾 BACKUP":
                if mode != "fast_helper":
                    await update.message.reply_text("❌ BACKUP only in FAST HELPER mode!")
                    return
                if not func_settings.get('backup', True):
                    await update.message.reply_text("❌ BACKUP DISABLED!")
                    return
                # Просто имитация бэкапа (файлы на Render не хранятся)
                await update.message.reply_text("✅ *BACKUP CREATED!*\n📁 Memory: Virtual", parse_mode=ParseMode.MARKDOWN, reply_markup=get_dev_menu(user_id))
                return

            if text == "🔙 EXIT DEV":
                db.set_dev_mode(user_id, 0)
                await update.message.reply_text(
                    "🔙 *EXITED DEV MODE*",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_main_menu(user_id)
                )
                context.user_data['state'] = 'main'
                return

        # ===== DEV SEARCH =====
        if state == 'dev_search':
            query = text.strip()
            users = db.search_users(query)
            if not users:
                await update.message.reply_text(get_text(user_id, "no_users"), reply_markup=get_dev_menu(user_id))
                return
            results = ""
            for user in users[:10]:
                results += f"└ @{user[1] or 'NO'} - {user[2] or ''} ({user[0]})\n"
            await update.message.reply_text(
                get_text(user_id, "search_results", results=results),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_dev_menu(user_id)
            )
            context.user_data['state'] = 'dev'
            return

        # ===== DEV BAN =====
        if state == 'dev_ban':
            try:
                target_id = int(text.strip())
                if db.is_admin(target_id):
                    await update.message.reply_text("❌ CAN'T BAN ADMIN!", reply_markup=get_dev_menu(user_id))
                    context.user_data['state'] = 'dev'
                    return
                context.user_data['ban_target'] = target_id
                await update.message.reply_text(get_text(user_id, "ban_reason"), parse_mode=ParseMode.MARKDOWN)
                context.user_data['state'] = 'dev_ban_reason'
            except:
                await update.message.reply_text(get_text(user_id, "invalid_id"), reply_markup=get_dev_menu(user_id))
                context.user_data['state'] = 'dev'
            return

        if state == 'dev_ban_reason':
            target_id = context.user_data.get('ban_target')
            reason = text if text != "Skip" else "Rule violation"
            if db.ban_user(target_id, user_id, reason):
                await update.message.reply_text(
                    get_text(user_id, "user_banned", id=target_id, reason=reason),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_dev_menu(user_id)
                )
            else:
                await update.message.reply_text("❌ CAN'T BAN MAIN ADMIN!", reply_markup=get_dev_menu(user_id))
            context.user_data['state'] = 'dev'

        # ===== DEV UNBAN =====
        if state == 'dev_unban':
            try:
                target_id = int(text.strip())
                db.unban_user(target_id)
                await update.message.reply_text(
                    get_text(user_id, "user_unbanned", id=target_id),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_dev_menu(user_id)
                )
            except:
                await update.message.reply_text(get_text(user_id, "invalid_id"), reply_markup=get_dev_menu(user_id))
            context.user_data['state'] = 'dev'

        # ===== DEV BROADCAST =====
        if state == 'dev_broadcast':
            if mode != "fast_helper":
                await update.message.reply_text("❌ BROADCAST only in FAST HELPER mode!")
                context.user_data['state'] = 'dev'
                return
            await update.message.reply_text("⏳ SENDING BROADCAST...")
            users = db.get_all_users()
            sent = 0
            for user in users:
                try:
                    await context.bot.send_message(
                        user[0],
                        f"📨 *GLOBAL NOTIFICATION*\n═══════════════════════\n\n{text}\n\n🔥 *HELPER BOT*",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    sent += 1
                    await asyncio.sleep(0.05)
                except:
                    pass
            await update.message.reply_text(
                f"✅ *BROADCAST COMPLETED!*\n📨 SENT: `{sent}` users",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_dev_menu(user_id)
            )
            context.user_data['state'] = 'dev'

        # ===== FUNCTION CONTROL =====
        if state == 'func_control':
            if text == "🔙 BACK":
                context.user_data['state'] = 'dev'
                await update.message.reply_text("🛠️ DEV MENU", reply_markup=get_dev_menu(user_id))
                return

            func_map = {
                "SEARCH": "search",
                "PROTECTION": "protection",
                "HACKER": "hacker_tools",
                "DDOS": "ddos",
                "TERMINAL": "terminal",
                "TROJAN": "trojan",
                "WIFI": "wifi",
                "CRYPTO": "crypto",
                "BOT CHECK": "bot_check",
                "SOCIAL": "social_graph",
                "EMERGENCY": "emergency",
                "AI": "ai",
                "DAILY STATS": "stats_daily",
                "DOSSIER": "dossier",
                "BROADCAST": "broadcast",
                "BACKUP": "backup"
            }

            for key, func_name in func_map.items():
                if key in text:
                    func_settings[func_name] = not func_settings[func_name]
                    status = "ENABLED ✅" if func_settings[func_name] else "DISABLED ❌"
                    await update.message.reply_text(
                        f"✅ *CHANGED*\n📌 {key}: `{status}`\n⚠️ *FOR ALL USERS*",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_func_control_menu()
                    )
                    return

        await update.message.reply_text(
            get_text(user_id, "main_menu"),
            reply_markup=get_main_menu(user_id)
        )
    except Exception as e:
        logger.error(f"Handle error: {e}")
        try:
            await update.message.reply_text(get_text(user_id, "error"))
        except:
            pass

async def error_handler(update, context):
    try:
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ ERROR! Try again.")
    except:
        pass

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
            print("✅ FAST HELPER + WEB APP LINKED!")
            print("\n✅ BOT STARTED!\n")
            
            application = ApplicationBuilder().token(TOKEN).build()
            
            application.add_handler(CommandHandler('start', start))
            application.add_handler(CommandHandler('help', start))
            application.add_handler(CallbackQueryHandler(button_callback))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.add_error_handler(error_handler)
            
            application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            print(f"\n❌ БОТ УПАЛ! ПЕРЕЗАПУСК ЧЕРЕЗ 3 СЕКУНДЫ...\n")
            time.sleep(3)
            continue

if __name__ == '__main__':
    # Запускаем Flask в фоне (чтобы Render видел порт)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Запускаем "неубиваемого" бота
    run_bot()
