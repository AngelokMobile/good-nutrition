import os
import json
import random
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from aiohttp import web

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ЗАГРУЗКА МЕНЮ ====================
KNOWLEDGE_DIR = Path("knowledge")
MEALS_DIR = KNOWLEDGE_DIR / "meals"

def load_meals():
    meals_db = {}
    if not MEALS_DIR.exists():
        logger.warning("Папка meals не найдена")
        return meals_db
    for file_path in MEALS_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                cal = file_path.stem
                meals_db[cal] = json.load(f)
                logger.info(f"Загружено меню {cal} ккал, дней: {len(meals_db[cal])}")
        except Exception as e:
            logger.error(f"Ошибка загрузки {file_path}: {e}")
    return meals_db

MEALS = load_meals()

# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ДАННЫЕ ====================
USER_DATA_FILE = Path("user_data.json")

def load_user_data():
    if not USER_DATA_FILE.exists():
        return {}
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения user_data.json: {e}")
        return {}

def save_user_data(data):
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка записи user_data.json: {e}")

def get_user_profile(user_id: str):
    data = load_user_data()
    if user_id not in data:
        data[user_id] = {"preferences": {}, "current_menu": {}, "leftovers": []}
        save_user_data(data)
    return data[user_id]

def update_user_profile(user_id: str, profile):
    data = load_user_data()
    data[user_id] = profile
    save_user_data(data)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    get_user_profile(user_id)
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
        "«составь меню на 5 дней 1600 ккал»\n"
        "«замени ужин на ...» (пока не реализовано)"
    )

async def leftovers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    text = update.message.text.replace("/leftovers", "").strip()
    if not text:
        await update.message.reply_text("Укажи продукты через запятую, например: /leftovers курица, помидоры")
        return
    items = [item.strip().lower() for item in text.split(",") if item.strip()]
    profile["leftovers"] = items
    update_user_profile(user_id, profile)
    await update.message.reply_text(f"✅ Запомнил остатки: {', '.join(items)}")

async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    menu = profile.get("current_menu", {})
    if not menu:
        await update.message.reply_text("Сначала составь меню командой «составь меню ...»")
        return
    
    ingredients = []
    for day, meals in menu.items():
        for meal_name, meal_data in meals.items():
            if isinstance(meal_data, dict) and "ingredients" in meal_data:
                for ing in meal_data["ingredients"]:
                    ingredients.append(ing["name"])
    
    if ingredients:
        leftovers = profile.get("leftovers", [])
        needed = list(set(ingredients) - set(leftovers))
        await update.message.reply_text("🛒 Список покупок:\n• " + "\n• ".join(needed))
    else:
        await update.message.reply_text("Не удалось собрать ингредиенты (возможно, меню в упрощённом формате).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    text = update.message.text.lower()

    if "составь меню" in text:
        days = 3
        calories = "1400"
        words = text.split()
        for i, word in enumerate(words):
            if word.isdigit():
                if i+1 < len(words) and ("дн" in words[i+1] or "день" in words[i+1]):
                    days = int(word)
                elif i+1 < len(words) and ("ккал" in words[i+1] or "калорий" in words[i+1]):
                    calories = word
                elif calories == "1400":
                    calories = word
        if calories not in MEALS:
            available = ", ".join(MEALS.keys())
            await update.message.reply_text(f"Меню на {calories} ккал нет. Доступно: {available}")
            return
        menu_days = list(MEALS[calories].keys())
        selected_days = {}
        for i in range(1, days+1):
            day_key = random.choice(menu_days)
            selected_days[f"day{i}"] = MEALS[calories][day_key]
        profile["current_menu"] = selected_days
        update_user_profile(user_id, profile)
        response = f"🍽 Меню на {days} дней ({calories} ккал):\n\n"
        for day_name, meals in selected_days.items():
            response += f"*{day_name}*\n"
            for meal_type, meal_desc in meals.items():
                if isinstance(meal_desc, dict):
                    response += f"  {meal_type}: {meal_desc.get('name', meal_desc)}\n"
                else:
                    response += f"  {meal_type}: {meal_desc}\n"
            response += "\n"
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Я пока понимаю только команды /start, /help, /leftovers, /shopping_list и фразу «составь меню».")

# ==================== HTTP-СЕРВЕР (ЗАПУСКАЕТСЯ ПЕРВЫМ) ====================
async def health_check(request):
    return web.Response(text="Bot is running")

async def run_http_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ HTTP-сервер запущен на порту {PORT}")
    # Сервер остаётся работать в фоне

async def main():
    # Сначала запускаем HTTP-сервер (чтобы Render увидел порт)
    await run_http_server()
    
    # Затем запускаем бота
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("leftovers", leftovers))
    application.add_handler(CommandHandler("shopping_list", shopping_list))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Бот запущен и готов к работе")
    await application.run_polling()

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Справка"),
        BotCommand("leftovers", "Сообщить остатки продуктов"),
        BotCommand("shopping_list", "Показать список покупок"),
    ])

if __name__ == "__main__":
    asyncio.run(main())
