import os
import asyncio
import subprocess
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.core.config import DOCUMENTS_PATH


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ *Hermes Activo*\n\n"
        "Comandos:\n"
        "• `/proyectos` - Lista repos en Documentos\n"
        "• `/run [proyecto] [issue]` - Ejecuta OpenCode\n"
        "• `/status` - Verifica OpenCode CLI",
        parse_mode="Markdown"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        result = await asyncio.to_thread(
            subprocess.run, ["opencode", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            await update.message.reply_text(
                f"✅ OpenCode CLI: `{result.stdout.strip()}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ OpenCode CLI no responde.")
    except FileNotFoundError:
        await update.message.reply_text(
            "❌ OpenCode CLI no instalado.\n"
            "Ejecuta: `npm install -g opencode-ai`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def listar_proyectos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        folders = [
            f for f in os.listdir(DOCUMENTS_PATH)
            if os.path.isdir(os.path.join(DOCUMENTS_PATH, f))
        ]
        if not folders:
            await update.message.reply_text("📂 No hay carpetas en Documentos.")
            return
        msg = "📁 *Proyectos:*\n\n" + "\n".join([f"• `{f}`" for f in folders])
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("status", status),
        CommandHandler("proyectos", listar_proyectos),
    ]
