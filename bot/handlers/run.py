import os
import subprocess
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.core.config import DOCUMENTS_PATH, TIMEOUT_SECONDS, MAX_OUTPUT_LENGTH
from bot.core.opencode_runner import ejecutar_opencode


async def ejecutar_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "⚠️ Uso: `/run [carpeta] [prompt]`",
                parse_mode="Markdown"
            )
            return

        proyecto = args[0]
        prompt = " ".join(args[1:])
        target_path = os.path.join(DOCUMENTS_PATH, proyecto)

        if not os.path.exists(target_path):
            await update.message.reply_text(
                f"❌ No existe `{proyecto}`.",
                parse_mode="Markdown"
            )
            return

        await update.message.reply_text(
            f"⏳ *Ejecutando en `{proyecto}`...*\n📝 _{prompt}_",
            parse_mode="Markdown"
        )

        result = await ejecutar_opencode(prompt, target_path)

        output = result["stdout"][-1500:] if result["stdout"] else ""
        errors = result["stderr"][-500:] if result["stderr"] else ""

        if result["returncode"] == 0:
            msg = f"✅ *Completado:*\n```\n{output}\n```"
        else:
            msg = f"❌ *Error:*\n```\n{errors}\n```"

        if len(msg) > MAX_OUTPUT_LENGTH:
            msg = msg[:MAX_OUTPUT_LENGTH] + "\n... (truncado)"

        await update.message.reply_text(msg, parse_mode="Markdown")

    except subprocess.TimeoutExpired:
        await update.message.reply_text(
            f"⏰ Timeout ({TIMEOUT_SECONDS}s)."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


def get_handlers():
    return [
        CommandHandler("run", ejecutar_issue),
    ]
