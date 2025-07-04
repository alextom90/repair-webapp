import json
import os
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# Стани діалогу
TYPE, ISSUE, NAME, PHONE, CHECK_STATUS, ADMIN_ACTION, ADMIN_UPDATE_STATUS = range(7)

# Файли даних
DATA_FILE = "clients.json"
LOG_FILE = "bot_log.txt"
ADMIN_IDS = [630776286]  # 🔒 Замінити на реальні ID адміністраторів

# Завантаження/збереження даних
def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def log_action(action, user_id=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] UserID: {user_id} - {action}\n")

# Ініціалізація даних
clients = load_data(DATA_FILE)

# Валідація телефонного номеру
def validate_phone(phone):
    phone = re.sub(r"[^\d+]", "", phone)
    return len(phone) >= 10 and phone.startswith(("+", "0"))

# Генерація ID замовлення
def generate_order_id(user_id):
    return f"ORD{user_id}_{datetime.now().strftime('%Y%m%d%H%M')}"

# Старт діалогу
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_action(f"Started conversation", user.id)
    
    await update.message.reply_text(
        "🔧 Привіт! Я бот сервісу ремонту техніки.\n"
        "Оберіть тип пристрою:",
        reply_markup=ReplyKeyboardMarkup(
            [["📱 Смартфон", "💻 Ноутбук"], ["🖥️ ПК", "⌚ Інше"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return TYPE

async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["type"] = update.message.text
    await update.message.reply_text(
        "Опишіть проблему з пристроем:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ISSUE

async def get_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["issue"] = update.message.text
    await update.message.reply_text("Введіть ваше ім'я:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Введіть номер телефону для зв'язку (формат: +380XXXXXXXXX або 0XXXXXXXXX):"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    if not validate_phone(phone):
        await update.message.reply_text("❌ Невірний формат телефону. Спробуйте ще раз:")
        return PHONE
    
    context.user_data["phone"] = phone
    context.user_data["status"] = "🟡 Прийнято"
    context.user_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    user_id = update.message.from_user.id
    order_id = generate_order_id(user_id)
    context.user_data["order_id"] = order_id
    
    clients[user_id] = context.user_data
    save_data(clients, DATA_FILE)
    
    log_action(f"Created order: {order_id}", user_id)
    
    await update.message.reply_text(
        f"✅ Дякуємо, {context.user_data['name']}!\n"
        f"Ваше замовлення прийнято.\n\n"
        f"📋 Деталі замовлення:\n"
        f"🆔 Код: {order_id}\n"
        f"📱 Пристрій: {context.user_data['type']}\n"
        f"⚠️ Проблема: {context.user_data['issue']}\n\n"
        f"Ви можете перевірити статус за допомогою команди /status"
    )
    
    # Повідомлення адміністратору
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"📌 Нове замовлення!\n"
                f"🆔 {order_id}\n"
                f"👤 {context.user_data['name']}\n"
                f"📞 {phone}\n"
                f"📱 {context.user_data['type']}\n"
                f"⚠️ {context.user_data['issue']}"
            )
        except Exception as e:
            log_action(f"Failed to notify admin {admin_id}: {str(e)}", user_id)
    
    return ConversationHandler.END

# Перевірка статусу
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    log_action("Checking status", user.id)
    
    # Перевірка чи є замовлення у цього користувача
    user_data = clients.get(user.id)
    if user_data:
        await update.message.reply_text(
            f"🔍 Ваше замовлення:\n"
            f"🆔 Код: {user_data['order_id']}\n"
            f"📱 Пристрій: {user_data['type']}\n"
            f"⚠️ Проблема: {user_data['issue']}\n"
            f"🛠 Статус: {user_data['status']}\n"
            f"📅 Дата: {user_data['timestamp']}"
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Введіть код вашого замовлення (наприклад, ORD123456_20240101):"
        )
        return CHECK_STATUS

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    if not re.match(r"ORD\d+_\d{12}", code):
        await update.message.reply_text("❌ Невірний формат коду. Спробуйте ще раз.")
        return CHECK_STATUS

    # Пошук замовлення за кодом
    found = False
    for user_id, data in clients.items():
        if data.get("order_id") == code:
            await update.message.reply_text(
                f"🔍 Результат пошуку:\n"
                f"🆔 Код: {code}\n"
                f"👤 Ім'я: {data['name']}\n"
                f"📱 Пристрій: {data['type']}\n"
                f"⚠️ Проблема: {data['issue']}\n"
                f"🛠 Статус: {data['status']}\n"
                f"📅 Дата: {data['timestamp']}"
            )
            found = True
            break
    
    if not found:
        await update.message.reply_text("❌ Замовлення не знайдено.")
    
    return ConversationHandler.END

# Адмін-панель
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ заборонено.")
        log_action("Unauthorized admin access attempt", user.id)
        return
    
    log_action("Admin panel accessed", user.id)
    
    await update.message.reply_text(
        "🔐 Адмін-панель\n"
        "Оберіть дію:",
        reply_markup=ReplyKeyboardMarkup(
            [["📊 Статистика", "📋 Список замовлень"], ["🔄 Оновити статус", "📤 Експорт даних"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return ADMIN_ACTION

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = update.message.text
    user = update.message.from_user
    
    if action == "📊 Статистика":
        total = len(clients)
        statuses = {}
        for data in clients.values():
            statuses[data.get("status", "Невідомо")] = statuses.get(data.get("status", "Невідомо"), 0) + 1
        
        stats = "\n".join([f"{k}: {v}" for k, v in statuses.items()])
        await update.message.reply_text(
            f"📊 Статистика:\n"
            f"📌 Всього замовлень: {total}\n"
            f"📈 По статусам:\n{stats}"
        )
        return ConversationHandler.END
    
    elif action == "📋 Список замовлень":
        if not clients:
            await update.message.reply_text("📭 Немає замовлень.")
            return ConversationHandler.END
        
        response = "📋 Останні 10 замовлень:\n"
        for i, (uid, data) in enumerate(list(clients.items())[-10:], 1):
            response += (
                f"\n{i}. 🆔 {data.get('order_id', 'N/A')}\n"
                f"👤 {data['name']}, 📞 {data['phone']}\n"
                f"📱 {data['type']}, ⚠️ {data['issue']}\n"
                f"🛠 {data.get('status', 'Невідомо')}, 📅 {data.get('timestamp', 'N/A')}\n"
            )
        
        await update.message.reply_text(response)
        return ConversationHandler.END
    
    elif action == "🔄 Оновити статус":
        await update.message.reply_text(
            "Введіть код замовлення для оновлення статусу:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADMIN_UPDATE_STATUS
    
    elif action == "📤 Експорт даних":
        if not clients:
            await update.message.reply_text("📭 Немає даних для експорту.")
            return ConversationHandler.END
        
        try:
            with open("orders_export.json", "w", encoding="utf-8") as f:
                json.dump(clients, f, ensure_ascii=False, indent=2)
            
            await update.message.reply_document(
                document=open("orders_export.json", "rb"),
                filename=f"orders_export_{datetime.now().strftime('%Y%m%d')}.json"
            )
            log_action("Exported data", user.id)
        except Exception as e:
            await update.message.reply_text(f"❌ Помилка при експорті: {str(e)}")
            log_action(f"Export failed: {str(e)}", user.id)
        
        return ConversationHandler.END
    
    else:
        await update.message.reply_text("Невідома команда.")
        return ConversationHandler.END

async def admin_update_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    found = False
    
    for user_id, data in clients.items():
        if data.get("order_id") == code:
            context.user_data["edit_order"] = code
            await update.message.reply_text(
                f"Знайдено замовлення:\n"
                f"👤 {data['name']}\n"
                f"📱 {data['type']}\n"
                f"⚠️ {data['issue']}\n"
                f"Поточний статус: {data.get('status', 'Невідомо')}\n\n"
                "Введіть новий статус:",
                reply_markup=ReplyKeyboardMarkup(
                    [["🟡 Прийнято", "🟠 В роботі"], ["🟢 Виконано", "🔴 Скасовано"]],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
            found = True
            break
    
    if not found:
        await update.message.reply_text("❌ Замовлення не знайдено.")
        return ConversationHandler.END
    
    return ADMIN_UPDATE_STATUS

async def save_updated_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_status = update.message.text
    order_code = context.user_data["edit_order"]
    
    for user_id, data in clients.items():
        if data.get("order_id") == order_code:
            old_status = data.get("status", "Невідомо")
            data["status"] = new_status
            save_data(clients, DATA_FILE)
            
            await update.message.reply_text(
                f"✅ Статус замовлення {order_code} змінено:\n"
                f"З {old_status} на {new_status}",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Сповіщення клієнта про зміну статусу
            try:
                await context.bot.send_message(
                    user_id,
                    f"ℹ️ Статус вашого замовлення оновлено:\n"
                    f"🆔 {order_code}\n"
                    f"🛠 Новий статус: {new_status}"
                )
                log_action(f"Updated status for {order_code} to {new_status}", update.message.from_user.id)
            except Exception as e:
                log_action(f"Failed to notify user {user_id}: {str(e)}", update.message.from_user.id)
            
            break
    
    return ConversationHandler.END

# Скасування діалогу
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Операцію скасовано.",
        reply_markup=ReplyKeyboardRemove()
    )
    log_action("Conversation canceled", update.message.from_user.id)
    return ConversationHandler.END

# Обробка помилок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user if update.message else None
    user_id = user.id if user else "unknown"
    log_action(f"Error: {context.error}", user_id)
    
    try:
        await update.message.reply_text(
            "❌ Сталася помилка. Будь ласка, спробуйте пізніше або зверніться до адміністратора."
        )
    except:
        pass

# Головна функція
def main():
    # Створення застосунку
    app = ApplicationBuilder().token("7715128894:AAFaA0ZGlroyEDkZAB13iEvpGhoIqk8mqk4").build()
    
    # Додавання обробників
    # Основний діалог замовлення
    order_conv = ConversationHandler(
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
    
    # Адмін-панель
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin)],
        states={
            ADMIN_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_action)],
            ADMIN_UPDATE_STATUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_update_status),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_updated_status),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Реєстрація обробників
    app.add_handler(order_conv)
    app.add_handler(status_conv)
    app.add_handler(admin_conv)
    app.add_error_handler(error_handler)
    
    # Запуск бота
    log_action("Bot started", "system")
    app.run_polling()

if __name__ == "__main__":
    main()