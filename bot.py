import logging
import os
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          filters, ContextTypes, ConversationHandler)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, timedelta

# Логування
logging.basicConfig(level=logging.INFO)

# Стани розмови
ENTER_NAME, ENTER_IPN, CHECK_STATUS = range(3)

# Клавіатури
main_keyboard = ReplyKeyboardMarkup(
    [["➕ Додати працівника"], ["📋 Перевірити статус"]], resize_keyboard=True
)
cancel_keyboard = ReplyKeyboardMarkup(
    [["❌ Скасувати"]], resize_keyboard=True
)

# Авторизація Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.getenv("Google_Creds_Json"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Перевірка аутсорс").sheet1

# Автоформатування ПІБ
def format_name(full_name):
    return " ".join(word.capitalize() for word in full_name.strip().split())

# Витяг дати народження з ІПН
def get_birthdate_from_ipn(ipn: str) -> str:
    try:
        base_date = date(1900, 1, 1)
        days = int(ipn[:5])
        birthdate = base_date + timedelta(days=days)
        return birthdate.strftime("%d.%m.%Y")
    except:
        return ""

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Оберіть дію:", reply_markup=main_keyboard)

# Додавання працівника
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ Введіть ПІБ працівника:", reply_markup=cancel_keyboard)
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = format_name(update.message.text)
    parts = text.split()
    if len(parts) != 3:
        await update.message.reply_text("❗ Введіть ПІБ у форматі: Прізвище Імʼя По-батькові")
        return ENTER_NAME
    context.user_data["surname"] = parts[0]
    context.user_data["name"] = parts[1]
    context.user_data["patronymic"] = parts[2]
    await update.message.reply_text("🔢 Введіть ІПН працівника:")
    return ENTER_IPN

async def enter_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not (text.isdigit() and len(text) == 10):
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр.\n🔁 Введіть ІПН ще раз:")
        return ENTER_IPN

    birthdate = get_birthdate_from_ipn(text)
    sheet.append_row([
        "",  # Порожня клітинка для ручного введення дати
        context.user_data["surname"],
        context.user_data["name"],
        context.user_data["patronymic"],
        birthdate,
        text,
        "Очікує погодження",
        "",
        ""
    ])
    await update.message.reply_text("✅ Дані успішно додано!", reply_markup=main_keyboard)
    return ConversationHandler.END

# Перевірка статусу
async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Введіть ІПН працівника:", reply_markup=cancel_keyboard)
    return CHECK_STATUS

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ipn = update.message.text.strip()
    if not (ipn.isdigit() and len(ipn) == 10):
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр.\n🔁 Введіть ІПН ще раз:")
        return CHECK_STATUS

    data = sheet.get_all_records()
    for row in data:
        if str(row.get("ІПН")) == ipn:
            name = row.get("Імʼя", "")
            patronymic = row.get("По батькові", "")
            status = row.get("Статус", "Невідомо")
            await update.message.reply_text(f"👤 {name} {patronymic} – {status}", reply_markup=main_keyboard)
            return ConversationHandler.END

    await update.message.reply_text("❌ Працівника не знайдено.", reply_markup=main_keyboard)
    return ConversationHandler.END

# Скасування дій
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Дію скасовано.", reply_markup=main_keyboard)
    return ConversationHandler.END

# Основна функція
async def main():
    token = os.getenv("Telegram_Token")
    if not token:
        raise ValueError("❌ BOT_TOKEN не знайдено в середовищі!")

    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Додати працівника$"), start_add),
            MessageHandler(filters.Regex("^📋 Перевірити статус$"), start_check),
        ],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_IPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ipn)],
            CHECK_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_status)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Скасувати$"), cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())


