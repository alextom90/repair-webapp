import json
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# Стан діалогу
TYPE = 0
ISSUE = 1
NAME = 2
PHONE = 3
CHECK_STATUS = 4

# Файл даних
DATA_FILE = "clients.json"
ADMIN_ID = 123456789  # 🔒 заміни на свій Telegram ID

# Загрузка/збереження клієнтів
def load_clients():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_clients(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Ініціалізація клієнтів
clients = load_clients()

# Старт діалогу
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Я бот сервісу ремонту техніки. Обери тип пристрою:",
        reply_markup=ReplyKeyboardMarkup(
            [["Смартфон", "Ноутбук"], ["ПК", "Інше"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return TYPE

async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["type"] = update.message.text
    await update.message.reply_text("Яка проблема з пристроєм?")
    return ISSUE

async def get_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["issue"] = update.message.text
    await update.message.reply_text("Введіть ваше ім’я:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Номер телефону:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    context.user_data["status"] = "Прийнято"
    
    user_id = update.message.from_user.id
    clients[user_id] = context.user_data
    save_clients(clients)

    order_id = f"ORD{user_id}"
    await update.message.reply_text(
        f"Дякуємо, {context.user_data['name']}! Ваш код замовлення: {order_id}"
    )

    return ConversationHandler.END

# Перевірка статусу
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть код замовлення (наприклад, ORD123456):")
    return CHECK_STATUS

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    if not code.startswith("ORD") or not code[3:].isdigit():
        await update.message.reply_text("Невірний формат коду. Спробуйте ще раз.")
        return CHECK_STATUS

    user_id = int(code[3:])
    data = clients.get(user_id)

    if data:
        await update.message.reply_text(
            f"🔧 Статус: {data.get('status', 'Невідомо')}\n"
            f"📱 Тип: {data['type']}\n"
            f"⚠️ Проблема: {data['issue']}"
        )
    else:
        await update.message.reply_text("❌ Замовлення не знайдено.")
    return ConversationHandler.END

# Команда /admin для перегляду всіх замовлень
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ заборонено.")
        return

    clients_data = load_clients()
    if not clients_data:
        await update.message.reply_text("Немає замовлень.")
        return

    response = "📋 Список замовлень:\n"
    for uid, info in clients_data.items():
        response += (
            f"\n🆔 {uid} | {info['name']}\n"
            f"📱 {info['type']}, ⚠️ {info['issue']}\n"
            f"📞 {info['phone']}, 🛠 {info.get('status', 'Невідомо')}\n"
        )
    await update.message.reply_text(response)

# Команда скасування
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операцію скасовано.")
    return ConversationHandler.END

# Створення застосунку
app = ApplicationBuilder().token("7715128894:AAFaA0ZGlroyEDkZAB13iEvpGhoIqk8mqk4").build()

# Оформлення замовлення
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_type)],
        ISSUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_issue)],
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# Перевірка статусу
status_conv = ConversationHandler(
    entry_points=[CommandHandler("status", status)],
    states={
        CHECK_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_status)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# Реєстрація хендлерів
app.add_handler(conv_handler)
app.add_handler(status_conv)
app.add_handler(CommandHandler("admin", admin))

# Запуск бота
app.run_polling()