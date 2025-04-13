from telegram.ext import Application, CommandHandler, MessageHandler, filters
from zadavalnik.database.db import add_session
from zadavalnik.ai.openai_client import OpenAIClient
# from zadavalnik.utils.helpers import get_current_time

def setup_handlers(app: Application):
    """
    Регистрирует обработчики команд и сообщений для Telegram-бота.
    """
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

async def start(update, context):
    """
    Обработчик команды /start: регистрирует сессию и отправляет приветствие.
    """
    user_id = update.effective_user.id
    add_session(user_id)
    await update.message.reply_text(
        "Добро пожаловать!"
    )

async def menu(update, context):
    """
    Обработчик команды /menu: отправляет список доступных команд.
    """
    await update.message.reply_text(
        "Доступные команды: /start - начать, /menu - меню"
    )

async def handle_text(update, context):
    """
    Обработчик текстовых сообщений: отправляет вопрос в OpenAI и возвращает ответ.
    """
    question = update.message.text
    # TODO: Создавать только одну сессию с LLM на всю тему
    client = OpenAIClient()
    response = client.ask(question)
    
    if response:
        await update.message.reply_text(response["message"])
    else:
        await update.message.reply_text("Ошибка, попробуйте позже")