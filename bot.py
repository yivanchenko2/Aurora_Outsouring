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


# ====== ПАРОЛІ ДОСТУПУ ======
SECURITY_PASSWORD = "secr5541"
RETAIL_PASSWORD = "retl4478"

# Logging
logging.basicConfig(level=logging.INFO)

# ====== СТАНИ ======
SELECT_DIRECTION, ASK_PASSWORD, ASK_COMPANY, CHOOSING, ENTER_NAME, ENTER_IPN, CHECK_STATUS = range(7)

# ====== КЛАВІАТУРИ ======
direction_keyboard = ReplyKeyboardMarkup([
    ["🏬 Магазини / Логістика"],
    ["🛡 Охорона"]
], resize_keyboard=True)

cancel_keyboard = ReplyKeyboardMarkup([
    ["❌ Скасувати"]
], resize_keyboard=True)


def get_main_keyboard(mode: str):
    return ReplyKeyboardMarkup([
        ["➕ Додати працівника", "📋 Перевірити статус"],
        ["📊 Аналітика"],
        ["⬅️ Змінити напрямок"]
    ], resize_keyboard=True)


# ====== GOOGLE SHEETS ======
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.getenv("Google_Creds_Json"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

HEADERS = ["Дата", "ПІБ", "Дата народження", "ІПН", "Статус", "Перевіряючий", "Коментар"]


def get_sheet(context):
    """Повертає відповідний лист залежно від режиму."""
    mode = context.user_data.get("mode", "retail")
    book = client.open("Перевірка аутсорс")
    if mode == "security":
        return book.worksheet("Охорона")
    return book.worksheet("Кандидати")


# ====== UTILS ======
def is_valid_ipn(text: str) -> bool:
    return text.isdigit() and len(text) == 10


def proper_case(text: str) -> str:
    return " ".join([w.capitalize() for w in text.split()])


def calculate_birthdate(ipn: str) -> str:
    try:
        base = date(1900, 1, 1)
        return (base + timedelta(days=int(ipn[:5]) - 1)).strftime("%d.%m.%Y")
    except Exception:
        return ""


def normalize_ipn(ipn: str) -> str:
    return str(ipn).strip().zfill(10)


def is_cancel(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in ["❌ скасувати", "скасувати"]


# ====== HANDLERS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Вітаю!* \n\n"
        "Цей бот створений командою Аврора для перевірки працівників аутсорсу.\n\n"
        "Перед початком роботи вам треба обрати ваш напрямок, за яким ви надаєте послуги аутсорсу та "
        "ввести пароль, наданий командою Аврори відповідно до напрямку.\n\n"
        "\nЯкщо ви хочете додати працівника на перевірку, натисність:\n"
        "========================================================\n"
        "                                       ➕ Додати працівника\n"
        "========================================================"
        "\nЯкщо ви хочете перевірити чи погоджений/не погоджений працівник, натисніть:\n"
        "========================================================\n"
        "                                        📋 Перевірити статус\n"
        "========================================================"
        "Можна здійснювати перевірку більше одного працівника."
        " Для цього внесіть ІПН декількох працівників через пробіл або в стовпчик."
        "\n\nЯкщо у ІПН переплутані цифри, то працівник *перевірятися не буде* та вам у телеграм прийде сповіщення у форматі:"
        "\nПІБ - *Очікує погодження*"
        "\nКоментар: _Невірний ІПН_"
        "\nЩоб виправити - треба знову надіслати працівника на перевірку.\n"
        "\n*Важливо*. Перевірка працівників здійснюється *до 24 годин*.\n"
        "*Субота та неділя - не робочі дні*, тому якщо ви надіслали працівника на перевірку у п'ятницю, результат буде у цей же день, або у понеділок.\n\n"
        "*Бажаємо гарного дня!*",
        parse_mode="Markdown"
    )
    await update.message.reply_text(
        "👋 Оберіть напрямок, з яким хочете працювати:",
        reply_markup=direction_keyboard
    )
    return SELECT_DIRECTION


async def select_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if is_cancel(text):
        return await cancel(update, context)

    if "Магазин" in text:
        context.user_data["requested_mode"] = "retail"
    elif "Охорона" in text:
        context.user_data["requested_mode"] = "security"
    else:
        await update.message.reply_text("❌ Невірний вибір. Спробуйте ще раз.")
        return SELECT_DIRECTION

    await update.message.reply_text("🔐 Введіть пароль доступу:", reply_markup=cancel_keyboard)
    return ASK_PASSWORD


async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()

    if is_cancel(password):
        return await cancel(update, context)

    requested = context.user_data.get("requested_mode")

    if requested == "security" and password == SECURITY_PASSWORD:
        context.user_data["mode"] = "security"

        # якщо компанію ще не вводили — запитуємо
        if not context.user_data.get("company"):
            await update.message.reply_text(
                "🏢 Введіть назву компанії, наприклад: *ОХОРОНА*:",
                reply_markup=cancel_keyboard,
                parse_mode="Markdown"
            )
            return ASK_COMPANY

    elif requested == "retail" and password == RETAIL_PASSWORD:
        context.user_data["mode"] = "retail"
    else:
        await update.message.reply_text("❌ Невірний пароль. Спробуйте ще раз:", reply_markup=cancel_keyboard)
        return ASK_PASSWORD

    await update.message.reply_text(
        f"✅ Доступ надано: {'Охорона' if requested == 'security' else 'Магазини / Логістика'}",
        reply_markup=get_main_keyboard(requested)
    )
    return CHOOSING


async def save_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if is_cancel(text):
        return await cancel(update, context)

    if len(text) < 2:
        await update.message.reply_text("❌ Назва компанії занадто коротка. Спробуйте ще раз:")
        return ASK_COMPANY

    context.user_data["company"] = text
    mode = context.user_data.get("mode", "security")

    await update.message.reply_text(
        f"✅ Компанію збережено: *{text}*",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(mode)
    )
    return CHOOSING


async def change_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔁 Оберіть напрямок:", reply_markup=direction_keyboard)
    return SELECT_DIRECTION


# ====== ДОДАВАННЯ ПРАЦІВНИКА ======
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✍️ Введіть ПІБ працівника:", reply_markup=cancel_keyboard)
    return ENTER_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if is_cancel(text):
        return await cancel(update, context)

    if len(text.split()) < 2:
        await update.message.reply_text("❗ Формат: Прізвище Ім’я По-батькові")
        return ENTER_NAME

    context.user_data["pib"] = proper_case(text)
    await update.message.reply_text("🔢 Введіть ІПН (10 цифр):", reply_markup=cancel_keyboard)
    return ENTER_IPN


async def enter_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet(context)
    text = update.message.text.strip()

    if is_cancel(text):
        return await cancel(update, context)

    if not is_valid_ipn(text):
        await update.message.reply_text("❌ ІПН має містити 10 цифр.")
        return ENTER_IPN

    ipn = text

    # перевірка на дубль
    data = sheet.get_all_records(expected_headers=HEADERS)
    for row in data:
        if normalize_ipn(row.get("ІПН")) == normalize_ipn(ipn):
            await update.message.reply_text(
                "🚫 Працівник вже існує.",
                reply_markup=get_main_keyboard(context.user_data.get("mode", "retail"))
            )
            return CHOOSING

    birthdate = calculate_birthdate(ipn)
    current_date = datetime.today().strftime("%d.%m.%y")

    mode = context.user_data.get("mode", "retail")
    company = context.user_data.get("company", "") if mode == "security" else ""

    # *** ГОЛОВНА ЗМІНА ***
    # Для охорони: A..I = Дата, ПІБ, ДН, ІПН, Статус, Дата перевірки, Перевіряючий, Коментар, Компанія
    # Для магазинів: A..G = Дата, ПІБ, ДН, ІПН, Статус, Перевіряючий, Коментар
    if mode == "security":
        new_row = [
            current_date,               # A Дата
            context.user_data["pib"],   # B ПІБ
            birthdate,                  # C Дата народження
            ipn,                        # D ІПН
            "Очікує погодження",        # E Статус
            "",                         # F Дата перевірки
            "",                         # G Перевіряючий
            "",                         # H Коментар
            company                     # I Компанія (останній стовпець)
        ]
    else:
        new_row = [
            current_date,               # A Дата
            context.user_data["pib"],   # B ПІБ
            birthdate,                  # C Дата народження
            ipn,                        # D ІПН
            "Очікує погодження",        # E Статус
            "",                         # F Перевіряючий
            ""                          # G Коментар
        ]

    sheet.append_row(new_row)

    await update.message.reply_text("✅ Працівника додано!", reply_markup=get_main_keyboard(mode))
    return CHOOSING


# ====== ПЕРЕВІРКА ======
async def start_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Введіть ІПН(и):", reply_markup=cancel_keyboard)
    return CHECK_STATUS


async def check_ipn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet(context)
    text = update.message.text.strip()

    if is_cancel(text):
        return await cancel(update, context)

    ipns = text.split()
    results = []

    rows = sheet.get_all_records()
    for ipn in ipns:
        found = False
        for row in rows:
            if str(row.get("ІПН", "")).zfill(10) == ipn:
                results.append(f"{ipn} – {row.get('ПІБ')} – {row.get('Статус')}")
                found = True
                break
        if not found:
            results.append(f"{ipn} – ❌ Не знайдено")

    mode = context.user_data.get("mode", "retail")
    await update.message.reply_text(
        "\n".join(results),
        reply_markup=get_main_keyboard(mode)
    )
    return CHOOSING


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # при скасуванні: якщо режим вже вибраний — повертаємо в головне меню,
    # інакше назад до вибору напрямку
    mode = context.user_data.get("mode")
    if mode:
        await update.message.reply_text("🔙 Скасовано.", reply_markup=get_main_keyboard(mode))
        return CHOOSING

    await update.message.reply_text("🔙 Скасовано. Оберіть напрямок:", reply_markup=direction_keyboard)
    return SELECT_DIRECTION


# ====== ЗАПУСК ======
if __name__ == "__main__":
    from analytics_menu import analytics_handlers

    app = ApplicationBuilder().token(os.getenv("Telegram_Token")).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_DIRECTION: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_direction),
            ],
            ASK_PASSWORD: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_password),
            ],
            ASK_COMPANY: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_company),
            ],
            CHOOSING: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.Regex("^➕ Додати працівника$"), start_add),
                MessageHandler(filters.Regex("^📋 Перевірити статус$"), start_check),
                MessageHandler(filters.Regex("^⬅️ Змінити напрямок$"), change_direction),
            ],
            ENTER_NAME: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name),
            ],
            ENTER_IPN: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_ipn),
            ],
            CHECK_STATUS: [
                MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_ipn),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^(❌ Скасувати|Скасувати)$"), cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    for handler in analytics_handlers:
        app.add_handler(handler)

    app.run_polling()
