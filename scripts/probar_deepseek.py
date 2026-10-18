import os
import sys
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def main():
    if not DEEPSEEK_API_KEY:
        print("No hay DEEPSEEK_API_KEY. Obtén una gratis en:")
        print("  1) Crear cuenta gratis en https://build.nvidia.com")
        print("  2) Modelo: deepseek-ai -> DeepSeek V4 Flash -> Get API key")
        print("  3) Copia la key y agregala al .env como DEEPSEEK_API_KEY=sk-...")
        sys.exit(1)

    print(f"Probando: {DEEPSEEK_BASE_URL}/chat/completions  modelo={DEEPSEEK_MODEL}")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "Eres un asistente breve."},
            {"role": "user", "content": "Responde solo: OK"},
        ],
        "max_tokens": 200,
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
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print(f"✅ Respuesta del modelo: {data['choices'][0]['message']['content']!r}")


if __name__ == "__main__":
    main()