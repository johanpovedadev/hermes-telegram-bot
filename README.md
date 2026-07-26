# Jarvis León Bot

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
