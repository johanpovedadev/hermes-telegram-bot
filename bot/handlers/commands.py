import os
import asyncio
import subprocess
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.core.config import DOCUMENTS_PATH
from bot.core.notifications import NotificationManager
from bot.core import projects

nm = NotificationManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ *Jarvis León Activo*\n\n"
        "📋 *Comandos Disponibles:*\n\n"
        "*Ejecución:*\n"
        "• `/run [proyecto] [tarea]` - Ejecutar tarea con OpenCode\n"
        "• `/chat [pregunta]` - Consulta IA (DeepSeek)\n\n"
        "*Información:*\n"
        "• `/proyectos` - Listar proyectos disponibles\n"
        "• `/status` - Estado de OpenCode CLI\n\n"
        "*Notificaciones & Auditoría:*\n"
        "• `/notificaciones` - Ver tareas pendientes de aprobación\n"
        "• `/historial` - Últimas 10 tareas completadas\n"
        "• `/estadisticas` - Procesos por proyecto\n"
        "• `/audit` - Log completo con timestamps\n"
        "• `/confiabilidad` - Tasa de éxito por proceso",
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
    """Lista los proyectos de projects.yaml (issue #8), ya no las carpetas sueltas de Documentos."""
    try:
        registro = projects.cargar()
        if not registro.proyectos and registro.errores:
            await update.message.reply_text("❌ projects.yaml:\n" + "\n".join(f"• {e}" for e in registro.errores[:5]))
            return
        lineas = ["📁 *Proyectos:*", ""]
        for p in registro.proyectos:
            estado = "✅" if p.habilitado else "⛔"
            lineas.append(f"{estado} `{p.nombre}` — {p.repo or 'sin repo'}")
        if registro.errores:
            lineas += ["", "⚠️ *Errores:*"] + [f"• {e}" for e in registro.errores[:5]]
        if registro.avisos:
            lineas += ["", "ℹ️ " + "; ".join(registro.avisos[:3])]
        await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar notificaciones pendientes de aprobación."""
    pendientes = nm.obtener_pendientes()

    if not pendientes:
        await update.message.reply_text("✅ No hay tareas pendientes de aprobación.")
        return

    msg = f"⏳ *Tareas Pendientes:* ({len(pendientes)})\n\n"

    for i, notif in enumerate(pendientes, 1):
        msg += f"{i}. 🏗️ `{notif.proyecto}`\n"
        msg += f"   📌 {notif.proceso}\n"
        msg += f"   ⏰ {notif.timestamp}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar últimas 10 tareas."""
    todas = nm.obtener_todas(limite=10)

    if not todas:
        await update.message.reply_text("📂 No hay historial.")
        return

    msg = f"📋 *Últimas {len(todas)} Tareas:*\n\n"

    for i, notif in enumerate(todas, 1):
        emoji = "✅" if notif.estado == "aprobado" else "❌" if notif.estado == "rechazado" else "⏳"
        msg += f"{i}. {emoji} `{notif.proyecto}` - {notif.proceso[:30]}\n"
        msg += f"   ⏰ {notif.timestamp}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar estadísticas por proyecto."""
    todas = nm.obtener_todas(limite=100)

    if not todas:
        await update.message.reply_text("📂 No hay datos.")
        return

    proyectos = set(n.proyecto for n in todas)
    msg = f"📊 *Estadísticas por Proyecto:*\n\n"

    for proyecto in sorted(proyectos):
        stats = nm.obtener_estadisticas_proyecto(proyecto)
        msg += f"📦 *{proyecto}*\n"
        msg += f"  Total: {stats['total_procesos']} | "
        msg += f"✅ {stats['aprobados']} | "
        msg += f"❌ {stats['rechazados']} | "
        msg += f"⏳ {stats['pendientes']}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def audit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar log completo con timestamps."""
    todas = nm.obtener_todas(limite=50)

    if not todas:
        await update.message.reply_text("📂 No hay registro.")
        return

    msg = f"🔍 *Audit Log* (últimas {len(todas)}):\n\n"

    for notif in todas:
        emoji = "✅" if notif.estado == "aprobado" else "❌" if notif.estado == "rechazado" else "⏳"
        msg += f"{emoji} {notif.timestamp}\n"
        msg += f"   `{notif.proyecto}` > {notif.proceso}\n"
        if notif.approved_by:
            msg += f"   👤 {notif.approved_by}\n"
        msg += "\n"

    if len(msg) > 4000:
        msg = msg[:3900] + "\n\n... (truncado)"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def confiabilidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar métricas de confiabilidad."""
    metricas = nm.obtener_metricas()

    if not metricas:
        await update.message.reply_text("📊 Sin datos de confiabilidad aún.")
        return

    msg = "📈 *Tasa de Confiabilidad:*\n\n"

    for proyecto in sorted(metricas.keys()):
        msg += f"📦 *{proyecto}*\n"
        procesos = metricas[proyecto]

        for proceso, stats in sorted(procesos.items()):
            total = stats.get("total", 0)
            success = stats.get("success", 0)
            tasa = (success / total * 100) if total > 0 else 0
            msg += f"  • {proceso}: {success}/{total} ({tasa:.0f}%)\n"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("status", status),
        CommandHandler("proyectos", listar_proyectos),
        CommandHandler("notificaciones", notificaciones),
        CommandHandler("historial", historial),
        CommandHandler("estadisticas", estadisticas),
        CommandHandler("audit", audit),
        CommandHandler("confiabilidad", confiabilidad),
    ]
