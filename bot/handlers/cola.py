"""Issue #9: comandos /cola, /pausar, /reanudar y los botones de aprobación del push."""
import asyncio
import uuid
from typing import Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.core import projects
from bot.core.cola import Cola
from bot.handlers.run import get_manager

_cola = None
_pendientes: Dict[str, asyncio.Future] = {}


def get_cola() -> Cola:
    global _cola
    if _cola is None:
        _cola = Cola(get_manager(), projects.cargar)
    return _cola


def crear_pedir_aprobacion(bot, chat_id: int):
    """Manda la pregunta con botones Subir/No subir y espera el clic de Johan."""
    async def pedir(texto: str) -> bool:
        aid = uuid.uuid4().hex[:8]
        fut = asyncio.get_running_loop().create_future()
        _pendientes[aid] = fut
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Subir", callback_data=f"cola:si:{aid}"),
                                        InlineKeyboardButton("🗑️ No subir", callback_data=f"cola:no:{aid}")]])
        try:
            await bot.send_message(chat_id=chat_id, text=texto[:4000], reply_markup=markup)
            return await fut
        finally:
            _pendientes.pop(aid, None)
    return pedir


async def responder_aprobacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, decision, aid = query.data.split(":", 2)
    fut = _pendientes.get(aid)
    if not fut or fut.done():
        await query.answer("Esta pregunta ya no está vigente", show_alert=True)
        return
    fut.set_result(decision == "si")
    await query.answer()
    await query.edit_message_text(query.message.text + ("\n\n🚀 Subiendo…" if decision == "si" else "\n\n🗑️ No se sube"))


async def cola(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        texto = await asyncio.to_thread(get_cola().resumen)
        await update.message.reply_text(texto)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def pausar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_cola().estado.pausar("pausada a mano con /pausar")
    await update.message.reply_text("⏸️ Cola en pausa. Termina lo que está haciendo y no toma más issues. /reanudar para seguir.")


async def reanudar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_cola().estado.reanudar()
    await update.message.reply_text("▶️ Cola activa (fallas seguidas en 0).")


def get_handlers():
    return [
        CommandHandler("cola", cola),
        CommandHandler("pausar", pausar),
        CommandHandler("reanudar", reanudar),
        CallbackQueryHandler(responder_aprobacion, pattern=r"^cola:(si|no):"),
    ]
