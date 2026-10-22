# Reglas del Proyecto: Jarvis León

> 📜 **Primero lee [`REGLAS_ECOSISTEMA.md`](REGLAS_ECOSISTEMA.md)**: reglas obligatorias de TODOS los proyectos de Johan (quién hace qué, gitflow, pruebas antes de subir, puertos libres antes de arrancar, multitenant, bots que no pierden chats, secretos). Lo de abajo es propio de este proyecto.

## 🚨 REGLAS DE DESARROLLO

1. **Código Ultra-Ligero**: El proyecto debe ser súper rápido, sin dependencias innecesarias para consumir lo mínimo de recursos.
2. **Manejo de Errores**: Todas las llamadas a la API de Telegram o webhooks deben incluir bloques try/catch para evitar que el script colapse.
3. **Formato Limpio**: Las notificaciones enviadas a Telegram deben ser claras, breves e incluir emoticonos de estado (ej: 🚀 Inicio, ✅ Éxito, ❌ Error).
