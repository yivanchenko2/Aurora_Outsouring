from telegram import ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, filters
from bot import CHOOSING, get_main_keyboard, sheet
from datetime import datetime, timedelta

# --- Стани для аналітики ---
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

def parse_date_input(text):
    text = text.strip().replace("/", ".")
    try:
        return datetime.strptime(text, "%d.%m.%y")
    except ValueError:
        return None

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

async def ask_period_start(update, context):
    await update.message.reply_text("🗓 Введіть початкову дату у форматі дд.мм.рр:")
    return STATISTICS_PERIOD_START

async def ask_period_end(update, context):
    try:
        start_date = datetime.strptime(update.message.text.strip(), "%d.%m.%y")
        context.user_data["stat_start"] = start_date
    except:
        await update.message.reply_text("❌ Невірний формат. Спробуйте ще раз:")
        return STATISTICS_PERIOD_START

    await update.message.reply_text("📆 Тепер введіть кінцеву дату у форматі дд.мм.рр:")
    return STATISTICS_PERIOD_END

async def show_statistics_period(update, context):
    try:
        end_date = datetime.strptime(update.message.text.strip(), "%d.%m.%y")
        start_date = context.user_data.get("stat_start")
        if not start_date:
            raise ValueError("Немає початкової дати")

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
                    if "✅ погоджено" in status:
                        positive += 1
                    elif "❌ не погоджено" in status:
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
        await update.message.reply_text("⚠️ Помилка обробки. Переконайтесь, що дати у форматі дд.мм.рр.")
        return STATISTICS_MENU

    return await analytics_back(update, context)

async def show_standard_statistics(update, context):
    today = datetime.today()
    weekday = today.weekday()

    if weekday == 0:
        yesterday = today - timedelta(days=3)
    elif weekday == 6:
        yesterday = today - timedelta(days=2)
    else:
        yesterday = today - timedelta(days=1)

    def get_stats_for_check_date(date_obj):
        formatted = date_obj.strftime("%d.%m.%y")
        total = checked = approved = rejected = 0
        try:
            records = sheet.get_all_records()
            for row in records:
                check_date = row.get("Дата перевірки", "").strip()
                if check_date == formatted:
                    checked += 1
                    status = row.get("Статус", "").strip()
                    if status == "✅ Погоджено":
                        approved += 1
                    elif status == "❌ Не погоджено":
                        rejected += 1
        except Exception as e:
            print(f"Помилка читання: {e}")
        return total, formatted, checked, approved, rejected

    def get_submitted_for_date(date_obj):
        formatted = date_obj.strftime("%d.%m.%y")
        try:
            return sum(1 for row in sheet.get_all_records() if row.get("Дата", "").strip() == formatted)
        except:
            return 0

    def count_pending():
        try:
            return sum(1 for row in sheet.get_all_records() if row.get("Статус", "").strip() == "Очікує погодження")
        except:
            return 0

    t_total, t_formatted, t_checked, t_approved, t_rejected = get_stats_for_check_date(today)
    y_total, y_formatted, y_checked, y_approved, y_rejected = get_stats_for_check_date(yesterday)

    t_submitted = get_submitted_for_date(today)
    y_submitted = get_submitted_for_date(yesterday)
    pending_total = count_pending()

    text = (
        f"📆 *Статистика за сьогодні* ({t_formatted}):\n"
        f"• Подано: {t_submitted}\n"
        f"• Перевірено: {t_checked}\n"
        f"• ✅ Погоджено: {t_approved}\n"
        f"• ❌ Не погоджено: {t_rejected}\n\n"
        f"📅 *Статистика за вчора* ({y_formatted}):\n"
        f"• Подано: {y_submitted}\n"
        f"• Перевірено: {y_checked}\n"
        f"• ✅ Погоджено: {y_approved}\n"
        f"• ❌ Не погоджено: {y_rejected}\n\n"
        f"⏳ *Очікує погодження зараз:* {pending_total}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")
    return STATISTICS_MENU

async def show_overall_statistics(update,context):
    try:
        records = sheet.get_all_records()
        submitted = checked = approved = rejected = 0

        for row in records:
            submitted += 1
            status = row.get("Статус","").strip().lower()
            if row.get("Дата перевірки","").strip():
                checked += 1
                if status == "✅ Погоджено":
                    approved += 1
                elif status == "❌ Не погоджено":
                    rejected += 1

        text = (
            f"📈 *Загальна статистика за весь період*\n\n"
            f"🔹 Подано: *{submitted}*\n"
            f"🔸 Перевірено: *{checked}*\n"
            f"✅ Погоджено: *{approved}*\n"
            f"❌ Не погоджено: *{rejected}*"
        )
        await update.message.reply_text(text,parse_mode = "Markdown")
    except Exception as e:
        await update.message.reply_text("⚠️ Помилка при зчитуванні таблиці.")
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
        STATISTICS_MENU: [
            MessageHandler(filters.Regex("^📅 За період$"), ask_period_start),
            MessageHandler(filters.Regex("^📆 Стандарт$"), show_standard_statistics),
            MessageHandler(filters.Regex("^📈 Загальна статистика$"),show_overall_statistics),
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
