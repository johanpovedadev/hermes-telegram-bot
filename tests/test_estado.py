"""Issue #6: /estado con datos reales y sin IA. Cada fuente falla por separado sin romper el mensaje."""
import json
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from bot.core import estado

AHORA = 1_800_000_000_000


def _pm2(apps):
    return json.dumps([{"name": n, "pm2_env": {"status": st, "restart_time": r, "pm_uptime": AHORA - up_s * 1000}} for n, st, r, up_s in apps])


def run_falso(respuestas):
    def run(argv, timeout):
        clave = argv[0] if argv[0] != "gh" else f"gh:{argv[4]}"
        r = respuestas.get(clave)
        if isinstance(r, Exception):
            raise r
        return r if r is not None else (1, "", "sin respuesta")
    return run


def test_pm2_todo_en_orden_y_app_caida():
    run = run_falso({"pm2": (0, _pm2([("bot-heladeria", "online", 0, 7200), ("agentes-redes", "errored", 3556315, 0), ("django", "online", 2, 90000)]), "")})
    lineas = estado.seccion_pm2(run, AHORA)
    assert lineas == ["🔴 agentes-redes · errored · 3556315 reinicios", "🟢 bot-heladeria · 2h", "🟢 django · 1d · 2 reinicios"]


@pytest.mark.parametrize("respuesta,esperado", [
    ((1, "", "connect ECONNREFUSED"), "PM2 no responde (connect ECONNREFUSED)"),
    (FileNotFoundError(), "no está instalado"),
    (subprocess.TimeoutExpired("pm2", 15), "más de 15 s"),
    ((0, "basura", ""), "no es JSON"),
    ((0, "[]", ""), "ninguna app"),
])
def test_pm2_que_no_responde_se_dice_claro(respuesta, esperado):
    lineas = estado.seccion_pm2(run_falso({"pm2": respuesta}), AHORA)
    assert len(lineas) == 1 and esperado in lineas[0]


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


def test_bots_con_servidor_real():
    srv = HTTPServer(("127.0.0.1", 0), _Health)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    vivo = srv.server_address[1]
    libre = socket.socket(); libre.bind(("127.0.0.1", 0)); muerto = libre.getsockname()[1]; libre.close()
    servicios = [
        {"name": "bot-heladeria", "port": vivo, "env": "LION_STATUS_PORT"},
        {"name": "bot-mascotas", "port": muerto, "env": "LION_STATUS_PORT"},
        {"name": "admin-panel", "port": vivo, "env": "PORT"},
        {"name": "lion-platform-api", "port": muerto, "env": "PORT", "manual": True},
    ]
    try:
        lineas = estado.seccion_bots(servicios)
    finally:
        srv.shutdown()
    assert f"🟢 bot-heladeria responde ({vivo})" in lineas
    assert f"🔴 bot-mascotas no responde ({muerto})" in lineas
    assert f"🟢 admin-panel :{vivo}" in lineas
    assert not any("lion-platform-api" in l for l in lineas), "los servicios manuales no se vigilan"


def test_sin_registro_de_puertos(tmp_path):
    assert estado.cargar_puertos(str(tmp_path)) is None
    assert "Sin registro" in estado.seccion_bots(None)[0]
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "ports.json").write_text(json.dumps({"services": [{"name": "x", "port": 1, "env": "PORT"}]}))
    assert estado.cargar_puertos(str(tmp_path))[0]["name"] == "x"


def test_ci():
    run = run_falso({
        "gh:o/verde": (0, json.dumps([{"status": "completed", "conclusion": "success", "headBranch": "develop"}]), ""),
        "gh:o/rojo": (0, json.dumps([{"status": "completed", "conclusion": "failure", "headBranch": "feature/x"}]), ""),
        "gh:o/corre": (0, json.dumps([{"status": "in_progress", "conclusion": None, "headBranch": "develop"}]), ""),
        "gh:o/vacio": (0, "[]", ""),
        "gh:o/privado": (1, "", "HTTP 404"),
    })
    l = estado.seccion_ci(["o/verde", "o/rojo", "o/corre", "o/vacio", "o/privado"], run)
    assert l == ["🟢 verde: verde (develop)", "🔴 rojo: failure (feature/x)", "🟡 corre: corriendo (develop)", "⚪ o/vacio: sin ejecuciones", "⚪ o/privado: sin datos (HTTP 404)"]
    assert "no está instalado" in estado.seccion_ci(["o/x"], run_falso({"gh:o/x": FileNotFoundError()}))[0]


def test_mensaje_completo_y_fuentes_que_fallan_por_separado(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "ports.json").write_text(json.dumps({"services": [{"name": "bot-heladeria", "port": 8096, "env": "LION_STATUS_PORT"}]}))
    saas = SimpleNamespace(nombre="saas-bot", repo="o/saas", carpeta=str(tmp_path))
    registro = SimpleNamespace(proyectos=[saas], obtener=lambda n: saas if n == "saas-bot" else None)
    manager = SimpleNamespace(corriendo=lambda: {"agentvents": 7})
    run = run_falso({"pm2": FileNotFoundError(), "gh:o/saas": (0, json.dumps([{"status": "completed", "conclusion": "success", "headBranch": "develop"}]), "")})
    txt = estado.construir_estado(registro, manager, run=run, health=lambda u: True, ahora_ms=AHORA)
    assert "PM2 no está instalado" in txt and "🟢 bot-heladeria responde (8096)" in txt and "🟢 saas: verde" in txt
    assert "🟡 Trabajando: agentvents #7" in txt


def test_una_seccion_que_explota_no_tumba_el_comando():
    registro = SimpleNamespace(proyectos=[], obtener=lambda n: None)

    def health_roto(u):
        raise RuntimeError("x")
    txt = estado.construir_estado(registro, None, run=run_falso({"pm2": (0, "[]", "")}), health=health_roto, ahora_ms=AHORA)
    assert "Hermes" in txt and "🟢 Libre" in txt and "Sin registro" in txt


@pytest.mark.asyncio
async def test_comando_estado(mock_update, mock_context, monkeypatch):
    import bot.handlers.run as run
    monkeypatch.setattr("bot.core.estado.construir_estado", lambda reg, man: "🤖 Hermes — estado\nok")
    await run.estado(mock_update, mock_context)
    assert mock_update.message.reply_text.call_args[0][0].startswith("🤖 Hermes")
    assert "parse_mode" not in mock_update.message.reply_text.call_args.kwargs
