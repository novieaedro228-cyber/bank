import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_HOST = "127.0.0.1"
WEBAPP_PORT = 3001
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # Для продакшена
DATABASE_URL = "sqlite:///./bank.db"