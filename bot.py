import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logging.basicConfig(level=logging.INFO)

CHOOSING, ENTER_NAME, ENTER_IPN, CHECK_STATUS = range(4)

main_keyboard = ReplyKeyboardMarkup([
    ["➕ Додати працівника"],
    ["📋 Перевірити статус"]
], resize_keyboard=True)

cancel_keyboard = ReplyKeyboardMarkup([
    ["❌ Скасувати"]
], resize_keyboard=True)

# GSpread auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.getenv("Google_Creds_Json"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Аутсорс").sheet1

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

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Вітаю!\n\n➕ Додати працівника\n📋 Перевірити статус",
        reply_markup=main_keyboard
    )
    return CHOOSING

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ Введіть ПІБ працівника:", reply_markup=cancel_keyboard)
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = proper_case(update.message.text.strip()).split()
    if len(parts) != 3:
        await update.message.reply_text("❗ Формат: Прізвище Імʼя По батькові")
        return ENTER_NAME
    context.user_data["name_parts"] = parts
    await update.message.reply_text("🔢 Введіть ІПН (10 цифр):")
    return ENTER_IPN

async def enter_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.lower() == "скасувати":
        return await cancel(update, context)

    if not is_valid_ipn(text):
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр. Спробуйте ще раз:")
        return ENTER_IPN

    surname, name, patronymic = context.user_data["name_parts"]
    birthdate = calculate_birthdate(text)

    # Додаткове логування
    logging.info(f"📥 Отримано ІПН: {text}")
    logging.info(f"📋 ПІБ: {surname} {name} {patronymic}, ДН: {birthdate}")

    try:
        row = ["", surname, name, patronymic, birthdate, text, "Очікує погодження", "Оберіть перевіряючого", ""]
        logging.info(f"📝 Додаємо рядок: {row}")

        sheet.append_row(row)
        logging.info("✅ Рядок успішно додано до Google Таблиці.")

        await update.message.reply_text("✅ Працівника додано!", reply_markup=main_keyboard)

    except Exception as e:
        logging.error(f"❌ Помилка при додаванні рядка: {e}")
        await update.message.reply_text("⚠️ Виникла помилка при додаванні до таблиці.", reply_markup=main_keyboard)

    return CHOOSING


async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Введіть ІПН працівника:", reply_markup=cancel_keyboard)
    return CHECK_STATUS

async def check_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ipn = update.message.text.strip()
    if not is_valid_ipn(ipn):
        await update.message.reply_text("❗ ІПН має містити 10 цифр.")
        return CHECK_STATUS

    data = sheet.get_all_records(expected_headers=[
        "Дата", "Прізвище", "Імя", "По батькові",
        "Дата народження", "ІПН", "Статус", "Перевіряючий", "Коментар"
    ])

    for row in data:
        if str(row["ІПН"]) == ipn:
            await update.message.reply_text(f'{row["Імя"]} {row["По батькові"]} — {row["Статус"]}', reply_markup=main_keyboard)
            return CHOOSING

    await update.message.reply_text("🚫 Працівника не знайдено", reply_markup=main_keyboard)
    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 Скасовано.", reply_markup=main_keyboard)
    return CHOOSING

# --- Start app ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("Telegram_Token")).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex("^➕"), start_add),
                MessageHandler(filters.Regex("^📋"), start_check)
            ],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ipn)],
            CHECK_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_ipn)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌"), cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.run_polling()
