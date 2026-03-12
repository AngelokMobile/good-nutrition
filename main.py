import os
import json
import random
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загрузка переменных окружения (для локального теста; на Render они будут в системе)
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ЗАГРУЗКА БАЗЫ ЗНАНИЙ ====================
KNOWLEDGE_DIR = Path("knowledge")
MEALS_DIR = KNOWLEDGE_DIR / "meals"

def load_meals():
    """Загружает все меню из JSON-файлов в папке knowledge/meals."""
    meals_db = {}
    if not MEALS_DIR.exists():
        logger.warning("Папка meals не найдена")
        return meals_db
    for file_path in MEALS_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                cal = file_path.stem  # имя файла без расширения, например "1250"
                meals_db[cal] = json.load(f)
                logger.info(f"Загружено меню {cal} ккал, дней: {len(meals_db[cal])}")
        except Exception as e:
            logger.error(f"Ошибка загрузки {file_path}: {e}")
    return meals_db

MEALS = load_meals()

# ==================== РАБОТА С ПОЛЬЗОВАТЕЛЬСКИМИ ДАННЫМИ ====================
USER_DATA_FILE = Path("user_data.json")

def load_user_data():
    """Читает user_data.json, возвращает словарь."""
    if not USER_DATA_FILE.exists():
        return {}
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения user_data.json: {e}")
        return {}

def save_user_data(data):
    """Сохраняет словарь в user_data.json."""
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка записи user_data.json: {e}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_user_profile(user_id: str):
    """Возвращает профиль пользователя (словарь с данными)."""
    data = load_user_data()
    if user_id not in data:
        data[user_id] = {
            "preferences": {},       # калории, количество персон и т.д.
            "current_menu": {},      # текущее выбранное меню
            "leftovers": []          # список остатков
        }
        save_user_data(data)
    return data[user_id]

def update_user_profile(user_id: str, profile):
    """Обновляет профиль пользователя."""
    data = load_user_data()
    data[user_id] = profile
    save_user_data(data)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение."""
    user_id = str(update.effective_user.id)
    get_user_profile(user_id)  # создаём запись, если нет
    await update.message.reply_text(
        "🍽 Привет! Я MealPlannerBot – помогу составить меню и список покупок.\n\n"
        "Примеры запросов:\n"
        "• «составь меню на 3 дня 1400 ккал»\n"
        "• /leftovers курица, помидоры, гречка\n"
        "• /shopping_list – показать текущий список\n"
        "• /help – подробная справка"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка."""
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
    """Сохраняет список остатков."""
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    text = update.message.text.replace("/leftovers", "").strip()
    if not text:
        await update.message.reply_text("Укажи продукты через запятую, например: /leftovers курица, помидоры")
        return
    # Разбираем список
    items = [item.strip().lower() for item in text.split(",") if item.strip()]
    profile["leftovers"] = items
    update_user_profile(user_id, profile)
    await update.message.reply_text(f"✅ Запомнил остатки: {', '.join(items)}")

async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Формирует список покупок из текущего меню (упрощённо)."""
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    menu = profile.get("current_menu", {})
    if not menu:
        await update.message.reply_text("Сначала составь меню командой «составь меню ...»")
        return
    # Простой сбор ингредиентов (для теста выводим все названия блюд)
    # В будущем здесь нужно будет парсить ингредиенты из JSON
    ingredients = []
    for day, meals in menu.items():
        for meal_name, meal_data in meals.items():
            if isinstance(meal_data, dict) and "ingredients" in meal_data:
                for ing in meal_data["ingredients"]:
                    ingredients.append(ing["name"])
            else:
                # Если данные в простом формате (строка) – пока игнорируем
                pass
    if ingredients:
        # Убираем дубликаты и вычитаем leftovers
        leftovers = profile.get("leftovers", [])
        needed = list(set(ingredients) - set(leftovers))
        await update.message.reply_text("🛒 Список покупок:\n• " + "\n• ".join(needed))
    else:
        await update.message.reply_text("Не удалось собрать ингредиенты (возможно, меню в упрощённом формате).")

# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает естественно-языковые запросы."""
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    text = update.message.text.lower()

    # Очень простой парсер для демо
    if "составь меню" in text:
        # Пытаемся извлечь калории и дни
        days = 3  # по умолчанию
        calories = "1400"  # по умолчанию
        words = text.split()
        for i, word in enumerate(words):
            if word.isdigit():
                # Если число стоит рядом со словом "дней" или "дня"
                if i+1 < len(words) and ("дн" in words[i+1] or "день" in words[i+1]):
                    days = int(word)
                elif i+1 < len(words) and ("ккал" in words[i+1] or "калорий" in words[i+1]):
                    calories = word
                # Если просто число – считаем калориями (упрощённо)
                elif calories == "1400":
                    calories = word
        # Проверяем, есть ли такое меню в базе
        if calories not in MEALS:
            available = ", ".join(MEALS.keys())
            await update.message.reply_text(f"Меню на {calories} ккал нет. Доступно: {available}")
            return
        # Выбираем случайные дни из меню (можем повторять)
        menu_days = list(MEALS[calories].keys())
        selected_days = {}
        for i in range(1, days+1):
            day_key = random.choice(menu_days)
            selected_days[f"day{i}"] = MEALS[calories][day_key]
        profile["current_menu"] = selected_days
        update_user_profile(user_id, profile)
        # Формируем ответ
        response = f"🍽 Меню на {days} дней ({calories} ккал):\n\n"
        for day_name, meals in selected_days.items():
            response += f"*{day_name}*\n"
            for meal_type, meal_desc in meals.items():
                if isinstance(meal_desc, dict):
                    # если в JSON есть структура с именем и ингредиентами
                    response += f"  {meal_type}: {meal_desc.get('name', meal_desc)}\n"
                else:
                    response += f"  {meal_type}: {meal_desc}\n"
            response += "\n"
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Я пока понимаю только команды /start, /help, /leftovers, /shopping_list и фразу «составь меню».")

# ==================== НАСТРОЙКА И ЗАПУСК ====================
async def post_init(application: Application):
    """Устанавливает команды бота в интерфейсе Telegram."""
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Справка"),
        BotCommand("leftovers", "Сообщить остатки продуктов"),
        BotCommand("shopping_list", "Показать список покупок"),
    ])

def main():
    """Точка входа."""
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("leftovers", leftovers))
    application.add_handler(CommandHandler("shopping_list", shopping_list))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
