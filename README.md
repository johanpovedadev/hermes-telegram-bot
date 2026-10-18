# Hermes Bot

Bot de Telegram que ejecuta OpenCode CLI de forma remota.

## Requisitos

- Python 3.10+
- Node.js + `npm install -g opencode-ai`
- Token de BotFather

## Instalación

```powershell
pip install -r requirements.txt
copy .env.example .env
# Editar .env con tu token
python bot.py
```

## Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Menú de comandos |
| `/status` | Verifica OpenCode CLI |
| `/proyectos` | Lista carpetas en Documentos |
| `/run [carpeta] [prompt]` | Ejecuta OpenCode en un proyecto |

## Desarrollo

```bash
pip install -r requirements-dev.txt
cp .env.example .env    # y llenar HERMES_BOT_TOKEN, HERMES_CHAT_ID
python -m pytest -q     # todas las pruebas deben pasar antes de subir (CI en cada PR)
python bot.py
```

- `notify.py "mensaje"`: envía un aviso a tu chat (lo usan los hooks de Claude Code).
- `notify_permission.py`: hook `Notification` de Claude Code (avisa cuando pide un permiso).
- `scripts/probar_deepseek.py`: prueba la IA de `/chat` con tu `DEEPSEEK_API_KEY` y `DEEPSEEK_MODEL`.
- Reglas del ecosistema: ver `REGLAS_ECOSISTEMA.md` (PR `docs/reglas-ecosistema`).
