"""Envía un aviso al chat de Jarvis León (@JarvisLeonAI_bot).

Restaurado desde el stash de feat/jarvis-rename-and-opencode-cli-tools (la versión
que funcionó hasta el 20-sep-2026). Autocontenido: lee HERMES_BOT_TOKEN y
HERMES_CHAT_ID del .env de esta carpeta, porque el config.py de master no trae
CHAT_ID. Lo usan notify_permission.py y los hooks de Claude Code.
"""
import sys
import os
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from telegram import Bot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN = os.environ.get("HERMES_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("HERMES_CHAT_ID", "5534032418"))
DEBUG_LOG = os.path.join(BASE_DIR, "notify_debug.log")


def log_debug(linea: str):
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {linea}\n")


async def notificar(mensaje: str):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=mensaje)


def es_trabajo_de_hermes() -> bool:
    """Los claude -p que lanza Hermes ya avisan por la cola; sus hooks no deben duplicar el aviso."""
    return os.environ.get("HERMES_JOB") == "1"


if __name__ == "__main__":
    if es_trabajo_de_hermes():
        sys.exit(0)
    msg = sys.argv[1] if len(sys.argv) > 1 else "Tarea completada"
    log_debug(f"hook=notify token_ok={bool(BOT_TOKEN)} chat_id={CHAT_ID} msg={msg}")
    try:
        asyncio.run(notificar(msg))
        log_debug("OK: notificacion enviada")
        print(f"OK: notificacion enviada: {msg}")
    except Exception as e:
        log_debug(f"ERROR: {e}")
        print(f"ERROR: no se pudo enviar la notificacion: {e}", file=sys.stderr)
        sys.exit(1)
