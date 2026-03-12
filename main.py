import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from dotenv import load_dotenv

# Загружаем токен
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

# Настройка логов
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========== ПРОСТОЙ HTTP-СЕРВЕР ДЛЯ RENDER ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        # Не захламляем логи HTTP-сервера
        pass

def run_http():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"✅ HTTP-сервер запущен на порту {PORT}")
    server.serve_forever()

# ========== ПРОСТЫЕ КОМАНДЫ ТЕЛЕГРАМ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Получена команда /start от {update.effective_user.id}")
    await update.message.reply_text("✅ Бот работает! Команды: /start, /help")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Доступные команды:\n/start - приветствие\n/help - эта справка")

# ========== ЗАПУСК ==========
def main():
    # Запускаем HTTP-сервер в отдельном потоке
    http_thread = Thread(target=run_http, daemon=True)
    http_thread.start()
    logger.info("✅ HTTP-поток запущен")

    # Запускаем бота
    logger.info("🤖 Запуск Telegram-бота...")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    logger.info("🎉 Бот запущен и готов к работе!")
    application.run_polling()

if __name__ == "__main__":
    main()
