import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========== HTTP-СЕРВЕР ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_http():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"✅ HTTP-сервер запущен на порту {PORT}")
    server.serve_forever()

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍽 Привет! Я MealPlannerBot – помогу составить меню и список покупок.\n\n"
        "Примеры запросов:\n"
        "• «составь меню на 3 дня 1400 ккал»\n"
        "• /leftovers курица, помидоры, гречка\n"
        "• /shopping_list – показать текущий список\n"
        "• /help – подробная справка"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Доступные команды:\n"
        "/start – начать работу\n"
        "/help – эта справка\n"
        "/leftovers [список] – сообщить, какие продукты уже есть (через запятую)\n"
        "/shopping_list – показать список покупок на основе текущего меню\n\n"
        "Можно также писать обычные фразы, например:\n"
        "«составь меню на 5 дней 1600 ккал»"
    )

async def leftovers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пока просто подтверждение
    await update.message.reply_text("✅ Функция leftovers пока в разработке")

async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 Функция shopping_list пока в разработке")

# ========== ЗАПУСК ==========
def main():
    Thread(target=run_http, daemon=True).start()
    logger.info("✅ HTTP-поток запущен")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("leftovers", leftovers))
    app.add_handler(CommandHandler("shopping_list", shopping_list))

    logger.info("🤖 Бот запущен и готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
