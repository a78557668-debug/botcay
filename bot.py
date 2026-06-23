import logging
import platform
import psutil
import sys
import sqlite3
import time
import asyncio
import random
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

VERSION = "v9.0.0"
BOT_NAME = "🔥 CYBER OSINT MASTER 🔥"
TOKEN = "8639382714:AAGc7AKr34f6tOQBNM1_m52fmIZI8FWVw3E"

DEV_PASSWORD = "987654321"
ADMIN_PASSWORD = "1981784489"
ADMIN_USERNAME = "fuck_society13"
MASTER_ADMIN_PASSWORD = "XK7M9P2R5Q8W4N6T3Y1U7L8C9V2B5D0E3"

DB_NAME = "bot_data.db"
LOG_FILE = "bot_errors.log"
MAX_REQUESTS_PER_MINUTE = 40
ONLINE_TIMEOUT = 300

hack_counter = 0

dev_settings = {
    "ddos_enabled": True,
    "terminal_enabled": True,
    "scanner_enabled": True,
    "cracker_enabled": True,
    "trojan_enabled": True,
    "wifi_enabled": True,
    "crypto_enabled": True,
    "search_enabled": True,
    "protection_enabled": True
}

pending_admin_keys = {}

request = HTTPXRequest(
    connection_pool_size=10,
    read_timeout=60,
    write_timeout=60,
    connect_timeout=60,
)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
                language TEXT DEFAULT 'ru',
                theme TEXT DEFAULT 'dark',
                bot_version TEXT DEFAULT '9.0',
                is_admin TEXT DEFAULT 'no',
                registered_at TIMESTAMP,
                last_active TIMESTAMP
            )
        ''')

        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'is_admin' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin TEXT DEFAULT 'no'")

        if 'bot_version' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN bot_version TEXT DEFAULT '9.0'")

        if 'theme' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'dark'")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                search_type TEXT,
                search_query TEXT,
                result TEXT,
                created_at TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                search_type TEXT,
                search_query TEXT,
                created_at TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_info (
                user_id INTEGER PRIMARY KEY,
                device_name TEXT,
                device_model TEXT,
                os TEXT,
                os_version TEXT,
                processor TEXT,
                ram_total TEXT,
                python_version TEXT,
                hostname TEXT,
                last_updated TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS social_graph (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_username TEXT,
                connections TEXT,
                created_at TIMESTAMP
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
        logger.info("База данных инициализирована")

    def add_user(self, user_id, username, first_name, last_name, language='ru', theme='dark', bot_version='9.0', is_admin='no'):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, language, theme, bot_version, is_admin, registered_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, language, theme, bot_version, is_admin, datetime.now(), datetime.now()))
        conn.commit()
        conn.close()

    def update_language(self, user_id, language):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
        conn.commit()
        conn.close()

    def update_theme(self, user_id, theme):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET theme = ? WHERE user_id = ?', (theme, user_id))
        conn.commit()
        conn.close()

    def update_version(self, user_id, version):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET bot_version = ? WHERE user_id = ?', (version, user_id))
        conn.commit()
        conn.close()

    def update_admin_status(self, user_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = ? WHERE user_id = ?', (status, user_id))
        conn.commit()
        conn.close()

    def update_last_active(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', (datetime.now(), user_id))
        conn.commit()
        conn.close()

    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name, is_admin FROM users ORDER BY registered_at DESC')
        results = cursor.fetchall()
        conn.close()
        return results

    def get_admins(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username, first_name, last_name, is_admin FROM users WHERE is_admin != "no"')
        results = cursor.fetchall()
        conn.close()
        return results

    def is_admin(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] != 'no'

    def is_main_admin(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] == 'main_admin'

    def update_device_info(self, user_id, device_info):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO device_info
            (user_id, device_name, device_model, os, os_version, processor, ram_total, python_version, hostname, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            device_info.get('device_name', 'Unknown'),
            device_info.get('device_model', 'Unknown'),
            device_info.get('os', 'Unknown'),
            device_info.get('os_version', 'Unknown'),
            device_info.get('processor', 'Unknown'),
            device_info.get('ram_total', 'Unknown'),
            device_info.get('python_version', 'Unknown'),
            device_info.get('hostname', 'Unknown'),
            datetime.now()
        ))
        conn.commit()
        conn.close()

    def get_all_devices(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.last_name,
                   d.device_name, d.device_model, d.os, d.os_version, d.processor, d.ram_total, d.python_version, d.hostname, d.last_updated
            FROM users u
            LEFT JOIN device_info d ON u.user_id = d.user_id
            ORDER BY d.last_updated DESC
        ''')
        results = cursor.fetchall()
        conn.close()
        return results

    def get_online_users(self, timeout=ONLINE_TIMEOUT):
        conn = self.get_connection()
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(seconds=timeout)
        try:
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, last_active, theme, bot_version, is_admin
                FROM users
                WHERE last_active > ?
                ORDER BY last_active DESC
            ''', (cutoff,))
            results = cursor.fetchall()
        except:
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, last_active
                FROM users
                WHERE last_active > ?
                ORDER BY last_active DESC
            ''', (cutoff,))
            results = [(r[0], r[1], r[2], r[3], r[4], 'dark', '9.0', 'no') for r in cursor.fetchall()]
        conn.close()
        return results

    def add_search_history(self, user_id, search_type, search_query, result):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO search_history (user_id, search_type, search_query, result, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, search_type, search_query, result, datetime.now()))
        conn.commit()
        conn.close()

    def get_search_history(self, user_id, limit=10):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT search_type, search_query, created_at FROM search_history
            WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
        ''', (user_id, limit))
        results = cursor.fetchall()
        conn.close()
        return results

    def add_favorite(self, user_id, search_type, search_query):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO favorites (user_id, search_type, search_query, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, search_type, search_query, datetime.now()))
        conn.commit()
        conn.close()

    def get_favorites(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT search_type, search_query, created_at FROM favorites
            WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def add_activity(self, user_id, action):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_activity (user_id, action, timestamp)
            VALUES (?, ?, ?)
        ''', (user_id, action, datetime.now()))
        conn.commit()
        conn.close()
        self.update_last_active(user_id)

    def get_user_activity(self, user_id, limit=20):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT action, timestamp FROM user_activity
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
        ''', (user_id, limit))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_total_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    def get_total_searches(self, user_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute('SELECT COUNT(*) FROM search_history WHERE user_id = ?', (user_id,))
        else:
            cursor.execute('SELECT COUNT(*) FROM search_history')
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    def add_admin_log(self, admin_id, action, target_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_logs (admin_id, action, target_id, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (admin_id, action, target_id, datetime.now()))
        conn.commit()
        conn.close()

    def get_admin_logs(self, limit=20):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_id, action, target_id, timestamp FROM admin_logs
            ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_user_version(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT bot_version FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
        except:
            result = None
        conn.close()
        if result:
            return result[0]
        return '9.0'

db = Database()
user_states = {}
user_devices = {}
user_languages = {}
user_themes = {}
user_versions = {}
rate_limit = defaultdict(list)
dev_mode_users = set()
admin_call_users = {}
ddos_active = {}

def generate_admin_key():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(15))

def get_lang(user_id):
    return user_languages.get(user_id, 'ru')

def get_user_version(user_id):
    return user_versions.get(user_id, '9.0')

def check_rate_limit(user_id):
    now = time.time()
    if user_id in rate_limit:
        rate_limit[user_id] = [t for t in rate_limit[user_id] if now - t < 60]
        if len(rate_limit[user_id]) >= MAX_REQUESTS_PER_MINUTE:
            return False
    rate_limit[user_id].append(now)
    return True

def get_device_info():
    try:
        system = platform.system()
        system_version = platform.version()
        machine = platform.machine()
        processor = platform.processor()
        hostname = platform.node()
        python_version = sys.version
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        ram_total = f"{memory.total / (1024**3):.2f} GB"
        ram_used = f"{memory.used / (1024**3):.2f} GB"
        ram_percent = f"{memory.percent}%"
        disk = psutil.disk_usage('/')
        disk_total = f"{disk.total / (1024**3):.2f} GB"
        disk_used = f"{disk.used / (1024**3):.2f} GB"
        disk_free = f"{disk.free / (1024**3):.2f} GB"
        disk_percent = f"{disk.percent}%"
        return {
            'device_name': hostname,
            'device_model': machine,
            'os': system,
            'os_version': system_version,
            'machine': machine,
            'processor': processor or 'Not detected',
            'cpu_count': cpu_count,
            'cpu_percent': cpu_percent,
            'ram_total': ram_total,
            'ram_used': ram_used,
            'ram_percent': ram_percent,
            'disk_total': disk_total,
            'disk_used': disk_used,
            'disk_free': disk_free,
            'disk_percent': disk_percent,
            'python_version': python_version,
            'hostname': hostname
        }
    except:
        return {
            'device_name': 'Error',
            'device_model': 'Error',
            'os': platform.system(),
            'os_version': 'Error',
            'machine': 'Error',
            'processor': 'Error',
            'cpu_count': 'Error',
            'cpu_percent': 'Error',
            'ram_total': 'Error',
            'ram_used': 'Error',
            'ram_percent': 'Error',
            'disk_total': 'Error',
            'disk_used': 'Error',
            'disk_free': 'Error',
            'disk_percent': 'Error',
            'python_version': 'Error',
            'hostname': 'Error'
        }

async def show_loading(update, text, delay=0.1):
    try:
        msg = await update.message.reply_text(f"⏳ {text}")
        await asyncio.sleep(delay)
        await msg.delete()
    except:
        pass
async def ddos_animation(update, target, packet_size):
    global hack_counter
    try:
        msg = await update.message.reply_text("```\n[🔥] INITIALIZING DDOS ATTACK...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        frames = [
            f"💀 [🔍] SCANNING TARGET: {target}...",
            "⚡ [💻] ANALYZING VULNERABILITIES...",
            "🔥 [💀] DEPLOYING BOTNET... 25%",
            "💥 [📦] PREPARING PACKETS... 50%",
            "☠️ [🚀] SENDING PACKETS... 75%",
            "💀 [⚡] ATTACK IN PROGRESS... 100%"
        ]

        for frame in frames:
            await asyncio.sleep(0.15)
            await msg.edit_text(f"```\n{frame}\n```", parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(0.2)

        packets_sent = random.randint(1000000, 9999999)
        hack_counter += 1

        result = (
            "🔥 *DDOS ATTACK COMPLETE!*\n"
            "═══════════════════════════════════════\n"
            f"💀 TARGET: `@{target}`\n"
            f"📦 PACKETS SENT: `{packets_sent}`\n"
            f"📦 PACKET SIZE: `{packet_size}`\n"
            f"⚡ STATUS: `SUCCESS ✅`\n"
            f"🕐 TIME: `{datetime.now().strftime('%H:%M:%S')}`\n"
            f"💀 TOTAL ATTACKS: `{hack_counter}`\n"
            "═══════════════════════════════════════\n"
            "☠️ *SYSTEM COMPROMISED*"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass

async def hacker_terminal(update, command):
    try:
        msg = await update.message.reply_text("```\n[🖥️] HACKER TERMINAL ACTIVATED\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        lines = [
            f"$> {command}",
            "[+] EXECUTING...",
            "[+] ACCESS GRANTED ✅",
            "[+] SYSTEM: SECURE",
            f"[+] USER: @{update.effective_user.username or 'anonymous'}",
            "[+] STATUS: ONLINE",
            "$> READY FOR NEXT COMMAND"
        ]

        for line in lines:
            await asyncio.sleep(0.12)
            await msg.edit_text(f"```\n{line}\n```", parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(0.5)
        await msg.delete()
    except:
        pass

async def port_scanner(update, target):
    try:
        msg = await update.message.reply_text("```\n[🔍] INITIALIZING PORT SCAN...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5432, 5900, 8080]
        open_ports = []

        for i, port in enumerate(ports):
            if random.random() > 0.6:
                open_ports.append(port)
            progress = int((i + 1) / len(ports) * 100)
            await msg.edit_text(f"```\n[🔍] SCANNING: {target}\n[📡] PORT: {port}\n[⚡] PROGRESS: {progress}%\n```", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.06)

        await asyncio.sleep(0.2)

        result = (
            f"🔍 *PORT SCAN COMPLETE!*\n"
            "═══════════════════════\n"
            f"💀 TARGET: `{target}`\n"
            f"📡 PORTS SCANNED: `{len(ports)}`\n"
            f"🔓 OPEN PORTS: `{len(open_ports)}`\n"
            f"📋 LIST: `{open_ports if open_ports else 'None'}`\n"
            "═══════════════════════\n"
            "💀 *VULNERABILITIES FOUND*"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass

async def password_cracker(update, target):
    try:
        msg = await update.message.reply_text("```\n[🔓] INITIALIZING PASSWORD CRACKER...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        passwords = ["123456", "password", "admin", "qwerty", "abc123", "letmein", "monkey", "dragon", "master", "sunshine"]

        for i, pwd in enumerate(passwords):
            progress = int((i + 1) / len(passwords) * 100)
            await msg.edit_text(f"```\n[🔓] CRACKING: {target}\n[🔑] TRYING: {pwd}\n[⚡] PROGRESS: {progress}%\n```", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.06)
            if random.random() > 0.8:
                found_pwd = pwd
                break
        else:
            found_pwd = random.choice(["h4ck3r", "root@123", "security!", "cyber2024", "osint@master"])

        await asyncio.sleep(0.2)

        result = (
            f"🔓 *PASSWORD CRACKED!*\n"
            "═══════════════════════\n"
            f"💀 TARGET: `{target}`\n"
            f"🔑 PASSWORD: `{found_pwd}`\n"
            f"⚡ STATUS: `SUCCESS ✅`\n"
            "═══════════════════════\n"
            "💀 *ACCESS GRANTED*"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass

async def trojan_virus(update, target):
    try:
        msg = await update.message.reply_text("```\n[🦠] INITIALIZING TROJAN DEPLOYMENT...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        steps = [
            "[🔍] SCANNING SYSTEM...",
            "[🦠] UPLOADING TROJAN...",
            "[💀] BYPASSING FIREWALL...",
            "[🔥] ESTABLISHING BACKDOOR...",
            "[⚡] INFECTION COMPLETE!"
        ]

        for step in steps:
            await asyncio.sleep(0.12)
            await msg.edit_text(f"```\n{step}\n```", parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(0.2)

        result = (
            f"🦠 *TROJAN DEPLOYED!*\n"
            "═══════════════════════\n"
            f"💀 TARGET: `{target}`\n"
            f"🦠 STATUS: `INFECTED ✅`\n"
            f"🔓 BACKDOOR: `ESTABLISHED`\n"
            "═══════════════════════\n"
            "💀 *SYSTEM COMPROMISED*"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass

async def wifi_hack(update, target):
    try:
        msg = await update.message.reply_text("```\n[📶] INITIALIZING WIFI HACK...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        steps = [
            "[📶] SCANNING NETWORKS...",
            "[🔍] TARGET FOUND: " + target,
            "[💀] BRUTEFORCING WPA2...",
            "[⚡] HANDSHAKE CAPTURED!",
            "[🔥] DECRYPTING PACKETS...",
            "[✅] CONNECTION ESTABLISHED!"
        ]

        for step in steps:
            await asyncio.sleep(0.12)
            await msg.edit_text(f"```\n{step}\n```", parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(0.2)

        result = (
            f"📶 *WIFI HACKED!*\n"
            "═══════════════════════\n"
            f"📶 NETWORK: `{target}`\n"
            f"🔑 KEY: `{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))}`\n"
            f"⚡ STATUS: `CONNECTED ✅`\n"
            "═══════════════════════\n"
            "💀 *NETWORK COMPROMISED*"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass

async def encrypt_decrypt(update, text, mode):
    try:
        msg = await update.message.reply_text(f"```\n[🔐] INITIALIZING {mode}...\n```", parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.2)

        steps = [
            f"[🔐] {mode}: ACTIVATED",
            "[⚡] PROCESSING DATA...",
            "[💀] ENCRYPTION PROTOCOL: AES-256",
            "[🔥] GENERATING KEYS...",
            "[✅] " + ("ENCRYPTION" if mode == "ENCRYPT" else "DECRYPTION") + " COMPLETE!"
        ]

        for step in steps:
            await asyncio.sleep(0.12)
            await msg.edit_text(f"```\n{step}\n```", parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(0.2)

        result_text = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=32)) if mode == "ENCRYPT" else text[:50] + "..."

        result = (
            f"🔐 *{mode} COMPLETE!*\n"
            "═══════════════════════\n"
            f"📝 INPUT: `{text[:30]}{'...' if len(text) > 30 else ''}`\n"
            f"🔑 OUTPUT: `{result_text}`\n"
            f"⚡ STATUS: `SUCCESS ✅`\n"
            "═══════════════════════\n"
            "💀 *DATA PROCESSED*"
        )

        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        await msg.delete()
    except:
        pass

async def show_hack_counter(update):
    await update.message.reply_text(
        f"💀 *HACKER COUNTER*\n"
        "═══════════════════════\n"
        f"💀 TOTAL ATTACKS: `{hack_counter}`\n"
        f"🔥 STATUS: `ACTIVE`\n"
        f"⚡ LEVEL: `{min(10, hack_counter // 10 + 1)}`\n"
        "═══════════════════════\n"
        "🔥 *KEEP HACKING!*",
        parse_mode=ParseMode.MARKDOWN
    )

def smart_search_detect(text):
    text = text.strip()
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text):
        return 'email'
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
        return 'ip'
    phone_clean = re.sub(r'[^0-9]', '', text)
    if len(phone_clean) >= 10 and len(phone_clean) <= 15:
        return 'phone'
    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$', text):
        return 'domain'
    return 'username'

def generate_vcard(query, search_type, version='9.0'):
    if version in ['1.0', '6.0']:
        vcard = "ВИЗИТКА\n=================================\n\n"
        if search_type == "username":
            vcard += f"ЮЗЕРНЕЙМ: {query}\n\n"
            vcard += "СОЦСЕТИ:\n"
            vcard += f"- VK: vk.com/{query}\n"
            vcard += f"- IG: instagram.com/{query}\n"
            vcard += f"- TW: twitter.com/{query}"
        elif search_type == "phone":
            vcard += f"ТЕЛЕФОН: +{query}\n\n"
            vcard += "МЕССЕНДЖЕРЫ:\n"
            vcard += f"- Telegram: @username\n"
            vcard += f"- WhatsApp: +{query}\n"
            vcard += f"- Viber: +{query}"
        elif search_type == "email":
            vcard += f"EMAIL: {query}\n\n"
            vcard += "УТЕЧКИ:\n"
            vcard += "- haveibeenpwned: чисто\n"
            vcard += "- dehashed: чисто"
        elif search_type == "ip":
            vcard += f"IP: {query}\n\n"
            vcard += "ГЕО:\n"
            vcard += f"- Страна: Россия\n"
            vcard += f"- Город: Москва"
        elif search_type == "domain":
            vcard += f"ДОМЕН: {query}\n\n"
            vcard += "WHOIS:\n"
            vcard += f"- Владелец: Private\n"
            vcard += f"- Статус: Active"
        else:
            vcard += f"ДАННЫЕ: {query}"
        vcard += "\n================================="
        return vcard

    vcard = "🪪 *ВИЗИТКА*\n═══════════════════════\n\n"
    if search_type == "username":
        vcard += f"👤 ЮЗЕРНЕЙМ: `{query}`\n\n"
        vcard += "📌 СОЦСЕТИ:\n"
        vcard += f"├ VK: vk.com/{query}\n"
        vcard += f"├ IG: instagram.com/{query}\n"
        vcard += f"└ TW: twitter.com/{query}"
    elif search_type == "phone":
        vcard += f"📱 ТЕЛЕФОН: `+{query}`\n\n"
        vcard += "📌 МЕССЕНДЖЕРЫ:\n"
        vcard += f"├ Telegram: @username\n"
        vcard += f"├ WhatsApp: +{query}\n"
        vcard += f"└ Viber: +{query}"
    elif search_type == "email":
        vcard += f"📧 EMAIL: `{query}`\n\n"
        vcard += "🔍 УТЕЧКИ:\n"
        vcard += "├ haveibeenpwned: ✅\n"
        vcard += "└ dehashed: ✅"
    elif search_type == "ip":
        vcard += f"🌍 IP: `{query}`\n\n"
        vcard += "📍 ГЕО:\n"
        vcard += f"├ Страна: Россия\n"
        vcard += f"└ Город: Москва"
    elif search_type == "domain":
        vcard += f"🏠 ДОМЕН: `{query}`\n\n"
        vcard += "📌 WHOIS:\n"
        vcard += f"├ Владелец: Private\n"
        vcard += f"└ Статус: Active"
    else:
        vcard += f"🔍 ДАННЫЕ: `{query}`"
    vcard += "\n═══════════════════════"
    return vcard

def generate_graph_report(username, version='9.0'):
    connections = [
        {"name": "user1", "type": "подписан"},
        {"name": "user2", "type": "подписчик"},
        {"name": "user3", "type": "друг"},
        {"name": "user4", "type": "подписан"},
        {"name": "user5", "type": "подписчик"}
    ]

    if version in ['1.0', '6.0']:
        report = "КАРТА СВЯЗЕЙ\n=================================\n\n"
        report += f"ЦЕЛЬ: @{username}\n"
        report += f"СВЯЗЕЙ: {random.randint(5, 50)}\n\n"
        report += "СВЯЗИ:\n"
        for conn in connections[:5]:
            report += f"- {conn['name']} ({conn['type']})\n"
        report += "\n================================="
        return report

    report = "🕸️ *КАРТА СВЯЗЕЙ*\n═══════════════════════\n\n"
    report += f"👤 ЦЕЛЬ: `@{username}`\n"
    report += f"📊 СВЯЗЕЙ: `{random.randint(5, 50)}`\n\n"
    report += "📌 *СВЯЗИ:*\n"
    for conn in connections[:5]:
        emoji = "🔗" if conn['type'] == "подписан" else "👥" if conn['type'] == "друг" else "📎"
        report += f"├ {emoji} {conn['name']} ({conn['type']})\n"
    report += "\n═══════════════════════"
    return report

def get_main_menu(version='9.0'):
    if version == '1.0':
        return ReplyKeyboardMarkup([
            [KeyboardButton("Чат")],
            [KeyboardButton("Выйти")]
        ], resize_keyboard=True)

    if version == '6.0':
        return ReplyKeyboardMarkup([
            [KeyboardButton("Защита")],
            [KeyboardButton("Поиск")],
            [KeyboardButton("Помощь")],
            [KeyboardButton("Настройки")]
        ], resize_keyboard=True)

    if version == '7.0':
        return ReplyKeyboardMarkup([
            [KeyboardButton("🛡️ ЗАЩИТА"), KeyboardButton("🔍 ПОИСК")],
            [KeyboardButton("🔑 KEY HELP"), KeyboardButton("⚙️ НАСТРОЙКИ")]
        ], resize_keyboard=True)

    return ReplyKeyboardMarkup([
        [KeyboardButton("🛡️ ЗАЩИТА АККАУНТА")],
        [KeyboardButton("🔍 РАСШИРЕННЫЙ ПОИСК")],
        [KeyboardButton("🔑 KEY HELP")],
        [KeyboardButton("⚙️ НАСТРОЙКИ")]
    ], resize_keyboard=True)

def get_settings_menu(version='9.0'):
    if version in ['1.0', '6.0']:
        return ReplyKeyboardMarkup([
            [KeyboardButton("Версия бота")],
            [KeyboardButton("Назад")]
        ], resize_keyboard=True)

    return ReplyKeyboardMarkup([
        [KeyboardButton("🌐 ЯЗЫК"), KeyboardButton("🎨 ТЕМА")],
        [KeyboardButton("📞 ВЫЗОВ АДМИНА"), KeyboardButton("📌 ВЕРСИЯ")],
        [KeyboardButton("💀 СЧЕТЧИК")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_dev_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 СТАТИСТИКА")],
        [KeyboardButton("👥 ОНЛАЙН")],
        [KeyboardButton("💻 УСТРОЙСТВА")],
        [KeyboardButton("📝 ЛОГИ")],
        [KeyboardButton("🛠️ УПРАВЛЕНИЕ ФУНКЦИЯМИ")],
        [KeyboardButton("👑 АДМИН-ПАНЕЛЬ")],
        [KeyboardButton("💀 СЧЕТЧИК")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_admin_panel_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👑 СТАТЬ АДМИНИСТРАТОРОМ")],
        [KeyboardButton("📋 СПИСОК АДМИНОВ")],
        [KeyboardButton("➕ НАЗНАЧИТЬ АДМИНА")],
        [KeyboardButton("📊 СТАТИСТИКА")],
        [KeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ")],
        [KeyboardButton("📝 ЛОГИ АДМИНОВ")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_admin_main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👑 АДМИН-ПАНЕЛЬ")],
        [KeyboardButton("📊 СТАТИСТИКА")],
        [KeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ")],
        [KeyboardButton("🛡️ ЗАЩИТА АККАУНТА")],
        [KeyboardButton("🔍 РАСШИРЕННЫЙ ПОИСК")],
        [KeyboardButton("🔑 KEY HELP")],
        [KeyboardButton("⚙️ НАСТРОЙКИ")]
    ], resize_keyboard=True)

def get_key_help_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🆘 ЭКСТРЕННАЯ ПОМОЩЬ"), KeyboardButton("💀 DDOS АТАКА")],
        [KeyboardButton("🤖 ПРОВЕРКА НА БОТА"), KeyboardButton("🕸️ КАРТА СВЯЗЕЙ")],
        [KeyboardButton("🖥️ ТЕРМИНАЛ"), KeyboardButton("🔍 СКАНЕР")],
        [KeyboardButton("🔓 КРАКЕР"), KeyboardButton("🦠 ТРОЯН")],
        [KeyboardButton("📶 WIFI"), KeyboardButton("🔐 ШИФР")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

def get_search_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👤 ПО ЮЗЕРНЕЙМУ"), KeyboardButton("📱 ПО ТЕЛЕФОНУ")],
        [KeyboardButton("📧 ПО EMAIL"), KeyboardButton("🌍 ПО IP")],
        [KeyboardButton("🏠 ПО ДОМЕНУ"), KeyboardButton("🖼️ ПО ФОТО")],
        [KeyboardButton("🔙 НАЗАД В МЕНЮ")]
    ], resize_keyboard=True)

def get_language_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇧🇾 Беларуская", callback_data="lang_be")]
    ])

def get_theme_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌙 ТЕМНЫЙ", callback_data="theme_dark")],
        [InlineKeyboardButton("☀️ СВЕТЛЫЙ", callback_data="theme_light")],
        [InlineKeyboardButton("💜 ФИОЛЕТОВЫЙ", callback_data="theme_purple")]
    ])

def get_version_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1.0 - Тест", callback_data="ver_1.0")],
        [InlineKeyboardButton("6.0 - Стабильная", callback_data="ver_6.0")],
        [InlineKeyboardButton("7.0 - Средняя", callback_data="ver_7.0")],
        [InlineKeyboardButton("9.0 - Полная", callback_data="ver_9.0")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="ver_back")]
    ])

def get_ddos_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 10 MB", callback_data="ddos_10")],
        [InlineKeyboardButton("📦 100 MB", callback_data="ddos_100")],
        [InlineKeyboardButton("📦 1 GB", callback_data="ddos_1gb")],
        [InlineKeyboardButton("🔙 ОТМЕНА", callback_data="ddos_cancel")]
    ])

def get_func_control_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💀 DDOS"), KeyboardButton("🖥️ ТЕРМИНАЛ")],
        [KeyboardButton("🔍 СКАНЕР"), KeyboardButton("🔓 КРАКЕР")],
        [KeyboardButton("🦠 ТРОЯН"), KeyboardButton("📶 WIFI")],
        [KeyboardButton("🔐 ШИФР"), KeyboardButton("🔍 ПОИСК")],
        [KeyboardButton("🛡️ ЗАЩИТА")],
        [KeyboardButton("🔙 НАЗАД")]
    ], resize_keyboard=True)

# ============================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# ============================================

async def start(update, context):
    try:
        user_id = update.effective_user.id
        version = db.get_user_version(user_id)
        user_versions[user_id] = version

        is_admin = db.is_admin(user_id)
        is_main = db.is_main_admin(user_id)

        db.add_user(
            user_id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name,
            is_admin='main_admin' if is_main else 'admin' if is_admin else 'no'
        )
        db.add_activity(user_id, "start")

        device_info = get_device_info()
        db.update_device_info(user_id, device_info)

        user_devices[user_id] = {
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "last_name": update.effective_user.last_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device": device_info.get('device_model', platform.system()),
            "user_id": user_id
        }
        user_states[user_id] = "main"

        if version == '1.0':
            await update.message.reply_text(
                "БОТ ЗАПУЩЕН\n=================================\n\n"
                "Версия: 1.0 (Тест)\n"
                "Только чат",
                reply_markup=get_main_menu(version)
            )
            return

        if version == '6.0':
            await update.message.reply_text(
                "БОТ ЗАПУЩЕН\n=================================\n\n"
                "Версия: 6.0 (Стабильная)",
                reply_markup=get_main_menu(version)
            )
            return

        if version == '7.0':
            await update.message.reply_text(
                "🚀 БОТ ЗАПУЩЕН\n"
                "Версия: 7.0 (Средняя)",
                reply_markup=get_main_menu(version)
            )
            return

        if is_admin or is_main:
            await update.message.reply_text(
                f"🔥 *CYBER OSINT MASTER v9.0* 🔥\n"
                "═══════════════════════════════════════\n\n"
                f"{'👑' if is_main else '👤'} *ДОБРО ПОЖАЛОВАТЬ, АДМИНИСТРАТОР!*\n"
                "💀 *СИСТЕМА АКТИВИРОВАНА*\n"
                "⚡ *СТАТУС: ONLINE*\n\n"
                "🔥 *ВЫБЕРИТЕ ДЕЙСТВИЕ:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_admin_main_menu()
            )
            return

        await update.message.reply_text(
            "🔥 *CYBER OSINT MASTER v9.0* 🔥\n"
            "═══════════════════════════════════════\n\n"
            "💀 *СИСТЕМА АКТИВИРОВАНА*\n"
            "⚡ *СТАТУС: ONLINE*\n"
            "🛡️ *ЗАЩИТА: АКТИВНА*\n\n"
            "🔥 *ВЫБЕРИТЕ ДЕЙСТВИЕ:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu(version)
        )
    except Exception as e:
        logger.error(f"Start error: {e}")

async def handle_admin_panel(update, context):
    try:
        user_id = update.effective_user.id
        text = update.message.text

        if text == "👑 СТАТЬ АДМИНИСТРАТОРОМ":
            if db.is_admin(user_id):
                await update.message.reply_text("❌ ВЫ УЖЕ АДМИНИСТРАТОР!")
                return

            await update.message.reply_text(
                "🔑 *ВВЕДИТЕ 30-ЗНАЧНЫЙ КЛЮЧ АДМИНИСТРАТОРА:*\n"
                "═══════════════════════\n\n"
                "Введите ключ для получения прав администратора.",
                parse_mode=ParseMode.MARKDOWN
            )
            user_states[user_id] = "admin_auth_key"
            return

        if text == "➕ НАЗНАЧИТЬ АДМИНА":
            if not db.is_main_admin(user_id):
                await update.message.reply_text("❌ ТОЛЬКО ГЛАВНЫЙ АДМИН МОЖЕТ НАЗНАЧАТЬ АДМИНОВ!")
                return

            admin_key = generate_admin_key()
            pending_admin_keys[admin_key] = {
                "generated_by": user_id,
                "timestamp": datetime.now()
            }

            await update.message.reply_text(
                f"🔑 *НОВЫЙ КЛЮЧ ДЛЯ АДМИНА:*\n"
                "═══════════════════════\n\n"
                f"📌 КЛЮЧ: `{admin_key}`\n\n"
                "🔥 ОТПРАВЬТЕ ЭТОТ КЛЮЧ ПОЛЬЗОВАТЕЛЮ, КОТОРОГО ХОТИТЕ СДЕЛАТЬ АДМИНОМ.\n\n"
                "📌 ПОЛЬЗОВАТЕЛЬ ДОЛЖЕН ВВЕСТИ ЭТОТ КЛЮЧ В РАЗДЕЛЕ 'СТАТЬ АДМИНИСТРАТОРОМ'",
                parse_mode=ParseMode.MARKDOWN
            )

            db.add_admin_log(user_id, f"generated_admin_key: {admin_key}")
            return

        if text == "📋 СПИСОК АДМИНОВ":
            admins_list = db.get_admins()
            if not admins_list:
                await update.message.reply_text("📋 НЕТ АДМИНОВ В СИСТЕМЕ.")
                return

            text_admins = "👑 *СПИСОК АДМИНИСТРАТОРОВ*\n"
            text_admins += "═══════════════════════\n\n"

            for admin in admins_list:
                user_id_adm, username, first_name, last_name, role = admin
                name = f"{first_name or ''} {last_name or ''}".strip() or username or str(user_id_adm)
                role_emoji = "👑" if role == "main_admin" else "👤"
                text_admins += f"{role_emoji} *{name}*\n"
                text_admins += f"├ ID: `{user_id_adm}`\n"
                text_admins += f"├ @{username or 'без юзернейма'}\n"
                text_admins += f"└ Роль: `{role}`\n\n"

            await update.message.reply_text(text_admins, parse_mode=ParseMode.MARKDOWN)
            return

        if text == "📊 СТАТИСТИКА":
            total_users = db.get_total_users()
            online_users = len(db.get_online_users(ONLINE_TIMEOUT))
            total_searches = db.get_total_searches()
            admin_count = len(db.get_admins())

            await update.message.reply_text(
                f"📊 *СТАТИСТИКА БОТА*\n"
                "═══════════════════════\n\n"
                f"👥 ВСЕГО ПОЛЬЗОВАТЕЛЕЙ: `{total_users}`\n"
                f"🟢 ОНЛАЙН СЕЙЧАС: `{online_users}`\n"
                f"👑 АДМИНИСТРАТОРОВ: `{admin_count}`\n"
                f"🔍 ВСЕГО ПОИСКОВ: `{total_searches}`\n"
                f"💀 ВСЕГО ВЗЛОМОВ: `{hack_counter}`\n"
                f"📌 ВЕРСИЯ БОТА: `{VERSION}`\n"
                f"⚡ СТАТУС: `АКТИВЕН ✅`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if text == "👥 ВСЕ ПОЛЬЗОВАТЕЛИ":
            users = db.get_all_users()
            if not users:
                await update.message.reply_text("👥 НЕТ ПОЛЬЗОВАТЕЛЕЙ.")
                return

            text_users = "👥 *ВСЕ ПОЛЬЗОВАТЕЛИ*\n"
            text_users += "═══════════════════════\n\n"

            for user in users[:20]:
                user_id_u, username, first_name, last_name, role = user
                name = f"{first_name or ''} {last_name or ''}".strip() or username or str(user_id_u)
                role_emoji = "👑" if role == "main_admin" else "👤" if role == "admin" else ""
                text_users += f"{role_emoji} *{name}*\n"
                text_users += f"├ ID: `{user_id_u}`\n"
                text_users += f"└ @{username or 'без юзернейма'}\n\n"

            if len(users) > 20:
                text_users += f"\n📊 *ПОКАЗАНО 20 ИЗ {len(users)} ПОЛЬЗОВАТЕЛЕЙ*"

            await update.message.reply_text(text_users, parse_mode=ParseMode.MARKDOWN)
            return

        if text == "📝 ЛОГИ АДМИНОВ":
            logs = db.get_admin_logs(20)
            if not logs:
                await update.message.reply_text("📝 ЛОГИ АДМИНОВ ПУСТЫ.")
                return

            text_logs = "📝 *ЛОГИ АДМИНОВ*\n"
            text_logs += "═══════════════════════\n\n"

            for admin_id, action, target_id, timestamp in logs[:20]:
                text_logs += f"└ Админ `{admin_id}`: {action}\n"
                if target_id:
                    text_logs += f"  └ Цель: `{target_id}`\n"
                text_logs += f"  └ Время: {timestamp[:16]}\n\n"

            await update.message.reply_text(text_logs, parse_mode=ParseMode.MARKDOWN)
            return

        if text == "🔙 НАЗАД":
            user_states[user_id] = "dev"
            await update.message.reply_text("🔙 ВОЗВРАТ В МЕНЮ РАЗРАБОТЧИКА", reply_markup=get_dev_menu())
            return

        await update.message.reply_text("❌ НЕИЗВЕСТНАЯ КОМАНДА", reply_markup=get_admin_panel_menu())
    except Exception as e:
        logger.error(f"Admin panel error: {e}")

async def handle_message(update, context):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        version = get_user_version(user_id)

        if not check_rate_limit(user_id):
            await update.message.reply_text("⏳ ПОДОЖДИТЕ...")
            return

        db.add_activity(user_id, f"message: {text[:30]}")
        state = user_states.get(user_id, "main")

        # ВХОД В РЕЖИМ РАЗРАБОТЧИКА ПО ПАРОЛЮ
        if text == DEV_PASSWORD:
            dev_mode_users.add(user_id)
            user_states[user_id] = "dev"
            await update.message.reply_text(
                "✅ *РЕЖИМ РАЗРАБОТЧИКА АКТИВИРОВАН!*\n"
                "═══════════════════════\n\n"
                "🔥 ДОБРО ПОЖАЛОВАТЬ В ПАНЕЛЬ УПРАВЛЕНИЯ",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_dev_menu()
            )
            return

        # АУТЕНТИФИКАЦИЯ АДМИНА ПО КЛЮЧУ
        if state == "admin_auth_key":
            if text == MASTER_ADMIN_PASSWORD:
                db.update_admin_status(user_id, "main_admin")
                db.add_admin_log(user_id, f"became main admin")
                await update.message.reply_text(
                    "✅ *ВЫ СТАЛИ ГЛАВНЫМ АДМИНИСТРАТОРОМ!*\n"
                    "═══════════════════════\n\n"
                    "👑 ДОБРО ПОЖАЛОВАТЬ В КОМАНДУ АДМИНОВ!",
                    parse_mode=ParseMode.MARKDOWN
                )
                user_states[user_id] = "dev"
                await update.message.reply_text("Меню разработчика:", reply_markup=get_dev_menu())
                return
            elif text in pending_admin_keys:
                key_data = pending_admin_keys[text]
                if (datetime.now() - key_data["timestamp"]).seconds > 86400:
                    await update.message.reply_text("❌ КЛЮЧ ИСТЕК! ОБРАТИТЕСЬ К ГЛАВНОМУ АДМИНУ.")
                    user_states[user_id] = "dev"
                    return

                db.update_admin_status(user_id, "admin")
                db.add_admin_log(key_data["generated_by"], f"promoted user {user_id} to admin", user_id)
                del pending_admin_keys[text]

                await update.message.reply_text(
                    "✅ *ВЫ СТАЛИ АДМИНИСТРАТОРОМ!*\n"
                    "═══════════════════════\n\n"
                    "👑 ДОБРО ПОЖАЛОВАТЬ В КОМАНДУ АДМИНОВ!",
                    parse_mode=ParseMode.MARKDOWN
                )
                user_states[user_id] = "dev"
                await update.message.reply_text("Меню разработчика:", reply_markup=get_dev_menu())
                return
            else:
                await update.message.reply_text("❌ НЕВЕРНЫЙ КЛЮЧ АДМИНА!")
                user_states[user_id] = "dev"
                await update.message.reply_text("Меню разработчика:", reply_markup=get_dev_menu())
                return

        # МЕНЮ РАЗРАБОТЧИКА
        if state == "dev":
            if text == "🔙 НАЗАД":
                user_states[user_id] = "main"
                await update.message.reply_text("🔙 ВОЗВРАТ В ГЛАВНОЕ МЕНЮ", reply_markup=get_main_menu(version))
                return

            if text == "📊 СТАТИСТИКА":
                online = db.get_online_users(ONLINE_TIMEOUT)
                devices = db.get_all_devices()
                await update.message.reply_text(
                    f"📊 *СТАТИСТИКА БОТА*\n"
                    "═══════════════════════\n\n"
                    f"👥 ОНЛАЙН: `{len(online)}`\n"
                    f"💻 УСТРОЙСТВ: `{len(devices)}`\n"
                    f"💀 ВЗЛОМОВ: `{hack_counter}`\n"
                    f"📌 ВЕРСИЯ: `{VERSION}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            if text == "👥 ОНЛАЙН":
                online_users = db.get_online_users(ONLINE_TIMEOUT)
                if not online_users:
                    await update.message.reply_text("👥 НЕТ ОНЛАЙН")
                    return
                text_online = f"👥 *ОНЛАЙН ({len(online_users)})*\n═══════════════════════\n\n"
                for user in online_users[:15]:
                    username = user[1] or 'NO'
                    full_name = user[2] or username
                    version = user[6] or '9.0'
                    text_online += f"└ @{username} - {full_name}\n  └ Версия: {version}\n\n"
                await update.message.reply_text(text_online, parse_mode=ParseMode.MARKDOWN)
                return

            if text == "💻 УСТРОЙСТВА":
                devices = db.get_all_devices()
                if not devices:
                    await update.message.reply_text("💻 НЕТ УСТРОЙСТВ")
                    return
                text_dev = "💻 *УСТРОЙСТВА*\n═══════════════════════\n\n"
                for device in devices[:15]:
                    username = device[1] or 'NO'
                    os = device[6] or 'Unknown'
                    ram = device[8] or 'Unknown'
                    text_dev += f"└ @{username}\n  ├ OS: `{os}`\n  └ RAM: `{ram}`\n\n"
                await update.message.reply_text(text_dev, parse_mode=ParseMode.MARKDOWN)
                return

            if text == "📝 ЛОГИ":
                activity = db.get_user_activity(user_id, 15)
                if not activity:
                    await update.message.reply_text("📝 ЛОГ ПУСТ")
                    return
                text_log = "📝 *ЛОГ АКТИВНОСТИ*\n═══════════════════════\n\n"
                for action, timestamp in activity[:15]:
                    text_log += f"└ {action[:25]} ({timestamp[:16]})\n"
                await update.message.reply_text(text_log, parse_mode=ParseMode.MARKDOWN)
                return

            if text == "🛠️ УПРАВЛЕНИЕ ФУНКЦИЯМИ":
                await update.message.reply_text(
                    "🛠️ *УПРАВЛЕНИЕ ФУНКЦИЯМИ*\n"
                    "═══════════════════════\n\n"
                    "ВЫБЕРИТЕ ФУНКЦИЮ:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_func_control_menu()
                )
                user_states[user_id] = "func_control"
                return

            if text == "👑 АДМИН-ПАНЕЛЬ":
                user_states[user_id] = "admin_panel"
                await update.message.reply_text(
                    "👑 *АДМИН-ПАНЕЛЬ*\n"
                    "═══════════════════════\n\n"
                    "Выберите действие:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_admin_panel_menu()
                )
                return

            if text == "💀 СЧЕТЧИК":
                await show_hack_counter(update)
                return

        # АДМИН-ПАНЕЛЬ
        if state == "admin_panel":
            await handle_admin_panel(update, context)
            return

        # УПРАВЛЕНИЕ ФУНКЦИЯМИ
        if state == "func_control":
            if text == "🔙 НАЗАД":
                user_states[user_id] = "dev"
                await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_dev_menu())
                return

            func_map = {
                "💀 DDOS": "ddos_enabled",
                "🖥️ ТЕРМИНАЛ": "terminal_enabled",
                "🔍 СКАНЕР": "scanner_enabled",
                "🔓 КРАКЕР": "cracker_enabled",
                "🦠 ТРОЯН": "trojan_enabled",
                "📶 WIFI": "wifi_enabled",
                "🔐 ШИФР": "crypto_enabled",
                "🔍 ПОИСК": "search_enabled",
                "🛡️ ЗАЩИТА": "protection_enabled"
            }

            if text in func_map:
                key = func_map[text]
                dev_settings[key] = not dev_settings[key]
                status = "ВКЛЮЧЕНА ✅" if dev_settings[key] else "ОТКЛЮЧЕНА ❌"
                await update.message.reply_text(
                    f"✅ *ИЗМЕНЕНО*\n"
                    "═══════════════════════\n\n"
                    f"📌 {text}: `{status}`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_func_control_menu()
                )
                return

        # ОСТАЛЬНЫЕ ФУНКЦИИ (ЗАЩИТА, ПОИСК, KEY HELP, НАСТРОЙКИ)
        if version == '1.0':
            if text == "Выйти":
                user_states[user_id] = "main"
                await update.message.reply_text("Выход", reply_markup=get_main_menu(version))
                return
            if text == "Чат":
                user_states[user_id] = "chat"
                await update.message.reply_text("Введите сообщение:")
                return
            if state == "chat":
                await update.message.reply_text(f"Вы: {text}")
                return
            await update.message.reply_text("Выберите действие:", reply_markup=get_main_menu(version))
            return

        if text == "⚙️ НАСТРОЙКИ" or text == "Настройки":
            user_states[user_id] = "settings"
            await update.message.reply_text(
                "⚙️ *НАСТРОЙКИ*\n"
                "═══════════════════════\n\n"
                "Выберите раздел:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_settings_menu(version)
            )
            return

        if state == "settings":
            if text == "🔙 НАЗАД" or text == "Назад":
                user_states[user_id] = "main"
                if db.is_admin(user_id):
                    await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_admin_main_menu())
                else:
                    await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_main_menu(version))
                return

            if text == "🌐 ЯЗЫК":
                await update.message.reply_text("🌍 ВЫБЕРИТЕ ЯЗЫК:", reply_markup=get_language_menu())
                return

            if text == "🎨 ТЕМА":
                await update.message.reply_text("🎨 ВЫБЕРИТЕ ТЕМУ:", reply_markup=get_theme_menu())
                return

            if text == "📌 ВЕРСИЯ" or text == "Версия бота":
                await update.message.reply_text(
                    "📌 *ВЕРСИЯ БОТА*\n"
                    "═══════════════════════\n\n"
                    f"Текущая: `{version}`\n\n"
                    "Выберите версию:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_version_menu()
                )
                return

            if text == "📞 ВЫЗОВ АДМИНА":
                user_states[user_id] = "admin_auth_first"
                await update.message.reply_text("🔐 *ВВЕДИТЕ ПАРОЛЬ РАЗРАБОТЧИКА:*", parse_mode=ParseMode.MARKDOWN)
                return

            if text == "💀 СЧЕТЧИК":
                await show_hack_counter(update)
                return

        if text == "🛡️ ЗАЩИТА АККАУНТА" or text == "Защита":
            await update.message.reply_text(
                "🛡️ *ЗАЩИТА АККАУНТА*\n"
                "═══════════════════════\n\n"
                "1️⃣ СКРОЙТЕ НОМЕР (НИКТО)\n"
                "2️⃣ ЗАПРЕТИТЕ ЗВОНКИ\n"
                "3️⃣ ВКЛЮЧИТЕ 2FA\n"
                "4️⃣ ПРОВЕРЯЙТЕ СЕССИИ\n\n"
                "🔥 *БУДЬТЕ В БЕЗОПАСНОСТИ*",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if text == "🔍 РАСШИРЕННЫЙ ПОИСК" or text == "Поиск":
            user_states[user_id] = "search_menu"
            await update.message.reply_text(
                "🔍 *РАСШИРЕННЫЙ ПОИСК*\n"
                "═══════════════════════\n\n"
                "Выберите тип поиска:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_search_menu()
            )
            return

        if state == "search_menu":
            if text == "🔙 НАЗАД В МЕНЮ" or text == "Назад":
                user_states[user_id] = "main"
                if db.is_admin(user_id):
                    await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_admin_main_menu())
                else:
                    await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_main_menu(version))
                return

            search_map = {
                "👤 ПО ЮЗЕРНЕЙМУ": "username",
                "📱 ПО ТЕЛЕФОНУ": "phone",
                "📧 ПО EMAIL": "email",
                "🌍 ПО IP": "ip",
                "🏠 ПО ДОМЕНУ": "domain",
                "🖼️ ПО ФОТО": "photo"
            }

            if text in search_map:
                search_type = search_map[text]
                user_states[user_id] = f"search_{search_type}"

                prompts = {
                    "username": "👤 ВВЕДИТЕ ЮЗЕРНЕЙМ:",
                    "phone": "📱 ВВЕДИТЕ НОМЕР ТЕЛЕФОНА:",
                    "email": "📧 ВВЕДИТЕ EMAIL:",
                    "ip": "🌍 ВВЕДИТЕ IP АДРЕС:",
                    "domain": "🏠 ВВЕДИТЕ ДОМЕН:",
                    "photo": "🖼️ ОТПРАВЬТЕ ФОТО (ФАЙЛОМ)"
                }
                await update.message.reply_text(prompts[search_type], parse_mode=ParseMode.MARKDOWN)
                return

        if state.startswith("search_"):
            search_type = state.replace("search_", "")
            if search_type == "photo":
                await update.message.reply_text(
                    "🖼️ *ПОИСК ПО ФОТО*\n"
                    "═══════════════════════\n\n"
                    "📌 ФУНКЦИЯ В РАЗРАБОТКЕ",
                    parse_mode=ParseMode.MARKDOWN
                )
                user_states[user_id] = "main"
                return

            await show_loading(update, "🔍 ПОИСК...", 0.1)

            result_text = ""
            if search_type == "username":
                result_text = f"👤 ПОИСК ПО ЮЗЕРНЕЙМУ: `{text}`\n\n📌 ПРОВЕРЬТЕ TELEGRAM, VK, INSTAGRAM"
            elif search_type == "phone":
                result_text = f"📱 ПОИСК ПО ТЕЛЕФОНУ: `{text}`\n\n📌 ПРОВЕРЬТЕ TELEGRAM, WHATSAPP, TRUECALLER"
            elif search_type == "email":
                result_text = f"📧 ПОИСК ПО EMAIL: `{text}`\n\n📌 ПРОВЕРЬТЕ HAVEIBEENPWNED.COM"
            elif search_type == "ip":
                result_text = f"🌍 ПОИСК ПО IP: `{text}`\n\n📌 ПРОВЕРЬТЕ IPINFO.IO, VIRUSTOTAL.COM"
            elif search_type == "domain":
                result_text = f"🏠 ПОИСК ПО ДОМЕНУ: `{text}`\n\n📌 ПРОВЕРЬТЕ WHOIS, DNSCRECKER.ORG"
            else:
                result_text = f"🔍 РЕЗУЛЬТАТ: `{text}`"

            await update.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN)
            user_states[user_id] = "main"
            if db.is_admin(user_id):
                await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_admin_main_menu())
            else:
                await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_main_menu(version))
            return

        if text == "🔑 KEY HELP" or text == "Помощь":
            user_states[user_id] = "key_help"
            await update.message.reply_text(
                "🔥 *KEY HELP - ХАКЕРСКИЙ ИНСТРУМЕНТАРИЙ*\n"
                "═══════════════════════════════════════\n\n"
                "💀 *ВЫБЕРИТЕ ИНСТРУМЕНТ:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_key_help_menu()
            )
            return

        if state == "key_help":
            if text == "🔙 НАЗАД" or text == "Назад":
                user_states[user_id] = "main"
                if db.is_admin(user_id):
                    await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_admin_main_menu())
                else:
                    await update.message.reply_text("🔙 ВОЗВРАТ", reply_markup=get_main_menu(version))
                return

            if text == "💀 DDOS АТАКА":
                await update.message.reply_text("💀 *ВВЕДИТЕ ЦЕЛЬ (@username):*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "ddos_target"
                return

            if text == "🖥️ ТЕРМИНАЛ":
                await update.message.reply_text("🖥️ *ВВЕДИТЕ КОМАНДУ:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "terminal"
                return

            if text == "🔍 СКАНЕР":
                await update.message.reply_text("🔍 *ВВЕДИТЕ ЦЕЛЬ:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "scanner"
                return

            if text == "🔓 КРАКЕР":
                await update.message.reply_text("🔓 *ВВЕДИТЕ ЦЕЛЬ:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "cracker"
                return

            if text == "🦠 ТРОЯН":
                await update.message.reply_text("🦠 *ВВЕДИТЕ ЦЕЛЬ:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "trojan"
                return

            if text == "📶 WIFI":
                await update.message.reply_text("📶 *ВВЕДИТЕ НАЗВАНИЕ WIFI:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "wifi"
                return

            if text == "🔐 ШИФР":
                await update.message.reply_text(
                    "🔐 *РЕЖИМЫ:*\n\n"
                    "1️⃣ /encrypt ТЕКСТ\n"
                    "2️⃣ /decrypt ТЕКСТ",
                    parse_mode=ParseMode.MARKDOWN
                )
                user_states[user_id] = "crypto"
                return

            if text == "🆘 ЭКСТРЕННАЯ ПОМОЩЬ":
                await update.message.reply_text(
                    "🆘 *ЭКСТРЕННАЯ ПОМОЩЬ*\n"
                    "═══════════════════════\n\n"
                    "1️⃣ СМЕНИТЕ ПАРОЛЬ\n"
                    "2️⃣ ЗАВЕРШИТЕ СЕССИИ\n"
                    "3️⃣ ВКЛЮЧИТЕ 2FA",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            if text == "🤖 ПРОВЕРКА НА БОТА":
                await update.message.reply_text("🤖 *ВВЕДИТЕ ЮЗЕРНЕЙМ:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "bot_check"
                return

            if text == "🕸️ КАРТА СВЯЗЕЙ":
                await update.message.reply_text("🕸️ *ВВЕДИТЕ ЮЗЕРНЕЙМ:*", parse_mode=ParseMode.MARKDOWN)
                user_states[user_id] = "social_graph"
                return

        if state == "ddos_target":
            target = text.strip().replace("@", "")
            if len(target) < 1:
                await update.message.reply_text("❌ НЕВЕРНАЯ ЦЕЛЬ")
                return
            ddos_active[user_id] = target
            await update.message.reply_text(
                f"💀 *ВЫБЕРИТЕ РАЗМЕР ПАКЕТОВ ДЛЯ @{target}:*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_ddos_menu()
            )
            user_states[user_id] = "key_help"
            return

        if state == "terminal":
            await hacker_terminal(update, text)
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "scanner":
            await port_scanner(update, text)
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "cracker":
            await password_cracker(update, text)
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "trojan":
            await trojan_virus(update, text)
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "wifi":
            await wifi_hack(update, text)
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "crypto":
            if text.startswith("/encrypt"):
                await encrypt_decrypt(update, text.replace("/encrypt", "").strip(), "ENCRYPT")
            elif text.startswith("/decrypt"):
                await encrypt_decrypt(update, text.replace("/decrypt", "").strip(), "DECRYPT")
            else:
                await update.message.reply_text("❌ ИСПОЛЬЗУЙТЕ /encrypt или /decrypt")
                return
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "bot_check":
            await show_loading(update, "🤖 АНАЛИЗ...", 0.1)
            username = text.strip().replace("@", "")
            score = random.randint(10, 95)
            result = "НИЗКАЯ (Человек)" if score > 70 else "СРЕДНЯЯ" if score > 40 else "ВЫСОКАЯ (Бот)"
            emoji = "👤" if score > 70 else "🤖" if score > 40 else "💀"

            report = f"🤖 *ПРОВЕРКА НА БОТА*\n═══════════════════════\n\n"
            report += f"👤 ЦЕЛЬ: @{username}\n"
            report += f"📊 ВЕРОЯТНОСТЬ: {score}%\n"
            report += f"{emoji} РЕЗУЛЬТАТ: {result}"

            await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
            user_states[user_id] = "key_help"
            await update.message.reply_text("💀 ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "social_graph":
            username = text.strip().replace("@", "")
            if len(username) < 1:
                await update.message.reply_text("❌ НЕВЕРНЫЙ ЮЗЕРНЕЙМ")
                return

            await show_loading(update, "🕸️ ПОСТРОЕНИЕ...", 0.1)
            report = generate_graph_report(username, version)
            await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
            user_states[user_id] = "key_help"
            await update.message.reply_text("🕸️ ПРОДОЛЖИТЬ?", reply_markup=get_key_help_menu())
            return

        if state == "admin_auth_first":
            if text == DEV_PASSWORD:
                user_states[user_id] = "admin_auth_second"
                await update.message.reply_text("🔐 *ВВЕДИТЕ ВТОРОЙ ПАРОЛЬ:*", parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text("❌ НЕВЕРНЫЙ ПАРОЛЬ")
                user_states[user_id] = "settings"
                await update.message.reply_text("Настройки:", reply_markup=get_settings_menu(version))
            return

        if state == "admin_auth_second":
            if text == ADMIN_PASSWORD:
                user_states[user_id] = "settings"
                await update.message.reply_text(
                    f"📞 *АДМИНИСТРАТОР НАЙДЕН*\n"
                    "═══════════════════════\n\n"
                    f"👤 *@{ADMIN_USERNAME}*",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ НЕВЕРНЫЙ ПАРОЛЬ")
                user_states[user_id] = "settings"
                await update.message.reply_text("Настройки:", reply_markup=get_settings_menu(version))
            return

        await update.message.reply_text("💀 ИСПОЛЬЗУЙТЕ МЕНЮ:", reply_markup=get_main_menu(version))
    except Exception as e:
        logger.error(f"Handle error: {e}")
        await update.message.reply_text("❌ ОШИБКА, ПОПРОБУЙТЕ СНОВА")

async def language_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        lang = query.data.split("_")[1]
        user_languages[user_id] = lang
        db.update_language(user_id, lang)
        await query.edit_message_text(f"✅ ЯЗЫК ИЗМЕНЕН НА {lang.upper()}")
    except Exception as e:
        logger.error(f"Language error: {e}")

async def theme_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        theme = query.data.split("_")[1]
        user_themes[user_id] = theme
        db.update_theme(user_id, theme)
        name = "ТЕМНЫЙ" if theme == "dark" else "СВЕТЛЫЙ" if theme == "light" else "ФИОЛЕТОВЫЙ"
        await query.edit_message_text(f"✅ ТЕМА ИЗМЕНЕНА НА {name}")
    except Exception as e:
        logger.error(f"Theme error: {e}")

async def version_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if query.data == "ver_back":
            await query.edit_message_text("⚙️ НАСТРОЙКИ")
            await query.message.reply_text("Выберите раздел:", reply_markup=get_settings_menu())
            user_states[user_id] = "settings"
            return

        version = query.data.replace("ver_", "")
        user_versions[user_id] = version
        db.update_version(user_id, version)

        await query.edit_message_text(
            f"✅ ВЕРСИЯ ИЗМЕНЕНА НА {version}\n\n"
            "Перезапустите бота командой /start"
        )
        user_states[user_id] = "main"
    except Exception as e:
        logger.error(f"Version error: {e}")

async def ddos_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if query.data == "ddos_cancel":
            await query.edit_message_text("🔙 ОТМЕНЕНО")
            await query.message.reply_text("Key Help:", reply_markup=get_key_help_menu())
            user_states[user_id] = "key_help"
            return

        packet_size = query.data.replace("ddos_", "")
        if packet_size == "10":
            packet_size = "10 MB"
        elif packet_size == "100":
            packet_size = "100 MB"
        elif packet_size == "1gb":
            packet_size = "1 GB"

        target = ddos_active.get(user_id, "unknown")

        await query.edit_message_text(f"💀 ЗАПУСК DDOS АТАКИ НА @{target}...")
        await asyncio.sleep(0.2)
        await query.delete_message()

        await ddos_animation(update, target, packet_size)

        await update.message.reply_text("Key Help:", reply_markup=get_key_help_menu())
        user_states[user_id] = "key_help"
    except Exception as e:
        logger.error(f"DDOS callback error: {e}")

async def fav_callback(update, context):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data.replace("fav_", "").split("_", 1)
        if len(data) == 2:
            search_type, search_query = data
            db.add_favorite(user_id, search_type, search_query)
            await query.edit_message_text("✅ СОХРАНЕНО!")
    except Exception as e:
        logger.error(f"Fav error: {e}")

# ============================================
# ЗАПУСК
# ============================================

def main():
    try:
        print(f"\n🔥=== {BOT_NAME} {VERSION} ===🔥")
        print("💀 СИСТЕМА АКТИВИРОВАНА")
        print("⚡ СТАТУС: ONLINE")
        print("\n🔥 БОТ УСПЕШНО ЗАПУЩЕН!")
        print("📌 ОТПРАВЬТЕ /start В TELEGRAM\n")
        print("👑 ГЛАВНЫЙ КЛЮЧ АДМИНА: XK7M9P2R5Q8W4N6T3Y1U7L8C9V2B5D0E3")
        print("🔑 ПАРОЛЬ ДЛЯ ВХОДА В МЕНЮ РАЗРАБОТЧИКА: 987654321")

        app = ApplicationBuilder().token(TOKEN).request(request).build()

        app.add_handler(CommandHandler('start', start))
        app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
        app.add_handler(CallbackQueryHandler(theme_callback, pattern="^theme_"))
        app.add_handler(CallbackQueryHandler(version_callback, pattern="^ver_"))
        app.add_handler(CallbackQueryHandler(ddos_callback, pattern="^ddos_"))
        app.add_handler(CallbackQueryHandler(fav_callback, pattern="^fav_"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        app.run_polling()
    except Exception as e:
        logger.error(f"Main error: {e}", exc_info=True)
        print(f"\n❌ ОШИБКА: {e}\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 БОТ ОСТАНОВЛЕН")
        sys.exit(0)
