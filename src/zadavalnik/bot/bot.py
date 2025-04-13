from telegram.ext import Application
from zadavalnik.config.settings import Settings
from zadavalnik.bot.handlers import setup_handlers

class Bot:
    def __init__(self):
        """
        Инициализирует Telegram-бота с токеном из конфигурации.
        """
        self.app = Application.builder().token(Settings.TELEGRAM_TOKEN).build()
        setup_handlers(self.app)

    def run(self):
        """
        Запускает бота в режиме polling.
        """
        self.app.run_polling()