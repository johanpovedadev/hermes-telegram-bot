# Reglas del ecosistema Lion (todos los proyectos de Johan)

> **Aplica a TODOS los proyectos, a los que ya existen y a los que se creen.** Cualquier persona o agente de IA que
> trabaje en uno de estos repos las sigue antes que cualquier otra costumbre. Si una regla de un proyecto (su
> `AGENTS.md`) es más estricta, gana la del proyecto. Si se contradicen, se le pregunta a Johan.
>
> Este archivo es **el mismo en todos los repos**. Se cambia en todos a la vez; la copia de referencia vive en
> `saas-bot/REGLAS_ECOSISTEMA.md`. Última actualización: 22 oct 2026.

## 0. Quién hace qué (regla del 22 oct 2026)

**Johan pide y prueba. Los agentes (Claude, Hermes) hacen el resto del proceso.**

| Paso | Quién |
|---|---|
| Pedir el cambio (en Telegram con `/pedir`, en un chat o en un issue) | Johan |
| Escribir el issue con criterio de aceptación | Agente |
| Rama `feature/*` desde `develop`, código, pruebas, commits convencionales | Agente |
| Revisión automática del diff contra estas reglas | Agente revisor |
| Push de la rama y PR a `develop` con descripción clara | Agente |
| **Probar a mano** con los pasos de "Cómo probar" del PR | **Johan** |
| Merge del PR a `develop`, solo después del ✅ de Johan | Agente |
| Pasar `develop` a `main` (producción) | **Johan** |

Johan sigue decidiendo siempre, y ningún agente lo hace por su cuenta:
- Pasar algo a producción (`main`/`master`, `pm2 restart` de bots en vivo).
- Gastar tokens o plata reales, borrar datos, tocar un negocio que no se pidió.
- Secretos y credenciales: los pone Johan en `.env`; los agentes nunca los ven ni los piden.

Excepción: en las **pruebas técnicas de procesos de selección** (por ejemplo `trycore-evm-project`, `todo-api-hono`)
mandan las reglas propias del repo: ahí los agentes no hacen commits, push ni merge, porque el trabajo lo evalúan como
de Johan.

Para que los repos sirvan de portafolio: commits `feat:`/`fix:`/`test:`/`docs:`, un PR por cambio con "Qué cambia",
"Por qué" y "Cómo probar", CI en verde y un README que explique cómo correr el proyecto.

## 1. Trabajo con el código

1. **Gitflow siempre.** Las ramas `feature/*`, `fix/*` y `docs/*` salen de `develop` y vuelven a `develop` por PR. Solo
   `develop` pasa a `main`/`master`. Nunca se commitea directo a `main`/`master` ni a `develop`. El merge a `develop`
   lo hace el agente tras la prueba de Johan; el paso a `main` lo hace Johan (sección 0).
2. **Pruebas antes de subir.** No se hace push sin correr la suite del proyecto en verde. Todo cambio trae su prueba.
   Toda falla real (un chat perdido, un error en producción) se vuelve primero una prueba que falla y después se
   corrige.
3. **Nada de parche sobre parche.** Si el mismo tipo de falla vuelve, se corrige la causa: el diseño, no el síntoma.
4. **Las pruebas simulan la IA.** Gastar tokens reales es decisión de Johan y se declara a propósito
   (`ALLOW_REAL_AI=1`). Ninguna prueba, agente ni script los gasta por su cuenta.
5. **Documentar lo que se decide:** requisitos en `docs/requirements.md` y decisiones en
   `docs/architecture-decisions.md` (ADR), o en su equivalente del proyecto. Cada regla nueva lleva su origen: la
   fecha y qué pasó.

## 2. Arrancar servicios (regla del 17 oct 2026)

6. **Validar que el puerto está libre ANTES de arrancar cualquier servicio**, en cualquier proyecto. Los puertos de
   todos los proyectos viven en un solo registro: `saas-bot/config/ports.json`.
   - Puerto nuevo: `node scripts/check-ports.js --new <puerto>` (o `--suggest <desde>`). Debe estar libre y sin
     dueño, y se registra ANTES de usarlo.
   - Antes de arrancar: `node scripts/check-ports.js --app <servicio>`.
   - Estado de todos: `npm run ports` (desde saas-bot).
7. **Nada corre a mano en PM2 ni desde una rama de trabajo.** Todo servicio persistente va en `ecosystem.config.js`,
   con `min_uptime`, `max_restarts` ≤ 10 y `stop_exit_codes: [78]`, y se arranca con `npm run start:safe -- <app>`.
   Origen: `agentes-redes` apuntaba a un archivo de otra rama, se reinició unos 3,5 millones de veces, llenó 3 GB de
   logs y el 17 oct tumbó a PM2 con todos los bots.
8. **Todo servidor atiende `EADDRINUSE`:** mensaje claro y `process.exit(78)` (o su equivalente en el lenguaje del
   proyecto). Nunca un bucle de caídas.

## 3. Multitenant y licencias

9. **Aislamiento estricto:** toda tabla o dato de un cliente lleva su `tenant_id`/`BUSINESS_KEY` y toda lectura
   filtra por él. Nunca se mezclan datos de dos negocios, ni en una respuesta ni en un archivo compartido.
10. **Licencias por producto** (Lion Platform: `CRM`, `BOT`, `SOCIAL`...). Lion Platform es la única fuente de
    verdad. Si no se pueden verificar, se **falla cerrado**.
11. **Un cambio para un negocio no toca a los demás:** las funciones nuevas llegan apagadas por defecto y se encienden
    por negocio (flag en `.env.<negocio>`), con canario por número antes de abrirlas a todos.

## 4. Bots y agentes de venta

12. **El objetivo es cerrar el pedido.** El bot entiende la **intención** del cliente aunque escriba mal
    (personas mayores, poca lectura). Si el cliente lo pide explícito, el bot actúa. Si solo pregunta, responde y
    confirma ("¿Lo quieres? Sí / No"). Si duda, confirma. Nunca descarta en silencio lo que el cliente dijo.
13. **Ningún chat se pierde.** Si el bot no entiende o se repite, pasa a una persona y avisa. Si el cliente deja de
    responder, el bot le hace seguimiento y luego avisa al negocio. Ver `saas-bot/bot-wasap/docs/red_de_seguridad_y_revision_diaria.md`.
14. **Mensajes cortos y fáciles.** Una sola pregunta por mensaje, con opciones concretas y en lenguaje del cliente.
15. **Los avisos van a quien atiende el negocio**, en lenguaje de negocio y con el link al chat. Lo técnico va solo al
    admin de sistema. Ejemplo: en Mundo Helados los avisos van a Isa y no a Johan.
16. **No tocar un negocio que no se pidió** (ej. mascotas) sin que Johan lo diga explícitamente.

## 5. Datos y seguridad

17. **Secretos solo en `.env` local o en GitHub Secrets.** Nunca en el código, los commits, los logs ni los chats.
    Una clave expuesta se revoca.
18. **No se guarda lo que escriben los clientes finales más allá de lo necesario** (ADR-014 de saas-bot). Los
    registros de métricas guardan tipos de evento, no textos.
19. **Solo APIs oficiales** (Meta Graph, YouTube Data, WhatsApp...). Nada de scraping sin una decisión documentada.
20. **Dato ausente = `null`, nunca 0.** Ningún número sale inventado por un modelo: sale de la base o de una API.

## 6. Proyecto nuevo: checklist obligatorio

Antes del primer commit de un proyecto nuevo:

- [ ] Copiar **este archivo** (`REGLAS_ECOSISTEMA.md`) a la raíz del proyecto.
- [ ] Crear su `AGENTS.md` con lo propio del proyecto y un enlace a este archivo al inicio.
- [ ] Crear las ramas `main` y `develop`, y un CI que corra las pruebas en cada PR.
- [ ] Agregar `.env.example` sin secretos y `.env` en `.gitignore`.
- [ ] Si escucha en un puerto: registrarlo en `saas-bot/config/ports.json` con `check-ports.js --new` y manejar
      `EADDRINUSE` con salida 78.
- [ ] Si corre permanente: agregarlo al `ecosystem.config.js` (no `pm2 start` a mano).
- [ ] Si es multitenant: `tenant_id` en todo, licencia verificada y falla cerrada.
- [ ] Agregarlo a la tabla de abajo (en todos los repos).

## 7. Proyectos del ecosistema

| Proyecto | Repo | Qué es | Puertos (`config/ports.json`) |
|---|---|---|---|
| saas-bot | johanpovedadev/saas-bot | Bots de WhatsApp multitenant (heladería, mascotas, pescadería, pilates, finanzas), Django y panel admin | 8000–8002, 8096–8103, 4000 |
| AGentVents | johanpovedadev/AGentVents | Agente de redes y ventas (métricas, informes, CRM) | 3100 (bandeja de redes) |
| lion-platform-api | johanpovedadev/lion-platform-api | API multitenant de Lion Platform (Java/Spring), licencias por producto | 8080 / 8081 |
| lion-platform-web | johanpovedadev/lion-platform-web | Frontend de Lion Platform (React/Vite) | 5173 |
| LionCore | johanpovedadev/LionCore | POS SaaS offline-first | — |
| Jarvis León | johanpovedadev/hermes-telegram-bot | Bot de Telegram de Johan (alertas y notificaciones) | — |
| pythonauto | johanpovedadev/pythonauto | Scripts de automatización y scraping de prospectos | — |
| social-bot | johanpovedadev/AGentVents (carpeta `social-bot/`) | Bot de comentarios y DMs de Instagram/Facebook | 8300 |
| ai-opportunity-hunter, todo-api-hono, pilatesapp, Portafolio, Mundo-Helados, maxtortecnoreparaciones, trycore-evm-project | johanpovedadev/… | Proyectos de apoyo, portafolio y pruebas | — |
