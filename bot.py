import os
import json
import logging
from datetime import date, timedelta
from io import StringIO

from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logging.basicConfig(level=logging.INFO)

# Conversation steps
CHOOSING, ENTER_NAME, ENTER_IPN, CHECK_STATUS = range(4)

# Menus
main_keyboard = ReplyKeyboardMarkup([
    ["➕ Додати працівника"],
    ["📋 Перевірити статус"]
], resize_keyboard=True)

cancel_keyboard = ReplyKeyboardMarkup([
    ["❌ Скасувати"]
], resize_keyboard=True)

# Google Sheets init
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.getenv("Google_Creds_Json"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Перевірка аутсорс").sheet1  # Назва таблиці

# --- Utils ---
def proper_case(text):
    return " ".join([word.capitalize() for word in text.split()])

def is_valid_ipn(text):
    return text.isdigit() and len(text) == 10

def calculate_birthdate(ipn: str) -> str:
    try:
        basedate = date(1900, 1, 1)
        days = int(ipn[:5])
        birthdate = basedate + timedelta(days=days - 1)
        return birthdate.strftime("%d.%m.%Y")
    except:
        return ""


# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first = update.effective_user.first_name
    welcome_message = (
        f"👋 Вітаю, {user_first}!\n\n"
        "Цей бот створений для додавання працівників та перевірки їх статусу.\n"
        "Скористайся меню нижче, щоб:\n"
        "➕ Додати нового працівника\n"
        "📋 Перевірити статус працівника\n\n"
        "Якщо щось піде не так — натисни ❌ Скасувати."
    )
    await update.message.reply_text(welcome_message, reply_markup=main_keyboard)
    return CHOOSING

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ Введіть ПІБ працівника:", reply_markup=cancel_keyboard)
    return ENTER_NAME

async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Введіть ІПН працівника:", reply_markup=cancel_keyboard)
    return CHECK_STATUS

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "скасувати":
        return await cancel(update, context)

    full_name = proper_case(text)
    parts = full_name.split()
    if len(parts) != 3:
        await update.message.reply_text("❗ Введіть ПІБ у форматі: Прізвище Імʼя По-батькові")
        return ENTER_NAME

    context.user_data["full_name"] = full_name
    await update.message.reply_text("🔢 Введіть ІПН (10 цифр):", reply_markup=cancel_keyboard)
    return ENTER_IPN

async def enter_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "скасувати":
        return await cancel(update, context)

    if not is_valid_ipn(text):
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр. Спробуйте ще раз:")
        return ENTER_IPN

    ipn = text
    data = sheet.get_all_records()
    for row in data:
        if str(row.get("ІПН")) == ipn:
            await update.message.reply_text("🚫 Працівника з таким ІПН вже додано. Спробуйте ще раз або перевірте статус.", reply_markup=main_keyboard)
            return CHOOSING

    full_name = context.user_data["full_name"]
    parts = full_name.split()
    birthdate = calculate_birthdate(ipn)

    sheet.append_row([
        "", full_name, "", "", birthdate, ipn, "Очікує погодження", "", ""
    ])

    await update.message.reply_text("✅ Працівника додано!", reply_markup=main_keyboard)
    return CHOOSING

async def check_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "скасувати":
        return await cancel(update, context)

    if not is_valid_ipn(text):
        await update.message.reply_text("❌ ІПН має містити 10 цифр. Спробуйте ще раз:")
        return CHECK_STATUS

    data = sheet.get_all_records()
    for row in data:
        if str(row.get("ІПН", "")) == text:
            full_name = row.get("ПІБ", "")
            parts = full_name.split()
            if len(parts) >= 3:
                result = f'{parts[1]} {parts[2]} – {row["Статус"]}'
            else:
                result = f'{full_name} – {row["Статус"]}'
            await update.message.reply_text(result, reply_markup=main_keyboard)
            return CHOOSING

    await update.message.reply_text("🚫 Працівника не знайдено", reply_markup=main_keyboard)
    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 Скасовано. Оберіть дію:", reply_markup=main_keyboard)
    return CHOOSING

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❗ Не розпізнано. Оберіть дію з меню:", reply_markup=main_keyboard)
    return CHOOSING

# --- Main ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("Telegram_Token")).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex("^(➕ Додати працівника)$"), start_add),
                MessageHandler(filters.Regex("^(📋 Перевірити статус)$"), start_check),
                MessageHandler(filters.Regex("^(❌ Скасувати)$"), cancel)
            ],
            ENTER_NAME: [
                MessageHandler(filters.Regex("^(❌ Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)
            ],
            ENTER_IPN: [
                MessageHandler(filters.Regex("^(❌ Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ipn)
            ],
            CHECK_STATUS: [
                MessageHandler(filters.Regex("^(❌ Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_ipn)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel)
        ],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.run_polling()