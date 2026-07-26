import sys
import os
import subprocess
import asyncio
from telegram import Bot
from bot.core.config import BOT_TOKEN, CHAT_ID

OPENCODE_CMD = os.path.join(os.environ.get("APPDATA", ""), "npm", "opencode.cmd")

LAST_LINES = 15


async def notificar(mensaje: str):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=mensaje)


def extraer_ultimas_lineas(texto, n=LAST_LINES):
    lineas = texto.strip().splitlines()
    return "\n".join(lineas[-n:])


def main():
    if len(sys.argv) < 2:
        print("Uso: python oc.py \"tu prompt aqui\"")
        sys.exit(1)

    prompt = sys.argv[1]
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."

    print(f"Ejecutando: {prompt}")
    print(f"Directorio: {cwd}")

    result = subprocess.run(
        [OPENCODE_CMD, "run", prompt],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    output = extraer_ultimas_lineas(result.stdout)
    errores = extraer_ultimas_lineas(result.stderr)

    if result.returncode == 0:
        msg = (
            f"Tarea completada\n"
            f"Prompt: {prompt}\n\n"
            f"Salida:\n{output}"
        )
    else:
        msg = (
            f"Error en tarea\n"
            f"Prompt: {prompt}\n"
            f"Exit code: {result.returncode}\n\n"
            f"Error:\n{errores}"
        )

    asyncio.run(notificar(msg))
    print("Notificacion enviada a Telegram")


if __name__ == "__main__":
    main()
