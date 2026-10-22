"""Issue #9: /pedir, /cola, /pausar, /reanudar y los botones ✅ Funciona / ❌ No funciona."""
import asyncio
import uuid
from typing import Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.core import projects
from bot.core.cola import ETQ_LISTO, Cola
from bot.core.estado import run_cmd
from bot.handlers.run import get_manager

_cola = None
_pendientes: Dict[str, asyncio.Future] = {}


def get_cola() -> Cola:
    global _cola
    if _cola is None:
        _cola = Cola(get_manager(), projects.cargar)
    return _cola


def crear_pedir_aprobacion(bot, chat_id: int):
    """Manda la pregunta con botones ✅ Funciona / ❌ No funciona y espera el clic de Johan."""
    async def pedir(texto: str) -> bool:
        aid = uuid.uuid4().hex[:8]
        fut = asyncio.get_running_loop().create_future()
        _pendientes[aid] = fut
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Funciona", callback_data=f"cola:si:{aid}"),
                                        InlineKeyboardButton("❌ No funciona", callback_data=f"cola:no:{aid}")]])
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
    await query.edit_message_text(query.message.text + ("\n\n✅ Haciendo el merge…" if decision == "si" else "\n\n❌ Queda abierto"))


def titulo_de(pedido: str) -> str:
    primera = pedido.strip().split("\n")[0].split(". ")[0].strip()
    t = primera[:70].rstrip()
    return (t[0].upper() + t[1:]) if t else "Pedido desde Telegram"


def crear_issue(proyecto, pedido: str, run=run_cmd) -> str:
    """Crea el issue con hermes:listo para que la cola lo tome. Devuelve el enlace."""
    cuerpo = f"{pedido.strip()}\n\n_Pedido por Johan desde Telegram. Hermes lo toma de la cola._"
    code, out, err = run(["gh", "issue", "create", "--repo", proyecto.repo, "--title", titulo_de(pedido),
                          "--body", cuerpo, "--label", ETQ_LISTO], 60)
    if code != 0:
        raise RuntimeError((err or out).strip()[:300] or f"gh salió con código {code}")
    return out.strip().splitlines()[-1]


async def pedir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pedir <proyecto> <qué quieres>: crea el issue y lo pone en la cola."""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("⚠️ Uso: /pedir <proyecto> <qué quieres>\nEj.: /pedir saas-bot que la heladería salude por el nombre")
        return
    registro = projects.cargar()
    p = registro.obtener(args[0])
    if not p or not p.habilitado or not p.repo:
        habil = ", ".join(x.nombre for x in registro.proyectos if x.habilitado and x.repo) or "ninguno"
        await update.message.reply_text(f"❌ «{args[0]}» no está habilitado en projects.yaml. Puedes pedir en: {habil}")
        return
    try:
        enlace = await asyncio.to_thread(crear_issue, p, " ".join(args[1:]))
    except Exception as e:
        await update.message.reply_text(f"❌ No pude crear el issue: {e}")
        return
    estado = get_cola().freno()
    await update.message.reply_text(f"📝 Anotado en {p.nombre}: {enlace}\n"
                                    + (f"Ojo: {estado}" if estado else "Lo tomo en la próxima vuelta de la cola y te voy contando."))


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
        CommandHandler("pedir", pedir),
        CommandHandler("cola", cola),
        CommandHandler("pausar", pausar),
        CommandHandler("reanudar", reanudar),
        CallbackQueryHandler(responder_aprobacion, pattern=r"^cola:(si|no):"),
    ]
