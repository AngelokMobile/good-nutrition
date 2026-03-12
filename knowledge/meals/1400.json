import os
import json
import random
import logging
import re
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

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
        data[user_id] = {
            "preferences": {},
            "current_menu": {},
            "leftovers": []
        }
        save_user_data(data)
    return data[user_id]

def update_user_profile(user_id: str, profile):
    data = load_user_data()
    data[user_id] = profile
    save_user_data(data)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИНГРЕДИЕНТОВ ====================
def parse_quantity(quantity_str):
    """
    Извлекает числовое значение и единицу измерения из строки количества.
    Пример: "200 гр" -> (200.0, "гр")
            "2 шт" -> (2.0, "шт")
            "½ ст.л" -> (0.5, "ст.л")
            "по вкусу" -> (None, "по вкусу")
    """
    if not quantity_str or quantity_str.strip() == "":
        return None, ""
    # Заменяем дробные обозначения ½, ¼ и т.п.
    fractions = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 0.333, "⅔": 0.667}
    for frac, val in fractions.items():
        if frac in quantity_str:
            quantity_str = quantity_str.replace(frac, str(val))
    # Ищем число в строке (целое или десятичное)
    match = re.search(r'(\d+[.,]?\d*)', quantity_str)
    if match:
        num_str = match.group(1).replace(',', '.')
        try:
            number = float(num_str)
        except:
            number = None
        # Остаток после числа — единица измерения
        unit = quantity_str[match.end():].strip()
        return number, unit
    else:
        return None, quantity_str.strip()

def normalize_product_name(name):
    """Приводит название продукта к единому виду."""
    return name.strip().lower()

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

    # Собираем все ингредиенты из меню
    all_ingredients = []  # список словарей с name, quantity
    for day, meals in menu.items():
        for meal_name, meal_data in meals.items():
            if isinstance(meal_data, dict) and "ingredients" in meal_data:
                for ing in meal_data["ingredients"]:
                    all_ingredients.append({
                        "name": normalize_product_name(ing["name"]),
                        "quantity": ing.get("quantity", "")
                    })

    if not all_ingredients:
        await update.message.reply_text("Не удалось собрать ингредиенты (возможно, меню в упрощённом формате).")
        return

    # Суммируем ингредиенты
    aggregated = defaultdict(lambda: {"total": 0.0, "unit": None, "items": []})

    for ing in all_ingredients:
        name = ing["name"]
        qty_str = ing["quantity"]
        number, unit = parse_quantity(qty_str)
        if number is None:
            # Если не удалось распарсить число, сохраняем исходную строку как есть
            aggregated[name]["items"].append(qty_str)
            continue
        # Если для этого продукта ещё нет единицы, устанавливаем
        if aggregated[name]["unit"] is None:
            aggregated[name]["unit"] = unit
        # Если единицы совпадают, суммируем
        if aggregated[name]["unit"] == unit:
            aggregated[name]["total"] += number
        else:
            # Если единицы разные, сохраняем в отдельный список как исходную строку
            aggregated[name]["items"].append(f"{number} {unit}" if unit else str(number))

    # Вычитаем leftovers (упрощённо: если продукт есть в leftovers, исключаем его полностью)
    leftovers_set = {normalize_product_name(x) for x in profile.get("leftovers", [])}

    # Формируем итоговый список
    result_lines = []
    for name, data in aggregated.items():
        if name in leftovers_set:
            continue
        parts = []
        if data["total"] > 0:
            total = round(data["total"], 2)
            unit = data["unit"] if data["unit"] else ""
            parts.append(f"{total} {unit}".strip())
        if data["items"]:
            parts.extend(data["items"])
        if parts:
            result_lines.append(f"• {name}: {', '.join(parts)}")
        else:
            result_lines.append(f"• {name}")

    if not result_lines:
        await update.message.reply_text("У тебя уже есть все необходимые продукты!")
        return

    # Разбиваем на части, если слишком длинный список (Telegram ограничение 4096 символов)
    text = "🛒 Список покупок:\n" + "\n".join(result_lines)
    await update.message.reply_text(text)

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

# ==================== HTTP-СЕРВЕР ====================
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

# ==================== ЗАПУСК ====================
async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("help", "Справка"),
        BotCommand("leftovers", "Сообщить остатки продуктов"),
        BotCommand("shopping_list", "Показать список покупок"),
    ])

def main():
    Thread(target=run_http, daemon=True).start()
    logger.info("✅ HTTP-поток запущен")

    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("leftovers", leftovers))
    app.add_handler(CommandHandler("shopping_list", shopping_list))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Бот запущен и готов к работе!")
    app.run_polling()

if __name__ == "__main__":
    main()
