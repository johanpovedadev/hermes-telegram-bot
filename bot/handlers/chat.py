import asyncio
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.core.ai import preguntar_a_ia


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "Uso: `/chat [pregunta]`\nEj: `/chat resume de que trata LionCore`",
            parse_mode="Markdown"
        )
        return

    pregunta = " ".join(args)
    try:
        respuesta = await asyncio.to_thread(preguntar_a_ia, pregunta)
    except RuntimeError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    except Exception as e:
        await update.message.reply_text(f"❌ Error consultando IA: {e}")
        return

    await update.message.reply_text(respuesta, disable_web_page_preview=True)


def get_handlers():
    return [
        CommandHandler("chat", chat),
    ]