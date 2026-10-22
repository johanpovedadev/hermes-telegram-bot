"""Issue #3: Hermes SOLO obedece a los chats permitidos.

Antes, cualquiera que encontrara @JarvisLeonAI_bot podía mandar `/run <carpeta> <prompt>` y ejecutar un agente en el
PC de Johan. Ahora una guardia corre ANTES que cualquier otro handler (grupo -1) y, si el chat no está en
HERMES_ALLOWED_CHAT_IDS, corta el update: no se ejecuta ningún comando, botón, texto ni nota de voz, el bot no responde
nada (ni siquiera confirma que existe) y el intento queda en la auditoría.

Falla cerrado: sin HERMES_ALLOWED_CHAT_IDS el bot no arranca.
"""
import json
import os
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional, Set

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes, TypeHandler

GUARD_GROUP = -1


def parse_allowed(raw: Optional[str]) -> Set[int]:
    """'5534032418, 123' -> {5534032418, 123}. Ignora vacíos; un valor no numérico es un error de configuración."""
    out: Set[int] = set()
    for part in str(raw or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError as e:
            raise ValueError(f"HERMES_ALLOWED_CHAT_IDS tiene un valor que no es un número: {part!r}") from e
    return out


def default_audit_path() -> str:
    data_dir = os.path.expanduser(os.environ.get("HERMES_DATA_DIR", "~/.jarvis"))
    return os.path.join(data_dir, "seguridad.jsonl")


def describe_update(update: Update) -> str:
    """Qué intentó hacer (para la auditoría), sin guardar mensajes largos."""
    if getattr(update, "callback_query", None) is not None and update.callback_query:
        return f"boton:{str(update.callback_query.data or '')[:60]}"
    msg = getattr(update, "effective_message", None)
    if msg is not None:
        if getattr(msg, "text", None):
            return f"texto:{msg.text[:60]}"
        if getattr(msg, "voice", None):
            return "voz"
    return "otro"


def make_audit_writer(path: Optional[str] = None) -> Callable[[dict], None]:
    target = path or default_audit_path()

    def write(entry: dict) -> None:
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # la auditoría nunca tumba al bot

    return write


def make_guard(allowed: Iterable[int], audit: Optional[Callable[[dict], None]] = None):
    """Callback de la guardia. Deja pasar los chats permitidos; a los demás los corta en seco."""
    allowed_set = set(allowed)
    audit = audit or make_audit_writer()

    async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = getattr(update, "effective_chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is not None and chat_id in allowed_set:
            return
        user = getattr(update, "effective_user", None)
        audit({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evento": "bloqueado",
            "chat_id": chat_id,
            "user_id": getattr(user, "id", None),
            "username": getattr(user, "username", None),
            "intento": describe_update(update),
        })
        raise ApplicationHandlerStop

    return guard


def build_guard_handler(allowed: Iterable[int], audit: Optional[Callable[[dict], None]] = None) -> TypeHandler:
    return TypeHandler(Update, make_guard(allowed, audit))
