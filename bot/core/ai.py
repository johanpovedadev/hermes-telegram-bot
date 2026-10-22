import json
import urllib.request
import urllib.error

from bot.core.config import AI_PROVIDER, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

SYSTEM_PROMPT = (
    "Eres Jarvis León, asistente personal. Responde en español, "
    "claro y breve, con emoticonos de estado cuando aplique."
)


def _llamar_openai_compat(mensaje: str, system: str = SYSTEM_PROMPT, max_tokens: int = 2000) -> str:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": mensaje},
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        data = json.loads(res.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def preguntar_a_ia(mensaje: str) -> str:
    if AI_PROVIDER == "none":
        raise RuntimeError("IA no configurada: agrega AI_PROVIDER=deepseek y DEEPSEEK_API_KEY en .env")
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("IA no configurada: falta DEEPSEEK_API_KEY en .env")
    if not DEEPSEEK_MODEL:
        raise RuntimeError("IA no configurada: falta DEEPSEEK_MODEL en .env (el id exacto del modelo en tu proveedor)")
    return _llamar_openai_compat(mensaje)