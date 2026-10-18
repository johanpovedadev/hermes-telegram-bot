import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.core.config import BOT_TOKEN, ALLOWED_CHAT_IDS_RAW
from bot.core.security import parse_allowed, build_guard_handler, GUARD_GROUP
from bot.handlers.commands import get_handlers as cmd_handlers
from bot.handlers.run import get_handlers as run_handlers
from bot.handlers.callbacks import get_handlers as callback_handlers
from bot.handlers.cola import get_handlers as cola_handlers
from bot.handlers.chat import get_handlers as chat_handlers

from telegram.ext import ApplicationBuilder


def crear_post_init(allowed):
    """Al arrancar: vigía de PM2 (#7) y cola de issues (#9) en segundo plano. Avisan al HERMES_CHAT_ID o al primer chat permitido."""
    async def post_init(app):
        from bot.core.vigia import Vigia, bucle_vigia
        chat_id = int(os.environ.get("HERMES_CHAT_ID") or sorted(allowed)[0])

        async def notify(texto):
            await app.bot.send_message(chat_id=chat_id, text=texto[:4000])

        if os.environ.get("HERMES_VIGIA", "1") != "0":
            app.create_task(bucle_vigia(Vigia(), notify))

        # Cola de issues (issue #9): apagada por defecto; trabaja sola, así que se prende a propósito con HERMES_COLA=1.
        if os.environ.get("HERMES_COLA", "0") == "1":
            from bot.core.cola import bucle_cola
            from bot.handlers.cola import crear_pedir_aprobacion, get_cola
            app.create_task(bucle_cola(get_cola(), notify, crear_pedir_aprobacion(app.bot, chat_id)))
    return post_init


def main():
    if not BOT_TOKEN:
        print("Configura HERMES_BOT_TOKEN en .env o variable de entorno.")
        sys.exit(1)

    try:
        allowed = parse_allowed(ALLOWED_CHAT_IDS_RAW)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    if not allowed:
        # Falla cerrado: sin lista de chats permitidos, cualquiera podría darle órdenes al bot.
        print("❌ Configura HERMES_ALLOWED_CHAT_IDS en .env (tu chat id de Telegram). Sin eso el bot no arranca.")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.post_init = crear_post_init(allowed)
    # La guardia va en el grupo -1: corre antes que cualquier comando, botón o mensaje.
    app.add_handler(build_guard_handler(allowed), group=GUARD_GROUP)

    for handler in cmd_handlers():
        app.add_handler(handler)
    for handler in run_handlers():
        app.add_handler(handler)
    for handler in callback_handlers():
        app.add_handler(handler)
    for handler in cola_handlers():
        app.add_handler(handler)
    for handler in chat_handlers():
        app.add_handler(handler)

    print("⚡ Jarvis León iniciado. Escuchando comandos...")
    app.run_polling()


if __name__ == "__main__":
    main()
