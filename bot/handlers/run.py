import uuid

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot.core import projects
from bot.core.jobs import JobManager, ProyectoOcupado, agente_configurado, resumen_trabajos
from bot.core.notifications import NotificationManager
from bot.handlers.callbacks import crear_botones_notificacion

nm = NotificationManager()
_manager = None


def get_manager() -> JobManager:
    """Un solo administrador de trabajos por proceso (los candados por proyecto viven aquí)."""
    global _manager
    if _manager is None:
        _manager = JobManager()
        _manager.store.marcar_interrumpidos()
    return _manager


RESULTADO_POR_ICONO = {"✅": "success", "❌": "error", "⏰": "timeout"}


def _notificador(context, chat_id: int, proyecto: str, prompt: str):
    """Envía los avisos del trabajo al chat. El aviso final lleva los botones de aprobar/rechazar de siempre."""
    async def notify(texto: str):
        markup = None
        resultado = RESULTADO_POR_ICONO.get(texto[:1])
        if resultado:
            notif_id = str(uuid.uuid4())[:8]
            nm.crear_notificacion(notif_id, proyecto, prompt, resultado=resultado)
            markup = crear_botones_notificacion(notif_id)
        # Texto plano: la salida del agente puede traer caracteres que rompen el Markdown de Telegram.
        await context.bot.send_message(chat_id=chat_id, text=texto[:4000], reply_markup=markup)
    return notify


async def ejecutar_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/run <proyecto> <tarea>: lanza el agente en segundo plano y avisa al empezar, al terminar y si falla."""
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("⚠️ Uso: `/run [proyecto] [tarea]`", parse_mode="Markdown")
            return
        prompt = " ".join(args[1:])
        # Solo proyectos de projects.yaml y habilitados (issue #8).
        registro = projects.cargar()
        if not registro.valido:
            await update.message.reply_text("❌ projects.yaml tiene errores:\n" + "\n".join(f"• {e}" for e in registro.errores[:5]))
            return
        info, motivo = registro.para_trabajar(args[0])
        if not info:
            await update.message.reply_text(motivo, parse_mode="Markdown")
            return
        manager = get_manager()
        try:
            job_id = manager.iniciar(info, prompt, _notificador(context, update.effective_chat.id, info.nombre, prompt))
        except ProyectoOcupado as e:
            await update.message.reply_text(str(e), parse_mode="Markdown")
            return
        await update.message.reply_text(
            f"🗂️ Trabajo #{job_id} en cola para `{info.nombre}` ({agente_configurado()}). Te aviso cuando termine; puedes seguir usando el bot.",
            parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def trabajos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/trabajos: lo que está corriendo y los últimos 10."""
    try:
        await update.message.reply_text(resumen_trabajos(get_manager()), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


def get_handlers():
    return [
        CommandHandler("run", ejecutar_issue),
        CommandHandler("trabajos", trabajos),
    ]
