"""Issue #5: administrador de trabajos con procesos reales (sin agente real: comandos de Python)."""
import asyncio
import sys
from types import SimpleNamespace

import pytest

from bot.core import jobs
from bot.core.jobs import JobManager, JobStore, ProyectoOcupado

PY = sys.executable


def _proyecto(tmp_path, pruebas="", nombre="p"):
    d = tmp_path / nombre
    d.mkdir(exist_ok=True)
    return SimpleNamespace(nombre=nombre, carpeta=str(d), pruebas=pruebas)


@pytest.fixture
def avisos():
    lista = []

    async def notify(t):
        lista.append(t)
    notify.lista = lista
    return notify


@pytest.fixture
def agente_python(monkeypatch):
    """El 'agente' es un python -c con el prompt como código: permite simular éxito, fallo y demora."""
    monkeypatch.setitem(jobs.AGENTES, "fake", lambda prompt: [PY, "-c", prompt])


@pytest.mark.asyncio
async def test_exito_corre_las_pruebas_y_registra(tmp_path, avisos, agente_python):
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    p = _proyecto(tmp_path, pruebas=f'"{PY}" -c "print(1)"')
    jid = m.iniciar(p, "print('hecho')", avisos, agente="fake")
    await m.esperar(jid)
    t = m.store.obtener(jid)
    assert t.estado == "ok" and t.codigo == 0 and t.pruebas == "ok" and "hecho" in t.salida and t.duracion_s is not None
    assert avisos.lista[0].startswith("▶️") and avisos.lista[-1].startswith("✅") and "Tests: OK" in avisos.lista[-1]


@pytest.mark.asyncio
async def test_pruebas_rojas_es_fallo(tmp_path, avisos, agente_python):
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    p = _proyecto(tmp_path, pruebas=f'"{PY}" -c "import sys; print(\'2 failed\'); sys.exit(1)"')
    jid = m.iniciar(p, "print('ok')", avisos, agente="fake")
    await m.esperar(jid)
    t = m.store.obtener(jid)
    assert t.estado == "fallo" and t.pruebas == "fallo"
    assert "pruebas fallaron" in avisos.lista[-1] and "2 failed" in avisos.lista[-1]


@pytest.mark.asyncio
async def test_agente_que_falla(tmp_path, avisos, agente_python):
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    jid = m.iniciar(_proyecto(tmp_path), "import sys; sys.stderr.write('boom'); sys.exit(3)", avisos, agente="fake")
    await m.esperar(jid)
    t = m.store.obtener(jid)
    assert t.estado == "fallo" and t.codigo == 3 and t.pruebas is None and "boom" in t.error
    assert "código 3" in avisos.lista[-1] and "boom" in avisos.lista[-1]


@pytest.mark.asyncio
async def test_timeout_mata_el_proceso(tmp_path, avisos, agente_python, monkeypatch):
    monkeypatch.setenv("HERMES_AGENT_TIMEOUT_MIN", str(0.5 / 60))  # medio segundo
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    marca = tmp_path / "siguio_vivo.txt"
    codigo = f"import time; time.sleep(3); open(r'{marca}','w').write('x')"
    jid = m.iniciar(_proyecto(tmp_path), codigo, avisos, agente="fake")
    await m.esperar(jid)
    await asyncio.sleep(3)
    assert m.store.obtener(jid).estado == "timeout" and avisos.lista[-1].startswith("⏰")
    assert not marca.exists(), "el agente vencido debe quedar muerto, no seguir corriendo"


@pytest.mark.asyncio
async def test_candado_por_proyecto_y_proyectos_distintos_en_paralelo(tmp_path, avisos, agente_python):
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    a, b = _proyecto(tmp_path, nombre="a"), _proyecto(tmp_path, nombre="b")
    j1 = m.iniciar(a, "import time; time.sleep(0.5)", avisos, agente="fake")
    with pytest.raises(ProyectoOcupado):
        m.iniciar(a, "print(1)", avisos, agente="fake")
    j2 = m.iniciar(b, "print(1)", avisos, agente="fake")
    assert set(m.corriendo()) == {"a", "b"}
    await m.esperar(j1)
    await m.esperar(j2)
    assert m.corriendo() == {}
    j3 = m.iniciar(a, "print(1)", avisos, agente="fake")  # liberado: se puede de nuevo
    await m.esperar(j3)


@pytest.mark.asyncio
async def test_un_aviso_que_falla_no_deja_el_candado_tomado(tmp_path, agente_python):
    async def notify_roto(_):
        raise RuntimeError("telegram caido")
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    p = _proyecto(tmp_path)
    jid = m.iniciar(p, "print(1)", notify_roto, agente="fake")
    await m.esperar(jid)
    assert m.corriendo() == {} and m.store.obtener(jid).estado == "ok"


@pytest.mark.asyncio
async def test_excepcion_inesperada_se_registra_y_libera(tmp_path, avisos):
    async def runner_roto(*a, **k):
        raise OSError("no existe el ejecutable")
    m = JobManager(JobStore(str(tmp_path / "j.db")), runner=runner_roto)
    jid = m.iniciar(_proyecto(tmp_path), "x", avisos, agente="opencode")
    await m.esperar(jid)
    t = m.store.obtener(jid)
    assert t.estado == "fallo" and "OSError" in t.error and m.corriendo() == {}
    assert "se cayó" in avisos.lista[-1]


def test_reinicio_marca_interrumpidos(tmp_path):
    s = JobStore(str(tmp_path / "j.db"))
    jid = s.crear("p", "x", "opencode")
    assert s.marcar_interrumpidos() == 1 and s.obtener(jid).estado == "interrumpido"


def test_agente_configurable(monkeypatch):
    monkeypatch.setenv("HERMES_AGENT", "claude")
    assert jobs.agente_configurado() == "claude" and jobs.AGENTES["claude"]("x") == ["claude", "-p", "x"]
    monkeypatch.setenv("HERMES_AGENT", "otro")
    assert jobs.agente_configurado() == "opencode"
    monkeypatch.delenv("HERMES_AGENT_TIMEOUT_MIN", raising=False)
    assert jobs.timeout_agente_s() == 45 * 60


def test_resumen(tmp_path):
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    jid = m.store.crear("p", "x", "opencode")
    m.store.cerrar(jid, "ok", 95, 0, "ok", "", "")
    txt = jobs.resumen_trabajos(m)
    assert "Corriendo: ninguno" in txt and f"#{jid}" in txt and "1 min 35 s" in txt and "tests ok" in txt


@pytest.mark.asyncio
async def test_timeout_mata_tambien_a_los_hijos(tmp_path, avisos, agente_python, monkeypatch):
    """El agente lanza otros procesos (node, npm...): al vencerse no puede quedar ninguno vivo escribiendo."""
    monkeypatch.setenv("HERMES_AGENT_TIMEOUT_MIN", str(0.5 / 60))
    marca = tmp_path / "hijo_vivo.txt"
    hijo = f"import time; time.sleep(2); open(r'{marca}','w').write('x')"
    codigo = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {hijo!r}]); time.sleep(5)"
    m = JobManager(JobStore(str(tmp_path / "j.db")))
    jid = m.iniciar(_proyecto(tmp_path), codigo, avisos, agente="fake")
    await m.esperar(jid)
    await asyncio.sleep(3)
    assert m.store.obtener(jid).estado == "timeout"
    assert not marca.exists(), "el proceso hijo del agente siguió vivo después del timeout"



def test_avisa_avances_mientras_el_agente_trabaja(tmp_path):
    import asyncio as aio
    from bot.core.jobs import JobManager, JobStore
    from bot.core.projects import Proyecto

    async def lento(argv, cwd, timeout, shell=False):
        if shell:
            return 0, "", "", False
        await aio.sleep(0.35)
        return 0, "ok", "", False

    avisos = []

    async def notify(t):
        avisos.append(t)

    async def caso():
        m = JobManager(store=JobStore(str(tmp_path / "j.db")), runner=lento, avance_cada_s=0.1,
                       avance_fn=lambda c: "\n2 archivo(s) cambiado(s): a.py, b.py")
        jid = m.iniciar(Proyecto("demo", "", str(tmp_path), "t"), "x", notify)
        await m.esperar(jid)

    aio.run(caso())
    avances = [a for a in avisos if a.startswith("⏳")]
    assert 2 <= len(avances) <= 4 and "a.py, b.py" in avances[0]
    assert avisos[-1].startswith("✅")


def test_avance_git(tmp_path):
    import subprocess
    from bot.core.jobs import avance_git
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert avance_git(str(tmp_path)) == "\nAún sin archivos cambiados."
    (tmp_path / "nuevo.py").write_text("x")
    assert "1 archivo(s) cambiado(s): nuevo.py" in avance_git(str(tmp_path))
    assert avance_git(str(tmp_path / "no-existe")) == ""
