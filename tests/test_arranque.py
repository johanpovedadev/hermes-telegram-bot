"""Issue #4: lo que está en GitHub tiene que arrancar (antes bot.py importaba archivos que solo existían en el PC)."""
import io
import json
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_bot_py_importa_y_registra_todos_los_comandos(monkeypatch):
    monkeypatch.setenv("HERMES_BOT_TOKEN", "123456:TEST-TOKEN-SIN-RED")
    import bot as _pkg  # noqa: F401  (paquete bot/)
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("bot_main", pathlib.Path(__file__).resolve().parents[1] / "bot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    registrados = []

    class FakeApp:
        def add_handler(self, h, group=0):
            registrados.append(h)

        def run_polling(self):
            pass

    builder = MagicMock()
    builder.token.return_value.build.return_value = FakeApp()
    monkeypatch.setattr(mod, "BOT_TOKEN", "123456:TEST-TOKEN-SIN-RED")
    monkeypatch.setattr(mod, "ALLOWED_CHAT_IDS_RAW", "5534032418")
    monkeypatch.setattr(mod, "ApplicationBuilder", lambda: builder)
    mod.main()
    comandos = {c for h in registrados for c in getattr(h, "commands", [])}
    for esperado in ["start", "status", "proyectos", "run", "chat", "historial"]:
        assert esperado in comandos, f"falta /{esperado}"


def test_sin_token_el_bot_no_arranca(monkeypatch, capsys):
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("bot_main2", pathlib.Path(__file__).resolve().parents[1] / "bot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "BOT_TOKEN", "")
    with pytest.raises(SystemExit) as salida:
        mod.main()
    assert salida.value.code == 78, "78 = PM2 no lo reinicia en bucle (stop_exit_codes)"


class TestIA:
    def test_apagada_por_defecto(self, monkeypatch):
        import bot.core.ai as ai
        monkeypatch.setattr(ai, "AI_PROVIDER", "none")
        with pytest.raises(RuntimeError, match="no configurada"):
            ai.preguntar_a_ia("hola")

    def test_falta_clave_o_modelo(self, monkeypatch):
        import bot.core.ai as ai
        monkeypatch.setattr(ai, "AI_PROVIDER", "deepseek")
        monkeypatch.setattr(ai, "DEEPSEEK_API_KEY", "")
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            ai.preguntar_a_ia("hola")
        monkeypatch.setattr(ai, "DEEPSEEK_API_KEY", "k")
        monkeypatch.setattr(ai, "DEEPSEEK_MODEL", "")
        with pytest.raises(RuntimeError, match="DEEPSEEK_MODEL"):
            ai.preguntar_a_ia("hola")

    def test_respuesta_del_proveedor(self, monkeypatch):
        import bot.core.ai as ai
        monkeypatch.setattr(ai, "AI_PROVIDER", "deepseek")
        monkeypatch.setattr(ai, "DEEPSEEK_API_KEY", "k")
        monkeypatch.setattr(ai, "DEEPSEEK_MODEL", "modelo-x")
        enviado = {}

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout):
            enviado["url"] = req.full_url
            enviado["body"] = json.loads(req.data)
            enviado["auth"] = req.headers.get("Authorization")
            return Resp(json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode())

        monkeypatch.setattr(ai.urllib.request, "urlopen", fake_urlopen)
        assert ai.preguntar_a_ia("hola") == "OK"
        assert enviado["url"].endswith("/chat/completions")
        assert enviado["body"]["model"] == "modelo-x"
        assert enviado["auth"] == "Bearer k"


class TestChat:
    @pytest.mark.asyncio
    async def test_sin_pregunta_muestra_uso(self, mock_update, mock_context):
        from bot.handlers.chat import chat
        mock_context.args = []
        await chat(mock_update, mock_context)
        assert "Uso:" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_ia_no_configurada_avisa(self, mock_update, mock_context, monkeypatch):
        import bot.handlers.chat as ch
        mock_context.args = ["hola"]

        def falla(_):
            raise RuntimeError("IA no configurada")

        monkeypatch.setattr(ch, "preguntar_a_ia", falla)
        await ch.chat(mock_update, mock_context)
        assert "⚠️" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_responde(self, mock_update, mock_context, monkeypatch):
        import bot.handlers.chat as ch
        mock_context.args = ["resume", "LionCore"]
        monkeypatch.setattr(ch, "preguntar_a_ia", lambda q: f"resp:{q}")
        await ch.chat(mock_update, mock_context)
        assert mock_update.message.reply_text.call_args[0][0] == "resp:resume LionCore"


class TestNotifyPermission:
    def _run(self, monkeypatch, payload):
        import notify_permission as npm
        importlib.reload(npm)
        enviados = []

        async def fake_notificar(m):
            enviados.append(m)

        monkeypatch.setattr(npm, "notificar", fake_notificar)
        monkeypatch.setattr(npm, "log_debug", lambda *_: None)
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload) if payload is not None else "no-json"))
        npm.main()
        return enviados

    def test_permiso_avisa(self, monkeypatch):
        out = self._run(monkeypatch, {"notification_type": "permission_prompt", "message": "Permitir Bash"})
        assert out and "Permiso requerido" in out[0] and "Permitir Bash" in out[0]

    def test_tipo_desconocido_se_ignora(self, monkeypatch):
        assert self._run(monkeypatch, {"notification_type": "otro"}) == []

    def test_json_invalido_usa_permiso_por_defecto(self, monkeypatch):
        out = self._run(monkeypatch, None)
        assert out and "Necesita tu atencion" in out[0]


def test_ecosystem_de_pm2_seguro():
    import json, pathlib, subprocess
    raiz = pathlib.Path(__file__).resolve().parents[1]
    js = "const c=require(process.argv[1]);console.log(JSON.stringify(c.apps))"
    try:
        apps = json.loads(subprocess.run(["node", "-e", js, str(raiz / "ecosystem.config.js")], capture_output=True, text=True, check=True).stdout)
    except FileNotFoundError:
        import pytest
        pytest.skip("node no está instalado")
    app = apps[0]
    assert app["name"] == "hermes" and app["script"] == "bot.py"
    assert app["env"]["PYTHONUTF8"] == "1", "sin esto los emojis tumban a Hermes en Windows"
    assert 78 in app["stop_exit_codes"] and app["max_restarts"] <= 10 and app["min_uptime"]


def test_consola_cp1252_no_tumba_el_bot(monkeypatch):
    import importlib.util, io, pathlib, sys
    spec = importlib.util.spec_from_file_location("bot_main3", pathlib.Path(__file__).resolve().parents[1] / "bot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    crudo = io.BytesIO()
    consola = io.TextIOWrapper(crudo, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", consola)
    mod._consola_utf8()
    print("\u26a1 Jarvis León iniciado")
    consola.flush()
    assert "⚡".encode("utf-8") in crudo.getvalue()
