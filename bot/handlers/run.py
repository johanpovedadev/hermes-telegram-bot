import os
import uuid
import subprocess
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
from bot.core.config import TIMEOUT_SECONDS, MAX_OUTPUT_LENGTH
from bot.core import projects
from bot.core.opencode_runner import ejecutar_opencode
from bot.core.notifications import NotificationManager
from bot.handlers.callbacks import crear_botones_notificacion

nm = NotificationManager()

async def ejecutar_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "⚠️ Uso: `/run [carpeta] [prompt]`",
                parse_mode="Markdown"
            )
            return

        prompt = " ".join(args[1:])
        # Solo proyectos de projects.yaml y habilitados (issue #8): antes /run aceptaba cualquier carpeta de Documentos.
        registro = projects.cargar()
        if not registro.valido:
            await update.message.reply_text("❌ projects.yaml tiene errores:\n" + "\n".join(f"• {e}" for e in registro.errores[:5]))
            return
        info, motivo = registro.para_trabajar(args[0])
        if not info:
            await update.message.reply_text(motivo, parse_mode="Markdown")
            return
        proyecto = info.nombre
        target_path = info.carpeta

        await update.message.reply_text(
            f"⏳ *Ejecutando en `{proyecto}`...*\n📝 _{prompt}_",
            parse_mode="Markdown"
        )

        result = await ejecutar_opencode(prompt, target_path)

        output = result["stdout"][-1500:] if result["stdout"] else ""
        errors = result["stderr"][-500:] if result["stderr"] else ""

        notif_id = str(uuid.uuid4())[:8]

        if result["returncode"] == 0:
            msg = f"✅ *Completado:* `{proyecto}`\n📌 *Proceso:* `{prompt[:50]}...`\n\n```\n{output}\n```"
            nm.crear_notificacion(notif_id, proyecto, prompt, resultado="success")
        else:
            msg = f"❌ *Error en:* `{proyecto}`\n📌 *Proceso:* `{prompt[:50]}...`\n\n```\n{errors}\n```"
            nm.crear_notificacion(notif_id, proyecto, prompt, resultado="error")

        if len(msg) > MAX_OUTPUT_LENGTH:
            msg = msg[:MAX_OUTPUT_LENGTH] + "\n... (truncado)"

        reply_markup = crear_botones_notificacion(notif_id)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

    except subprocess.TimeoutExpired:
        notif_id = str(uuid.uuid4())[:8]
        nm.crear_notificacion(notif_id, args[0] if args else "unknown",
                            " ".join(args[1:]) if len(args) > 1 else "",
                            resultado="timeout")
        await update.message.reply_text(
            f"⏰ Timeout ({TIMEOUT_SECONDS}s)."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


def get_handlers():
    return [
        CommandHandler("run", ejecutar_issue),
    ]
