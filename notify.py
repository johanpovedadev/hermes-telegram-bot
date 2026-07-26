import sys
import asyncio
from telegram import Bot
from bot.core.config import BOT_TOKEN, CHAT_ID


async def notificar(mensaje: str):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=mensaje)


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Tarea completada"
    asyncio.run(notificar(msg))
