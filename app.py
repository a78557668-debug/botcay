# ... (все твои импорты и код до функции main() остаются без изменений) ...

import asyncio
import logging
import sqlite3
import os
import sys
import time
import random
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web  # ДОБАВЛЕНО ДЛЯ RENDER

# ... (КОНФИГ, FEATURES, БАЗА ДАННЫХ, КЛАВИАТУРЫ, OSINT ЛОГИКА, ХЕНДЛЕРЫ — ОСТАВЬ ВСЁ КАК ЕСТЬ) ...

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Web server started on port {port}")

# ==================== АВТО-ПЕРЕЗАПУСК И ЗАЩИТА ====================
async def main():
    init_db()
    
    # Запускаем веб-сервер для Render
    await start_web_server()
    
    while True:
        try:
            print(f"\n🚀 БОТ ЗАПУЩЕН! Пароль админа: {ADMIN_PASSWORD}")
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"❌ Бот упал: {e}")
            print("🔄 Перезапуск через 3 секунды...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
