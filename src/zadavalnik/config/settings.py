from dotenv import load_dotenv
import os

load_dotenv(".env", verbose=True)

class Settings:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    DB_PATH = os.getenv("DB_PATH", "./zadavalnik.db")

    