from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, filters
from bot import CHOOSING, get_main_keyboard, get_sheet
from datetime import datetime, timedelta

# --- Стани ---
ANALYTICS_MENU, ANALYTICS_DATE_INPUT, STATISTICS_MENU, STATISTICS_PERIOD_START, STATISTICS_PERIOD_END, STATISTICS_STANDARD = range(100, 106)

analytics_keyboard = ReplyKeyboardMarkup([
    ["🔍 Перевірити за датою"],
    ["📊 Статистика"],
    ["⬅️ Назад"]
], resize_keyboard=True)

statistics_keyboard = ReplyKeyboardMarkup([
    ["📅 За період", "📆 Сьогодні/вчора"],
    ["📈 Загальна статистика"],
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
    if date_str.lower() in ["назад", "⬅️ назад"]:
        return await analytics_back(update, context)
    try:
        dt = datetime.strptime(date_str, "%d.%m.%y")
        formatted_date = dt.strftime("%d.%m.%y")
    except ValueError:
        await update.message.reply_text("❌ Невірний формат дати.")
        return ANALYTICS_DATE_INPUT

    try:
        sheet = get_sheet(context)
        records = sheet.get_all_records()
        results = [f"👤 {row.get('ПІБ')} – *{row.get('Статус')}*" for row in records if row.get("Дата") == formatted_date]
        if results:
            await update.message.reply_text("\n".join(results), parse_mode="Markdown")
        else:
            await update.message.reply_text("ℹ️ Працівників за цю дату не знайдено.")
    except Exception as e:
        await update.message.reply_text("⚠️ Помилка при зчитуванні таблиці.")
    return await analytics_back(update, context)

# === Обробник "📊 Статистика" ===
async def ask_statistics_type(update, context):
    await update.message.reply_text("📊 Оберіть тип статистики:", reply_markup=statistics_keyboard)
    return STATISTICS_MENU

async def ask_period_start(update, context):
    await update.message.reply_text("🗓 Введіть початкову дату у форматі дд.мм.рр:")
    return STATISTICS_PERIOD_START

async def ask_period_end(update, context):
    try:
        context.user_data["stat_start"] = datetime.strptime(update.message.text.strip(), "%d.%m.%y")
    except:
        await update.message.reply_text("❌ Невірний формат.")
        return STATISTICS_PERIOD_START
    await update.message.reply_text("📆 Тепер введіть кінцеву дату:")
    return STATISTICS_PERIOD_END

async def show_statistics_period(update, context):
    try:
        end_date = datetime.strptime(update.message.text.strip(), "%d.%m.%y")
        start_date = context.user_data.get("stat_start")
        if not start_date:
            raise ValueError("Немає початкової дати")

        sheet = get_sheet(context)
        records = sheet.get_all_records()
        submitted = checked = positive = negative = 0

        for row in records:
            row_date_str = row.get("Дата")
            try:
                row_date = datetime.strptime(row_date_str, "%d.%m.%y")
            except:
                continue

            if start_date <= row_date <= end_date:
                submitted += 1
                status = row.get("Статус", "").lower()
                if status != "очікує погодження":
                    checked += 1
                    if "погоджено" in status:
                        positive += 1
                    elif "не погоджено" in status:
                        negative += 1

        text = (
            f"📊 *Статистика з {start_date.strftime('%d.%m.%y')} по {end_date.strftime('%d.%m.%y')}*\n\n"
            f"🔹 Подано: *{submitted}*\n"
            f"🔸 Перевірено: *{checked}*\n"
            f"✅ Позитивних: *{positive}*\n"
            f"❌ Негативних: *{negative}*"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except:
        await update.message.reply_text("⚠️ Помилка. Перевірте формат дат.")
        return STATISTICS_MENU
    return await analytics_back(update, context)

async def show_standard_statistics(update, context):
    today = datetime.today()
    weekday = today.weekday()
    yesterday = today - timedelta(days=3 if weekday == 0 else 2 if weekday == 6 else 1)

    sheet = get_sheet(context)
    records = sheet.get_all_records()

    def get_stats_for_date(date_obj):
        formatted = date_obj.strftime("%d.%m.%y")
        submitted = sum(1 for row in records if row.get("Дата", "") == formatted)
        checked = sum(1 for row in records if row.get("Дата перевірки", "") == formatted)
        approved = sum(1 for row in records if row.get("Дата перевірки", "") == formatted and row.get("Статус") == "✅ Погоджено")
        rejected = sum(1 for row in records if row.get("Дата перевірки", "") == formatted and row.get("Статус") == "❌ Не погоджено")
        return formatted, submitted, checked, approved, rejected

    def count_pending():
        return sum(1 for row in records if row.get("Статус") == "Очікує погодження")

    t_fmt, t_sub, t_chk, t_app, t_rej = get_stats_for_date(today)
    y_fmt, y_sub, y_chk, y_app, y_rej = get_stats_for_date(yesterday)
    pending = count_pending()

    text = (
        f"📆 *Сьогодні* ({t_fmt}):\n"
        f"• Подано: {t_sub}\n• Перевірено: {t_chk}\n• ✅ Погоджено: {t_app}\n• ❌ Не погоджено: {t_rej}\n\n"
        f"📅 *Вчора* ({y_fmt}):\n"
        f"• Подано: {y_sub}\n• Перевірено: {y_chk}\n• ✅ Погоджено: {y_app}\n• ❌ Не погоджено: {y_rej}\n\n"
        f"⏳ *Очікує погодження:* {pending}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return STATISTICS_MENU

async def show_overall_statistics(update, context):
    try:
        sheet = get_sheet(context)
        records = sheet.get_all_records()
        submitted = len(records)
        checked = sum(1 for row in records if row.get("Дата перевірки", ""))
        approved = sum(1 for row in records if row.get("Статус") == "✅ Погоджено")
        rejected = sum(1 for row in records if row.get("Статус") == "❌ Не погоджено")

        text = (
            f"📈 *Загальна статистика*\n\n"
            f"🔹 Подано: *{submitted}*\n"
            f"🔸 Перевірено: *{checked}*\n"
            f"✅ Погоджено: *{approved}*\n"
            f"❌ Не погоджено: *{rejected}*"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except:
        await update.message.reply_text("⚠️ Помилка при зчитуванні.")
    return STATISTICS_MENU

async def analytics_back(update, context):
    keyboard = get_main_keyboard(context.user_data.get("mode"))
    await update.message.reply_text("🔙 Повернення назад...", reply_markup=keyboard)
    return CHOOSING

analytics_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^📊 Аналітика$"), show_analytics_menu)],
    states={
        ANALYTICS_MENU: [
            MessageHandler(filters.Regex("^🔍 Перевірити за датою$"), ask_analytics_date),
            MessageHandler(filters.Regex("^📊 Статистика$"), ask_statistics_type),
            MessageHandler(filters.Regex("^⬅️ Назад$"), analytics_back),
        ],
        ANALYTICS_DATE_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, show_employees_by_date)
        ],
        STATISTICS_MENU: [
            MessageHandler(filters.Regex("^📅 За період$"), ask_period_start),
            MessageHandler(filters.Regex("^📆 Сьогодні/вчора$"), show_standard_statistics),
            MessageHandler(filters.Regex("^📈 Загальна статистика$"), show_overall_statistics),
            MessageHandler(filters.Regex("^⬅️ Назад$"), analytics_back),
        ],
        STATISTICS_PERIOD_START: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_period_end),
        ],
        STATISTICS_PERIOD_END: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, show_statistics_period)
        ]
    },
    fallbacks=[MessageHandler(filters.Regex("^⬅️ Назад$"), analytics_back)],
    allow_reentry=True
)

analytics_handlers = [analytics_conv]
