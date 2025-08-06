import os
import json
import logging
from datetime import date, datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logging.basicConfig(level=logging.INFO)

# --- Стани ---
CHOOSING, ENTER_NAME, ENTER_IPN, CHECK_STATUS = range(4)

# --- Список користувачів з доступом до аналітики ---
ANALYTICS_USERS = [7555663197]

def is_analytics_user(user_id):
    return user_id in ANALYTICS_USERS

def get_main_keyboard(user_id):
    if is_analytics_user(user_id):
        return ReplyKeyboardMarkup([
            ["➕ Додати працівника"],
            ["📋 Перевірити статус"],
            ["📊 Аналітика"]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            ["➕ Додати працівника"],
            ["📋 Перевірити статус"]
        ], resize_keyboard=True)

cancel_keyboard = ReplyKeyboardMarkup([
    ["❌ Скасувати"]
], resize_keyboard=True)

# --- Підключення до Google Таблиці ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.getenv("Google_Creds_Json"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Перевірка аутсорс").worksheet("Кандидати")

HEADERS = ["Дата", "ПІБ", "Дата народження", "ІПН", "Статус", "Перевіряючий", "Коментар"]

# --- Перевірки ---
def is_valid_ipn(text):
    return text.isdigit() and len(text) == 10

def proper_case(text):
    return " ".join([w.capitalize() for w in text.split()])

def calculate_birthdate(ipn):
    try:
        base = date(1900, 1, 1)
        return (base + timedelta(days=int(ipn[:5]) - 1)).strftime("%d.%m.%Y")
    except:
        return ""

def normalize_ipn(ipn):
    return str(ipn).strip().zfill(10)

# --- Обробники ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*👋 Вітаю!*\n\nЦей бот створений командою Аврора для перевірки працівників аутсорсу\n"
        "Якщо ви хочете додати працівника на перевірку, натисність:\n"
        "========================================================\n"
        "                                           ➕ Додати працівника\n"
        "========================================================\n"
        "Якщо ви хочете перевірити чи погоджений/не погоджений працівник, натисніть:\n"
        "========================================================\n"
        "                                           📋 Перевірити статус\n"
        "========================================================\n\n"
        "Можна здійснювати перевірку більше одного працівника.\n"
        "Для цього внесіть ІПН декількох працівників через пробіл або в стовпчик.\n\n"
        "*Важливо.* Перевірка працівників здійснюється *до 24 годин*.\n"
        "*Субота та неділя - не робочі дні*, тому якщо ви надіслали працівника на перевірку у п'ятницю, результат буде у цей же день, або у понеділок.\n\n"
        "Бажаємо гарного дня!",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(update.effective_user.id)
    )
    return CHOOSING

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ Введіть ПІБ працівника:", reply_markup=cancel_keyboard)
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "скасувати":
        return await cancel(update, context)

    if len(text.split()) < 2:
        await update.message.reply_text("❗ Формат: Прізвище Ім’я По-батькові")
        return ENTER_NAME

    context.user_data["pib"] = proper_case(text)
    await update.message.reply_text("🔢 Введіть ІПН (10 цифр):", reply_markup=cancel_keyboard)
    return ENTER_IPN

async def enter_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "скасувати":
        return await cancel(update, context)

    if not is_valid_ipn(text):
        await update.message.reply_text("❌ ІПН має містити 10 цифр.")
        return ENTER_IPN

    ipn = text
    context.user_data["ipn"] = ipn

    try:
        data = sheet.get_all_records(expected_headers=HEADERS)
    except Exception as e:
        logging.error(f"Помилка зчитування: {e}")
        await update.message.reply_text("⚠️ Спробуйте пізніше.", reply_markup=get_main_keyboard(update.effective_user.id))
        return CHOOSING

    for row in data:
        if normalize_ipn(row.get("ІПН")) == normalize_ipn(ipn):
            await update.message.reply_text("🚫 Працівник вже існує.", reply_markup=get_main_keyboard(update.effective_user.id))
            return CHOOSING

    birthdate = calculate_birthdate(ipn)
    full_name = context.user_data["pib"]
    current_date = datetime.today().strftime("%d.%m.%y")
    new_row = [current_date, full_name, birthdate, ipn, "Очікує погодження", "", "", ""]

    try:
        sheet.append_row(new_row)
        await update.message.reply_text("✅ Працівника додано!", reply_markup=get_main_keyboard(update.effective_user.id))

        try:
            senders_sheet = client.open("Перевірка аутсорс").worksheet("Відправники")
            telegram_id = str(update.effective_user.id)
            senders_sheet.append_row([ipn, telegram_id])
        except Exception as e:
            logging.error(f"Не вдалося записати Telegram ID: {e}")

    except Exception as e:
        logging.error(f"Помилка запису: {e}")
        await update.message.reply_text("⚠️ Не вдалося додати.", reply_markup=get_main_keyboard(update.effective_user.id))

    return CHOOSING

async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Введіть один або кілька ІПН (через пробіл):", reply_markup=cancel_keyboard)
    return CHECK_STATUS

async def check_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "скасувати":
        return await cancel(update, context)

    ipns = text.split()
    if not all(ipn.isdigit() and len(ipn) == 10 for ipn in ipns):
        await update.message.reply_text("❌ Усі ІПН мають містити 10 цифр.")
        return CHECK_STATUS

    try:
        data = sheet.get_all_records()
    except Exception as e:
        logging.error(f"Помилка при зчитуванні: {e}")
        await update.message.reply_text("⚠️ Не вдалося зчитати дані.")
        return CHOOSING

    response = []
    for ipn in ipns:
        found = False
        for row in data:
            if str(row.get("ІПН", "")).zfill(10) == ipn:
                response.append(f"{ipn} – {row.get('ПІБ')} – {row.get('Статус')}")
                found = True
                break
        if not found:
            response.append(f"{ipn} – ❌ Не знайдено")

    await update.message.reply_text("\n".join(response), reply_markup=get_main_keyboard(update.effective_user.id))
    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 Скасовано.", reply_markup=get_main_keyboard(update.effective_user.id))
    return CHOOSING

# --- Запуск ---
if __name__ == "__main__":
    from analytics_menu import analytics_handlers

    app = ApplicationBuilder().token(os.getenv("Telegram_Token")).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex("^➕ Додати працівника$"), start_add),
                MessageHandler(filters.Regex("^📋 Перевірити статус$"), start_check),
                MessageHandler(filters.Regex("^❌ Скасувати$"), cancel),
            ],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ipn)],
            CHECK_STATUS: [
                MessageHandler(filters.Regex("^❌ Скасувати|Скасувати$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_ipn)
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), cancel)],
        allow_reentry=True
    )

    app.add_handler(conv)

    # Додаємо аналітичні обробники
    for handler in analytics_handlers:
        app.add_handler(handler)

    app.run_polling()
