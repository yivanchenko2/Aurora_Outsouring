from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, filters
from bot import CHOOSING, get_main_keyboard, sheet
from datetime import datetime

# --- Стани для аналітики ---
ANALYTICS_MENU, ANALYTICS_DATE_INPUT, STATISTICS_MENU, STATISTICS_PERIOD_START, STATISTICS_PERIOD_END, STATISTICS_STANDARD = range(100, 106)

analytics_keyboard = ReplyKeyboardMarkup([
    ["🔍 Перевірити за датою"],
    ["📊 Статистика"],
    ["⬅️ Назад"]
], resize_keyboard=True)

statistics_keyboard = ReplyKeyboardMarkup([
    ["📅 За період", "📆 Стандарт"],
    ["⬅️ Назад"]
], resize_keyboard=True)

# === Обробник кнопки "📊 Аналітика" ===
async def show_analytics_menu(update, context):
    await update.message.reply_text("📊 *Меню аналітики*", reply_markup=analytics_keyboard, parse_mode="Markdown")
    return ANALYTICS_MENU

# === Обробник "🔍 Перевірити за датою" ===
async def ask_analytics_date(update, context):
    await update.message.reply_text("📅 Введіть дату у форматі дд.мм.рр (наприклад 05.07.24):")
    return ANALYTICS_DATE_INPUT

async def show_employees_by_date(update, context):
    date_str = update.message.text.strip()
    try:
        # Пробуємо парсити дату
        dt = datetime.strptime(date_str, "%d.%m.%y")
        formatted_date = dt.strftime("%d.%m.%y")
    except ValueError:
        await update.message.reply_text("❌ Невірний формат. Спробуйте ще раз у форматі дд.мм.рр (наприклад 05.07.24):")
        return ANALYTICS_DATE_INPUT

    try:
        records = sheet.get_all_records()
        results = []
        for row in records:
            if row.get("Дата") == formatted_date:
                results.append(f"👤 {row.get('ПІБ')} – *{row.get('Статус')}*")

        if results:
            await update.message.reply_text("\n".join(results), parse_mode="Markdown")
        else:
            await update.message.reply_text("ℹ️ Працівників за цю дату не знайдено.")

    except Exception as e:
        await update.message.reply_text("⚠️ Помилка при зчитуванні таблиці.")

    keyboard = get_main_keyboard(update.effective_user.id)
    await update.message.reply_text("⬅️ Повернення до головного меню", reply_markup=keyboard)
    return CHOOSING

# === Обробник "📊 Статистика" ===
async def ask_statistics_type(update, context):
    await update.message.reply_text("📊 Оберіть тип статистики:", reply_markup=statistics_keyboard)
    return STATISTICS_MENU

# === Обробник повернення назад з меню аналітики ===
async def analytics_back(update, context):
    keyboard = get_main_keyboard(update.effective_user.id)
    await update.message.reply_text("🔙 Повертаємося назад...", reply_markup=keyboard)
    return CHOOSING

# === Обгортка для додавання handlers ===
analytics_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^📊 Аналітика$"), show_analytics_menu)
    ],
    states={
        ANALYTICS_MENU: [
            MessageHandler(filters.Regex("^🔍 Перевірити за датою$"), ask_analytics_date),
            MessageHandler(filters.Regex("^📊 Статистика$"), ask_statistics_type),
            MessageHandler(filters.Regex("^⬅️ Назад$"), analytics_back),
        ],
        ANALYTICS_DATE_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, show_employees_by_date)
        ],
    },
    fallbacks=[MessageHandler(filters.Regex("^⬅️ Назад$"), analytics_back)],
    allow_reentry=True
)

analytics_handlers = [analytics_conv]
