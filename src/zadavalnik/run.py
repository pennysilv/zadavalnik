# run.py (в корне проекта)

import asyncio
import logging

# Импортируем функцию main из нашего модуля бота
from zadavalnik.bot.bot import main as run_bot_main 
# Даем псевдоним, чтобы избежать конфликта с локальной функцией main, если она понадобится здесь

# Можно настроить базовое логирование здесь, если хотите,
# хотя в zadavainik/bot/bot.py оно уже настроено.
# Это может быть полезно, если сам run.py делает какие-то предварительные действия.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# logger = logging.getLogger(__name__)

logging.getLogger("zadavalnik.ai.openai_client").setLevel(logging.DEBUG)
logging.getLogger("zadavalnik.bot.handlers").setLevel(logging.DEBUG) # Для логов истории в хендлерах


if __name__ == "__main__":
    # logger.info("Starting application via run.py...")
    try:
        # Запускаем асинхронную функцию main из модуля бота
        asyncio.run(run_bot_main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Application stopped by user (Ctrl-C) via run.py.")
    except Exception as e:
        logging.getLogger(__name__).critical(f"Critical error during application startup via run.py: {e}", exc_info=True)