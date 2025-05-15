import asyncio
import logging
from telegram.ext import Application

from zadavalnik.config.settings import settings
from zadavalnik.database.db import init_db
from zadavalnik.ai.openai_client import OpenAIClient
from zadavalnik.bot.handlers import setup_handlers

# Настройка базового логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting bot...")

    # 1. Инициализация базы данных
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        return # Не запускаем бота, если БД не работает

    # 2. Инициализация клиента OpenAI
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set in environment variables or .env file.")
        return
    openai_client = OpenAIClient(api_key=settings.OPENAI_API_KEY, model_name=settings.OPENAI_MODEL)
    logger.info(f"OpenAI client initialized with model: {settings.OPENAI_MODEL}.")

    # 3. Создание Application
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables or .env file.")
        return
        
    application = Application.builder().token(settings.BOT_TOKEN).build()

    # 4. Сохраняем клиент OpenAI в bot_data для доступа из хендлеров
    application.bot_data['openai_client'] = openai_client
    # Сессии БД будут получаться через get_db_session() в хендлерах

    # 5. Регистрация обработчиков
    setup_handlers(application)
    logger.info("Handlers are set up.")

    # 6. Запуск бота
    try:
        logger.info("Initializing application...")
        await application.initialize()
        logger.info("Starting polling...")
        await application.start()
        await application.updater.start_polling()
        logger.info("Bot has started successfully. Press Ctrl-C to stop.")
        
        # Бесконечный цикл, чтобы процесс не завершался (если нет других задач в main)
        # На практике, updater.start_polling() уже блокирующий, но для явности можно оставить
        while True:
            await asyncio.sleep(3600) # Просыпаться раз в час, просто чтобы цикл был
            
    except Exception as e:
        logger.error(f"An error occurred during bot operation: {e}", exc_info=True)
    finally:
        logger.info("Stopping bot...")
        if application.updater and application.updater.running: # Проверка, запущен ли updater
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Bot stopped.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl-C).")
    except Exception as e:
        logger.critical(f"Critical error during bot startup or shutdown: {e}", exc_info=True)