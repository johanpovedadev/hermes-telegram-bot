from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ContextTypes
from bot.core.notifications import NotificationManager

nm = NotificationManager()

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja clic en botón 'Aprobar'."""
    query = update.callback_query
    notif_id = query.data.split(":")[1]

    user_id = update.effective_user.id

    if nm.aprobar(notif_id, user_id=user_id):
        await query.answer(f"✅ Aprobado por @{update.effective_user.username or 'usuario'}")

        text = query.message.text + "\n\n✅ *Aprobado* por @" + (update.effective_user.username or "usuario")

        await query.edit_message_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=None
        )
    else:
        await query.answer("❌ Notificación no encontrada", show_alert=True)

async def handle_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja clic en botón 'Rechazar'."""
    query = update.callback_query
    notif_id = query.data.split(":")[1]

    if nm.rechazar(notif_id):
        await query.answer(f"❌ Rechazado por @{update.effective_user.username or 'usuario'}")

        text = query.message.text + "\n\n❌ *Rechazado* por @" + (update.effective_user.username or "usuario")

        await query.edit_message_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=None
        )
    else:
        await query.answer("❌ Notificación no encontrada", show_alert=True)

async def handle_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja clic en botón 'Ver más'."""
    query = update.callback_query
    notif_id = query.data.split(":")[1]

    todas = nm.obtener_todas()
    notif = next((n for n in todas if n.id == notif_id), None)

    if notif:
        stats = nm.obtener_estadisticas_proyecto(notif.proyecto)

        details = (
            f"📋 *Detalles del Proceso*\n\n"
            f"🆔 ID: `{notif.id}`\n"
            f"🏗️ Proyecto: `{notif.proyecto}`\n"
            f"📌 Proceso: `{notif.proceso}`\n"
            f"⏰ Hora: `{notif.timestamp}`\n"
            f"📊 Estado: {_estado_emoji(notif.estado)}\n\n"
            f"📈 *Estadísticas del Proyecto:*\n"
            f"• Total: {stats['total_procesos']}\n"
            f"• ✅ Aprobados: {stats['aprobados']}\n"
            f"• ❌ Rechazados: {stats['rechazados']}\n"
            f"• ⏳ Pendientes: {stats['pendientes']}"
        )

        await query.answer()
        await query.edit_message_text(
            text=details,
            parse_mode="Markdown"
        )
    else:
        await query.answer("❌ Notificación no encontrada", show_alert=True)

async def handle_later(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja clic en botón 'Después'."""
    query = update.callback_query
    await query.answer("⏳ Recordatorio guardado. Revisaremos después.")

def _estado_emoji(estado: str) -> str:
    emojis = {
        "pendiente": "⏳ Pendiente",
        "aprobado": "✅ Aprobado",
        "rechazado": "❌ Rechazado"
    }
    return emojis.get(estado, estado)

def crear_botones_notificacion(notif_id: str) -> InlineKeyboardMarkup:
    """Crea botones para una notificación."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar", callback_data=f"approve:{notif_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"reject:{notif_id}"),
        ],
        [
            InlineKeyboardButton("❓ Ver más", callback_data=f"details:{notif_id}"),
            InlineKeyboardButton("⏳ Después", callback_data=f"later:{notif_id}"),
        ]
    ])

def get_handlers():
    return [
        CallbackQueryHandler(handle_approval, pattern=r"^approve:"),
        CallbackQueryHandler(handle_rejection, pattern=r"^reject:"),
        CallbackQueryHandler(handle_details, pattern=r"^details:"),
        CallbackQueryHandler(handle_later, pattern=r"^later:"),
    ]
