# Hoja de Ruta de Jarvis León

## ✅ Completado

- [x] Creación de estructura inicial de reglas y contexto.
- [x] Script principal de notificaciones a Telegram (`notify.py`).
- [x] Notificación al finalizar tarea en Open Code (`oc.py`, `oc.ps1`).
- [x] Hooks de Claude Code: notificar fin de tarea (`Stop`, `SubagentStop`) y solicitud de permisos (`Notification`).
- [x] Mensaje de prueba exitoso al celular.
- [x] Corregir causa raíz de notificaciones: `config.py` carga el `.env` desde la ruta absoluta de LionTelegram (antes dependía del directorio de trabajo, por eso fallaba desde otros proyectos).
- [x] Manejo de errores con try/catch en `notify.py` y `notify_permission.py`.
- [x] `notify_permission.py` adaptado al schema real del evento `Notification` de Claude Code (con fallback cuando falta `notification_type`, ver bug anthropics/claude-code#11964).
- [x] Hooks de Claude Code ya no ocultan errores (`2>/dev/null` → log en `hooks_errors.log`).
- [x] Integrar IA DeepSeek V4 Flash en `/chat` (vía NVIDIA NIM gratis, configurable con `AI_PROVIDER`).

## 🔄 En Proceso

- [ ] Confirmar en una sesión real de Claude Code que llega la notificación al terminar proceso (fix aplicado, falta verificación en vivo).
- [ ] Agregar `DEEPSEEK_API_KEY` (NVIDIA NIM gratis) al `.env` y correr `python test_deepseek.py` para activar `/chat`.
- [ ] Validar que el modelo responda de forma consistente durante un día completo antes de depender de él.

## ❌ Pendiente

- [ ] Integrar disparador (trigger) en más herramientas de IA (Apify/scraping).
