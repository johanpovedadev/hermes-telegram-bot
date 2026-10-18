# Instrucciones para Claude Code / Cowork en este repo

## Notificar por Telegram al terminar tareas

Los hooks de `~/.claude/settings.json` (Stop/SubagentStop/Notification) solo se disparan en
sesiones de la CLI local `claude`, **no** en sesiones de Cowork. Como este proyecto es justo
el bot de Telegram del usuario y él quiere enterarse cuando una tarea termina, en sesiones de
Cowork hay que avisar manualmente:

- Al terminar una tarea significativa (no trivial, no una pregunta rápida) en este repo, ejecutar:
  ```bash
  python notify.py "<resumen breve de 1 línea de lo que se hizo>"
  ```
- No notificar por cada paso intermedio ni por preguntas triviales — solo cuando el trabajo
  de fondo terminó y el usuario podría no estar mirando.
- `notify.py` usa `HERMES_BOT_TOKEN`/`HERMES_CHAT_ID` de `.env` (vía `bot/core/config.py`) y ya
  está probado y funcionando desde Cowork.
