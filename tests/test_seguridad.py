"""Issue #3: Hermes solo obedece a los chats permitidos (prueba de punta a punta con python-telegram-bot real)."""
import importlib.util
import json
import pathlib

import pytest
from telegram import Update, User
from telegram.ext import ApplicationBuilder, ApplicationHandlerStop, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot.core.security import GUARD_GROUP, build_guard_handler, describe_update, make_audit_writer, make_guard, parse_allowed

PERMITIDO = 5534032418
EXTRANO = 999000111


def _msg(chat_id, text=None, voice=False):
    m = {"message_id": 1, "date": 0, "chat": {"id": chat_id, "type": "private"}, "from": {"id": chat_id, "is_bot": False, "first_name": "x", "username": "u"}}
    if text is not None:
        m["text"] = text
        if text.startswith("/"):
            m["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    if voice:
        m["voice"] = {"file_id": "f", "file_unique_id": "u", "duration": 2}
    return {"update_id": 1, "message": m}


def _cb(chat_id, data="aprobar:abc"):
    return {"update_id": 2, "callback_query": {"id": "q", "chat_instance": "c", "data": data,
            "from": {"id": chat_id, "is_bot": False, "first_name": "x"},
            "message": {"message_id": 5, "date": 0, "chat": {"id": chat_id, "type": "private"}, "text": "t"}}}


@pytest.fixture
def app_con_guardia(tmp_path):
    audit_file = tmp_path / "seguridad.jsonl"
    app = ApplicationBuilder().token("123456:TEST-SIN-RED").build()
    ejecutados = []

    async def run(update, context):
        ejecutados.append(("run", context.args))

    async def boton(update, context):
        ejecutados.append(("boton", update.callback_query.data))

    async def voz(update, context):
        ejecutados.append(("voz", None))

    async def texto(update, context):
        ejecutados.append(("texto", update.message.text))

    app.add_handler(build_guard_handler({PERMITIDO}, make_audit_writer(str(audit_file))), group=GUARD_GROUP)
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CallbackQueryHandler(boton))
    app.add_handler(MessageHandler(filters.VOICE, voz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto))
    # Sin red: initialize() real llamaría a get_me de Telegram. Para procesar updates locales basta con marcarla.
    app._initialized = True
    app.bot._bot_user = User(id=123456, first_name="Jarvis", is_bot=True, username="JarvisLeonAI_bot")
    app.bot._bot_initialized = True
    return app, ejecutados, audit_file


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,esperado", [
    (_msg(PERMITIDO, "/run empanadas hola"), "run"),
    (_cb(PERMITIDO), "boton"),
    (_msg(PERMITIDO, voice=True), "voz"),
    (_msg(PERMITIDO, "hola"), "texto"),
])
async def test_chat_permitido_si_ejecuta(app_con_guardia, payload, esperado):
    app, ejecutados, audit_file = app_con_guardia
    await app.process_update(Update.de_json(payload, app.bot))
    assert [e[0] for e in ejecutados] == [esperado]
    assert not audit_file.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,intento", [
    (_msg(EXTRANO, "/run empanadas rm -rf todo"), "texto:/run empanadas rm -rf todo"),
    (_cb(EXTRANO, "aprobar:xyz"), "boton:aprobar:xyz"),
    (_msg(EXTRANO, voice=True), "voz"),
    (_msg(EXTRANO, "hola"), "texto:hola"),
])
async def test_chat_no_permitido_no_ejecuta_nada_y_queda_auditado(app_con_guardia, payload, intento):
    app, ejecutados, audit_file = app_con_guardia
    await app.process_update(Update.de_json(payload, app.bot))
    assert ejecutados == [], "ningún handler debe correr para un chat no permitido"
    entrada = json.loads(audit_file.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entrada["evento"] == "bloqueado" and entrada["chat_id"] == EXTRANO and entrada["intento"] == intento


@pytest.mark.asyncio
async def test_update_sin_chat_se_bloquea():
    vistos = []
    guard = make_guard({PERMITIDO}, vistos.append)

    class SinChat:
        effective_chat = None
        effective_user = None
        callback_query = None
        effective_message = None

    with pytest.raises(ApplicationHandlerStop):
        await guard(SinChat(), None)
    assert vistos and vistos[0]["chat_id"] is None and vistos[0]["intento"] == "otro"


def test_parse_allowed():
    assert parse_allowed("5534032418, 123 ;456") == {5534032418, 123, 456}
    assert parse_allowed("") == set() and parse_allowed(None) == set()
    with pytest.raises(ValueError, match="no es un número"):
        parse_allowed("5534032418,@johan")


def test_auditoria_nunca_tumba_al_bot(tmp_path):
    bloqueado = tmp_path / "archivo"
    bloqueado.write_text("x")
    write = make_audit_writer(str(bloqueado / "no-se-puede.jsonl"))  # el "directorio" es un archivo
    write({"a": 1})  # no lanza


def _cargar_bot_py():
    spec = importlib.util.spec_from_file_location("bot_main_seg", pathlib.Path(__file__).resolve().parents[1] / "bot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("valor", ["", "   ", "abc"])
def test_sin_lista_valida_el_bot_no_arranca(monkeypatch, valor):
    mod = _cargar_bot_py()
    monkeypatch.setattr(mod, "BOT_TOKEN", "123:abc")
    monkeypatch.setattr(mod, "ALLOWED_CHAT_IDS_RAW", valor)
    with pytest.raises(SystemExit):
        mod.main()


def test_la_guardia_queda_antes_que_todo(monkeypatch):
    mod = _cargar_bot_py()
    grupos = []

    class FakeApp:
        def add_handler(self, h, group=0):
            grupos.append((group, type(h).__name__))

        def run_polling(self):
            pass

    class B:
        def token(self, t):
            return self

        def build(self):
            return FakeApp()

    monkeypatch.setattr(mod, "BOT_TOKEN", "123:abc")
    monkeypatch.setattr(mod, "ALLOWED_CHAT_IDS_RAW", str(PERMITIDO))
    monkeypatch.setattr(mod, "ApplicationBuilder", lambda: B())
    mod.main()
    assert grupos[0] == (GUARD_GROUP, "TypeHandler")
    assert all(g > GUARD_GROUP for g, _ in grupos[1:])
