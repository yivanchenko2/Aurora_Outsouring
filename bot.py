from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- Google Sheets Setup ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)

# 🔽 ВАЖЛИВО: назва таблиці має бути точно такою, як у Google Sheets!
sheet = client.open("Перевірка аутсорс").sheet1  # ← Заміни назву, якщо у тебе інша

# --- Стан введення ---
NAME, ITN, CHECK_ITN = range(3)

# --- Клавіатури ---
main_keyboard = ReplyKeyboardMarkup(
    [["Додати працівника", "Перевірити статус"]],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup([["Скасувати"]], resize_keyboard=True)

# --- Розрахунок дати народження ---
def calculate_birthdate_from_itn(itn: str) -> str:
    try:
        days = int(itn[:5])
        base_date = datetime(1900, 1, 1)
        birthdate = base_date + timedelta(days=days - 1)
        return birthdate.strftime("%d.%m.%Y")
    except:
        return ""

# --- /start команда ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Оберіть дію:", reply_markup=main_keyboard)

# --- Обробка вибору з меню ---
async def handle_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Додати працівника":
        await update.message.reply_text("Введіть ПІБ працівника:", reply_markup=cancel_keyboard)
        return NAME
    elif text == "Перевірити статус":
        await update.message.reply_text("Введіть ІПН працівника:", reply_markup=cancel_keyboard)
        return CHECK_ITN
    else:
        await update.message.reply_text("Будь ласка, скористайтесь кнопками нижче ⬇️", reply_markup=main_keyboard)
        return ConversationHandler.END

# --- Додавання працівника ---
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    parts = full_name.split()

    if len(parts) != 3:
        await update.message.reply_text("❌ Введіть ПІБ у форматі: Прізвище Ім’я По батькові (три слова)")
        await update.message.reply_text("🔄 Наприклад: Іваненко Юрій Юрійович", reply_markup=cancel_keyboard)
        return NAME

    # 🔧 Автокорекція: кожне слово — з великої літери
    surname = parts[0].capitalize()
    name = parts[1].capitalize()
    patronymic = parts[2].capitalize()

    context.user_data["surname"] = surname
    context.user_data["name"] = name
    context.user_data["patronymic"] = patronymic

    await update.message.reply_text(
        f"Прийнято: {surname} {name} {patronymic}",
        reply_markup=cancel_keyboard
    )
    await update.message.reply_text("Введіть ІПН:")
    return ITN


async def get_itn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    itn = update.message.text.strip()

    if not itn.isdigit() or len(itn) != 10:
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр.")
        await update.message.reply_text("🔄 Введіть ІПН ще раз:", reply_markup=cancel_keyboard)
        return ITN

    context.user_data["itn"] = itn

    birthdate = calculate_birthdate_from_itn(itn)

    # 🔽 Формуємо рядок з пустим значенням для дати народження (колонка №4)
    values = [[
        "",
        context.user_data["surname"],   # A – Прізвище
        context.user_data["name"],      # B – Ім’я
        context.user_data["patronymic"],# C – По батькові
        birthdate,                              # D – Дата народження (залишається формула)
        context.user_data["itn"],       # E – ІПН
        "Очікує погодження"              # F – Статус
    ]]

    sheet.append_rows(values, value_input_option="USER_ENTERED")

    await update.message.reply_text("✅ Дані працівника збережено!", reply_markup=main_keyboard)
    return ConversationHandler.END


# --- Перевірка статусу ---
async def check_itn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    itn = update.message.text.strip()

    if not itn.isdigit() or len(itn) != 10:
        await update.message.reply_text("❌ ІПН має містити рівно 10 цифр.")
        await update.message.reply_text("🔄 Введіть ІПН ще раз:", reply_markup=cancel_keyboard)
        return CHECK_ITN

    records = sheet.get_all_records()
    for record in records:
        if str(record["ІПН"]) == itn:
            # 🔽 Формуємо відповідь: лише Ім’я + По батькові + Статус
            first_name = record.get("Імя", "")
            patronymic = record.get("По батькові", "")
            status = record.get("Статус", "Невідомо")

            msg = f"{first_name} {patronymic} – {status}"
            await update.message.reply_text(msg, reply_markup=main_keyboard)
            return ConversationHandler.END

    await update.message.reply_text("Працівника не знайдено.", reply_markup=main_keyboard)
    return ConversationHandler.END


# --- Скасування ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Операцію скасовано.",
        reply_markup=main_keyboard  # ← Повертаємо головне меню
    )
    return ConversationHandler.END

# --- Основний запуск ---
if __name__ == '__main__':
    app = ApplicationBuilder().token("8098286591:AAG2XUsSdmvmKDfIR3Ff6Vwn3CfqeFZABfo").build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_choice)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ITN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_itn)],
            CHECK_ITN: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_itn)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^Скасувати$"), cancel)
        ]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    app.run_polling()
