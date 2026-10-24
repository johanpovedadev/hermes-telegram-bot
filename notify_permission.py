import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify import notificar, log_debug, es_trabajo_de_hermes

EMOJIS = {
    "permission_prompt": "🔐 Permiso requerido",
    "idle_prompt": "⏳ En espera",
    "auth_success": "✅ Autenticacion",
}


def main():
    if es_trabajo_de_hermes():
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    notification_type = data.get("notification_type") or "permission_prompt"
    title = data.get("title", "")
    message = data.get("message", "")

    if notification_type not in EMOJIS:
        log_debug(f"hook=permission tipo={notification_type} IGNORADO (mensaje={message})")
        return

    texto = message or title
    if not texto:
        texto = "Claude Code quedo en espera (tarea finalizada)" if notification_type == "idle_prompt" else "Necesita tu atencion"

    log_debug(f"hook=permission tipo={notification_type} msg={texto}")
    try:
        asyncio.run(notificar(f"{EMOJIS[notification_type]} en Claude Code:\n{texto}"))
    except Exception as e:
        log_debug(f"hook=permission ERROR: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
