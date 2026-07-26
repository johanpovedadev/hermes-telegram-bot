import os
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.core.config import DOCUMENTS_PATH, MAX_OUTPUT_LENGTH
from bot.core.opencode_runner import ejecutar_opencode

LAST_LINES = 15


def extraer_ultimas_lineas(texto, n=LAST_LINES):
    lineas = texto.strip().splitlines()
    return "\n".join(lineas[-n:])


async def ejecutar_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: `/run [carpeta] [prompt]`",
            parse_mode="Markdown"
        )
        return

    proyecto = args[0]
    prompt = " ".join(args[1:])
    target_path = os.path.join(DOCUMENTS_PATH, proyecto)

    if not os.path.exists(target_path):
        await update.message.reply_text(
            f"No existe `{proyecto}`.",
            parse_mode="Markdown"
        )
        return

    status_msg = await update.message.reply_text(
        f"Ejecutando en `{proyecto}`...\n_{prompt}_",
        parse_mode="Markdown"
    )

    chat_id = update.effective_chat.id

    async def on_complete(result):
        if result.get("timeout"):
            text = f"Timeout ({result['stderr']})"
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id, text=text
            )
            return

        output = extraer_ultimas_lineas(result["stdout"])
        errores = extraer_ultimas_lineas(result["stderr"])

        if result["returncode"] == 0:
            text = (
                f"Tarea completada: {proyecto}\n"
                f"Prompt: {prompt}\n\n"
                f"Salida:\n```\n{output}\n```"
            )
        else:
            text = (
                f"Error en: {proyecto}\n"
                f"Prompt: {prompt}\n"
                f"Exit code: {result['returncode']}\n\n"
                f"Error:\n```\n{errores}\n```"
            )

        if len(text) > MAX_OUTPUT_LENGTH:
            text = text[:MAX_OUTPUT_LENGTH] + "\n... (truncado)"

        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=status_msg.message_id,
            text=text, parse_mode="Markdown"
        )

    await ejecutar_opencode(prompt, target_path, on_complete=on_complete)


def get_handlers():
    return [
        CommandHandler("run", ejecutar_issue),
    ]
