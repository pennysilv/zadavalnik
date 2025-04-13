# from .config.settings import Settings

# def main():

#     print(Settings.TELEGRAM_TOKEN)
#     return "Hello world"

# if __name__ == "__main__":
#     print(main())


from zadavalnik.bot.bot import Bot
from zadavalnik.database.db import init_db

def main():
    """
    Инициализирует базу данных и запускает бота.
    """
    init_db()
    bot = Bot()
    bot.run()

if __name__ == "__main__":
    main()