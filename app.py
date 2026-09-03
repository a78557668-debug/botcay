import os
import threading
import time
from flask import Flask, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

TOKEN = os.environ.get("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)

@app.route('/health')
def health():
    return {"status": "ok"}, 200

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ROOTNET SECURE OS подключен!")

def run_telegram_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    print("[SYSTEM] Запуск Thread для Telegram Bot...")
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.start()
    
    print(f"[SYSTEM] Запуск Flask на порту {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
