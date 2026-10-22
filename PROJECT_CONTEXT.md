# Contexto del Proyecto: Jarvis León

## 🎯 Objetivo

Sistema de alertas y notificaciones automáticas a Telegram para confirmar la finalización de tareas de IA (Open Code, Claude Code, scripts de scraping en Apify).

## 🏗️ Componentes Clave

- Módulo de Notificaciones: `notify.py` envía mensajes a la Telegram Bot API (reutilizado por `oc.py`, `oc.ps1` y los hooks de Claude Code).

- Hooks de Claude Code: configurados en `~/.claude/settings.json` con eventos `Stop`, `SubagentStop` y `Notification` para notificar al terminar tareas o solicitar permisos.

- Notificación de permisos: `notify_permission.py` lee el JSON del hook `Notification` por stdin y avisa cuando Claude Code pide un permiso.

- Configuración: Variables de entorno (.env) para `HERMES_BOT_TOKEN` y `HERMES_CHAT_ID` (ver `bot/core/config.py`).
