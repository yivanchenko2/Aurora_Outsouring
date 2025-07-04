import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta
import json
from io import StringIO

logging.basicConfig(level=logging.INFO)

# --- CONSTANTS ---
CHOOSING, ENTER_NAME, ENTER_IPN, CHECK_STATUS = range(4)

# --- KEYBOARDS ---
main_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("➕ Додати працівника", callback_data="add_employee")],
    [InlineKeyboardButton("📋 Перевірити статус", callback_data="check_status")]
])

cancel_keyboard = ReplyKeyboardMarkup([[KeyboardButton("❌ Скасувати")]], resize_keyboard=True)

# --- GOOGLE SHEET SETUP ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_CREDS_JSON")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Aurora Outsourcing").sheet1

# --- HELPERS ---
def proper_case(text):
    return " ".join([w.capitalize() for w in text.split()])

def is_valid_ipn(text):
    return text.isdigit() and len(text) == 10

def calculate_birthdate():
    today = date.today()
    birthdate = today - timedelta(days=(18 * 365 + 4))  # 18 років з поправкою
    return birthdate.strftime("%d.%m.%Y")

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт! Обери дію:", reply_markup=main_keyboard
    )
    return CHOOSING

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_employee":
        await query.edit_message_text("Введіть ПІБ працівника:")
        return ENTER_NAME

    elif query.data == "check_status":
        await query.edit_message_text("🧾 Введіть ІПН працівника:")
        return CHECK_STATUS

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name_raw = update.message.text.strip()
    if name_raw.lower() == "скасувати":
        return await cancel(update, context)

    name = proper_case(name_raw)
    parts = name.split()

    if len(parts) != 3:
        await update.message.reply_text("❗ Введіть ПІБ у форматі: Прізвище Ім’я По-батькові")
        return ENTER_NAME

    context.user_data["name_parts"] = parts
    await update.message.reply_text("🔢 Введіть ІПН:", reply_markup=cancel_keyboard)
    return ENTER_IPN

async def enter_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ipn = update.message.text.strip()

    if ipn.lower() == "скасувати":
        return await cancel(update, context)

    if not is_valid_ipn(ipn):
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр.\n🔁 Введіть ІПН ще раз:")
        return ENTER_IPN

    surname, name, middlename = context.user_data["name_parts"]
    birthdate = calculate_birthdate()

    sheet.append_row([
        surname, name, middlename, birthdate, ipn, "Очікує погодження", "", ""
    ])

    await update.message.reply_text("✅ Дані працівника збережено!", reply_markup=main_keyboard)
    return CHOOSING

async def check_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ipn = update.message.text.strip()

    if ipn.lower() == "скасувати":
        return await cancel(update, context)

    if not is_valid_ipn(ipn):
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр.\n🔁 Спробуйте ще раз:")
        return CHECK_STATUS

    data = sheet.get_all_records()
    for row in data:
        if str(row["ІПН"]) == ipn:
            result = f'{row["Імя"]} {row["По батькові"]} – {row["Статус"]}'
            await update.message.reply_text(result, reply_markup=main_keyboard)
            return CHOOSING

    await update.message.reply_text("🚫 Працівника не знайдено", reply_markup=main_keyboard)
    return CHOOSING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔙 Повертаємось в головне меню", reply_markup=main_keyboard)
    return CHOOSING

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Не розумію... Виберіть опцію з меню ⬇️")
    return CHOOSING

# --- MAIN ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(button_click)
            ],
            ENTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)
            ],
            ENTER_IPN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ipn)
            ],
            CHECK_STATUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_ipn)
            ]
        },
        fallbacks=[MessageHandler(filters.TEXT, fallback)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.run_polling()
