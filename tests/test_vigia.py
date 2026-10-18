"""Issue #7: el vigía avisa una sola vez por problema, avisa cuando se arregla y respeta las horas de silencio."""
import asyncio
import importlib.util
import json
import pathlib
import subprocess

import pytest

from bot.core import vigia as vg


class PM2Falso:
    def __init__(self):
        self.apps = {}
        self.caido = False

    def poner(self, nombre, status="online", reinicios=0):
        self.apps[nombre] = {"name": nombre, "pm2_env": {"status": status, "restart_time": reinicios}}

    def __call__(self, argv, timeout):
        if self.caido == "noinstalado":
            raise FileNotFoundError()
        if self.caido == "lento":
            raise subprocess.TimeoutExpired("pm2", 15)
        if self.caido:
            return 1, "", "connect ECONNREFUSED"
        return 0, json.dumps(list(self.apps.values())), ""


class Reloj:
    def __init__(self):
        self.t = 1_000_000.0
        self.h = 12

    def __call__(self):
        return self.t

    def avanzar(self, minutos):
        self.t += minutos * 60


@pytest.fixture
def ambiente(monkeypatch):
    for k in ["HERMES_VIGIA_MAX_REINICIOS", "HERMES_VIGIA_VENTANA_MIN", "HERMES_SILENCIO", "HERMES_HEARTBEAT_URL"]:
        monkeypatch.delenv(k, raising=False)
    pm2, reloj = PM2Falso(), Reloj()
    v = vg.Vigia(run=pm2, reloj=reloj, hora=lambda: reloj.h)
    return v, pm2, reloj


def test_todo_en_orden_no_avisa(ambiente):
    v, pm2, reloj = ambiente
    pm2.poner("bot-heladeria", reinicios=2)
    assert v.revisar() == []
    reloj.avanzar(5)
    assert v.revisar() == []


def test_bucle_de_reinicios_se_avisa_una_vez_y_luego_se_normaliza(ambiente):
    v, pm2, reloj = ambiente
    pm2.poner("agentes-redes", reinicios=100)
    assert v.revisar() == []  # primera foto: no sabemos cuántos fueron recientes
    reloj.avanzar(5)
    pm2.poner("agentes-redes", status="online", reinicios=1800)  # el caso real: ~370.000 al día
    m = v.revisar()
    assert len(m) == 1 and m[0].startswith("🔁 agentes-redes está en bucle: 1700 reinicios") and "pm2 stop agentes-redes" in m[0]
    reloj.avanzar(5)
    pm2.poner("agentes-redes", reinicios=3500)
    assert v.revisar() == [], "un mismo problema se avisa UNA sola vez"
    reloj.avanzar(11)
    assert v.revisar() == ["✅ agentes-redes se normalizó"]


def test_pocos_reinicios_no_son_bucle(ambiente):
    v, pm2, reloj = ambiente
    pm2.poner("bot-mascotas", reinicios=0)
    v.revisar()
    reloj.avanzar(5)
    pm2.poner("bot-mascotas", reinicios=3)
    assert v.revisar() == []


def test_app_caida_y_recuperada(ambiente):
    v, pm2, reloj = ambiente
    pm2.poner("bot-heladeria", status="errored", reinicios=10)
    m = v.revisar()
    assert m == ["🔴 bot-heladeria está errored en PM2. Revisa: pm2 logs bot-heladeria --lines 30"]
    reloj.avanzar(5)
    assert v.revisar() == []
    pm2.poner("bot-heladeria", status="online", reinicios=10)
    reloj.avanzar(5)
    assert v.revisar() == ["✅ bot-heladeria se normalizó"]


@pytest.mark.parametrize("falla", [True, "noinstalado", "lento"])
def test_pm2_no_responde(ambiente, falla):
    v, pm2, reloj = ambiente
    pm2.caido = falla
    m = v.revisar()
    assert len(m) == 1 and m[0].startswith("🔴 PM2 no responde")
    reloj.avanzar(5)
    assert v.revisar() == []
    pm2.caido = False
    reloj.avanzar(5)
    assert v.revisar() == ["✅ PM2 volvió a responder"]


def test_horas_de_silencio(ambiente, monkeypatch):
    monkeypatch.setenv("HERMES_SILENCIO", "22-7")
    pm2, reloj = PM2Falso(), Reloj()
    v = vg.Vigia(run=pm2, reloj=reloj, hora=lambda: reloj.h)
    reloj.h = 23
    pm2.poner("bot-pilates", status="stopped")
    assert v.revisar()[0].startswith("🔴 bot-pilates"), "lo crítico se avisa aunque sea de noche"
    pm2.poner("bot-pilates", status="online")
    reloj.avanzar(5)
    assert v.revisar() == [], "la recuperación (no crítica) espera a la mañana"
    reloj.h = 7
    reloj.avanzar(5)
    m = v.revisar()
    assert len(m) == 1 and m[0].startswith("🌅 Mientras estabas en silencio") and "bot-pilates se normalizó" in m[0]


@pytest.mark.parametrize("raw,esperado", [("22-7", (22, 7)), ("8-18", (8, 18)), ("", None), ("x", None), ("5-5", None), ("25-3", None)])
def test_parse_silencio(raw, esperado):
    assert vg.parse_silencio(raw) == esperado


def test_en_silencio_cruzando_medianoche():
    assert vg.en_silencio(23, (22, 7)) and vg.en_silencio(3, (22, 7)) and not vg.en_silencio(7, (22, 7))
    assert vg.en_silencio(9, (8, 18)) and not vg.en_silencio(18, (8, 18))


def test_latido_externo(ambiente, monkeypatch):
    monkeypatch.setenv("HERMES_HEARTBEAT_URL", "https://hc-ping.com/xyz")
    pm2, reloj = PM2Falso(), Reloj()
    visitadas = []
    v = vg.Vigia(run=pm2, reloj=reloj, hora=lambda: 12, ping_fn=lambda u: visitadas.append(u) or True)
    v.revisar()
    assert visitadas == ["https://hc-ping.com/xyz"] and v.ultimo_latido_ok is True


@pytest.mark.asyncio
async def test_bucle_envia_y_no_se_cae_si_telegram_falla(ambiente):
    v, pm2, reloj = ambiente
    pm2.caido = True
    enviados = []

    async def notify(t):
        enviados.append(t)
        raise RuntimeError("telegram caído")

    await vg.bucle_vigia(v, notify, cada_s=0, veces=2)
    assert len(enviados) == 1


def test_bot_arranca_el_vigia(monkeypatch):
    spec = importlib.util.spec_from_file_location("bot_main_vigia", pathlib.Path(__file__).resolve().parents[1] / "bot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    creadas = []

    class FakeApp:
        bot = None

        def create_task(self, coro):
            creadas.append(coro)
            coro.close()

    monkeypatch.delenv("HERMES_VIGIA", raising=False)
    monkeypatch.setenv("HERMES_CHAT_ID", "5534032418")
    asyncio.run(mod.crear_post_init({5534032418})(FakeApp()))
    assert len(creadas) == 1
    monkeypatch.setenv("HERMES_VIGIA", "0")
    asyncio.run(mod.crear_post_init({5534032418})(FakeApp()))
    assert len(creadas) == 1, "HERMES_VIGIA=0 lo apaga"
