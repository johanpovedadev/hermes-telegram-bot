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
| `/cola` | Issues con `hermes:listo` y estado de la cola |
| `/pausar` · `/reanudar` | Frenar o seguir la cola (`/reanudar` pone las fallas en 0) |

## Cola de issues

Con `HERMES_COLA=1`, cada 10 minutos Hermes busca issues abiertos con la etiqueta `hermes:listo` en los proyectos
**habilitados** de `projects.yaml` y los trabaja uno por uno:

1. Crea un worktree en `~/.jarvis/worktrees/<proyecto>/issue-<n>` con la rama `feature/issue-<n>` desde la rama base.
   La carpeta del proyecto (donde corre producción) no se toca.
2. El agente resuelve el issue ahí. Luego Hermes corre las pruebas del proyecto.
3. Si pasan, hace un commit **local** y te pregunta por Telegram: 🚀 Subir / 🗑️ No subir.
4. Solo con 🚀 hace `git push` de la rama y te manda el enlace para abrir el PR. El PR y el merge siempre los haces tú.

Frenos: si las pruebas fallan la cola se pausa; también con 2 fallas seguidas del agente o al llegar a 5 issues en el
día. La pausa sobrevive reinicios: se sigue con `/reanudar`.

Crea las etiquetas una vez en cada repo:

```bash
for e in listo trabajando esperando-aprobacion hecho fallo rechazado; do gh label create "hermes:$e" --repo DUEÑO/REPO; done
```

Si el bot se reinicia a mitad de un issue, ese issue queda con `hermes:trabajando` y su worktree en disco: revísalo y
vuelve a ponerle `hermes:listo` (borrando antes el worktree con `git worktree remove`) si quieres que lo reintente.

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
