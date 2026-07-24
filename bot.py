import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.core.config import BOT_TOKEN
from bot.handlers.commands import get_handlers as cmd_handlers
from bot.handlers.run import get_handlers as run_handlers

from telegram.ext import ApplicationBuilder


def main():
    if not BOT_TOKEN:
        print("Configura HERMES_BOT_TOKEN en .env o variable de entorno.")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    for handler in cmd_handlers():
        app.add_handler(handler)
    for handler in run_handlers():
        app.add_handler(handler)

    print("🤖 Hermes iniciado. Escuchando comandos...")
    app.run_polling()


if __name__ == "__main__":
    main()
