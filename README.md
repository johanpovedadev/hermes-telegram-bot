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
| `/run [proyecto] [tarea]` | Lanza el agente en segundo plano (solo proyectos habilitados en `projects.yaml`) |
| `/trabajos` | Trabajos corriendo y los últimos 10 |
| `/estado` | PM2, bots, puertos, CI y trabajos (datos reales, sin IA) |

## Vigía (avisos automáticos)

Cada 5 minutos Hermes revisa `pm2 jlist` y te escribe **una sola vez** por problema:

- 🔁 una app en bucle de reinicios (más de 5 en 10 minutos),
- 🔴 una app `stopped`/`errored`, o PM2 que no responde,
- ✅ cuando se arregla.

Con `HERMES_SILENCIO=22-7` lo crítico llega igual de noche y las recuperaciones llegan juntas en la mañana.

**¿Y si se cae Hermes o el PC?** Nadie adentro puede avisar. Para eso está el latido externo:

1. Crea un check gratis en https://healthchecks.io (periodo 5 min, gracia 10 min).
2. En *Integrations* conecta Telegram para que el aviso te llegue al celular.
3. Copia la URL de ping en `HERMES_HEARTBEAT_URL` del `.env` y reinicia Hermes.

Si Hermes deja de hacer ping, healthchecks.io te avisa.

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
