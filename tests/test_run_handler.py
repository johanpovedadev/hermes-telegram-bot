"""/run (issue #5): lanza el trabajo en segundo plano, avisa al terminar con botones y respeta projects.yaml."""
import asyncio

import pytest
from unittest.mock import AsyncMock

import bot.handlers.run as run
from bot.core.jobs import JobManager, JobStore
from bot.core.notifications import NotificationManager


@pytest.fixture(autouse=True)
def registro_falso(monkeypatch, tmp_path):
    """projects.yaml de prueba con 'proyecto-1' habilitado (issue #8)."""
    (tmp_path / "proyecto-1").mkdir()
    (tmp_path / "projects.yaml").write_text(
        "proyectos:\n  - nombre: proyecto-1\n    carpeta: proyecto-1\n    pruebas: echo ok\n    habilitado: true\n", encoding="utf-8")
    from bot.core import projects
    real = projects.cargar
    monkeypatch.setattr("bot.handlers.run.projects.cargar", lambda *a, **k: real(str(tmp_path / "projects.yaml"), str(tmp_path)))


@pytest.fixture
def manager(monkeypatch, tmp_path):
    resultados = {}

    async def runner(cmd, cwd, timeout, shell=False):
        clave = "pruebas" if shell else "agente"
        r = resultados.get(clave, (0, "ok", "", False))
        if callable(r):
            r = await r()
        return r

    m = JobManager(JobStore(str(tmp_path / "jobs.db")), runner=runner)
    m.resultados = resultados
    monkeypatch.setattr(run, "_manager", m)
    monkeypatch.setattr(run, "nm", NotificationManager(data_dir=str(tmp_path)))
    return m


def _enviados(ctx):
    return [c.kwargs["text"] for c in ctx.bot.send_message.call_args_list]


class TestRun:
    @pytest.mark.asyncio
    async def test_sin_args(self, mock_update, mock_context):
        mock_context.args = []
        await run.ejecutar_issue(mock_update, mock_context)
        assert "Uso:" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_proyecto_no_registrado(self, mock_update, mock_context, manager):
        mock_context.args = ["proyecto-no-existe", "hacer algo"]
        await run.ejecutar_issue(mock_update, mock_context)
        assert "no está en projects.yaml" in mock_update.message.reply_text.call_args[0][0]
        assert manager.store.ultimos() == []

    @pytest.mark.asyncio
    async def test_exitoso_responde_ya_y_avisa_al_terminar_con_botones(self, mock_update, mock_context, manager):
        mock_context.args = ["proyecto-1", "agrega", "pruebas"]
        await run.ejecutar_issue(mock_update, mock_context)
        assert "en cola" in mock_update.message.reply_text.call_args[0][0]
        job_id = manager.store.ultimos()[0].id
        await manager.esperar(job_id)
        textos = _enviados(mock_context)
        assert textos[0].startswith("▶️") and textos[-1].startswith("✅") and "Tests: OK" in textos[-1]
        ultimo = mock_context.bot.send_message.call_args_list[-1]
        assert ultimo.kwargs["reply_markup"] is not None and ultimo.kwargs["chat_id"] == 12345
        assert run.nm.obtener_pendientes()[0].proyecto == "proyecto-1"

    @pytest.mark.asyncio
    async def test_error_del_agente(self, mock_update, mock_context, manager):
        manager.resultados["agente"] = (1, "", "Build failed: syntax error", False)
        mock_context.args = ["proyecto-1", "build"]
        await run.ejecutar_issue(mock_update, mock_context)
        await manager.esperar(manager.store.ultimos()[0].id)
        assert _enviados(mock_context)[-1].startswith("❌") and "syntax error" in _enviados(mock_context)[-1]

    @pytest.mark.asyncio
    async def test_segundo_trabajo_en_el_mismo_proyecto_se_rechaza(self, mock_update, mock_context, manager):
        liberar = asyncio.Event()

        async def lento():
            await liberar.wait()
            return (0, "", "", False)

        manager.resultados["agente"] = lento
        mock_context.args = ["proyecto-1", "uno"]
        await run.ejecutar_issue(mock_update, mock_context)
        await asyncio.sleep(0)
        mock_context.args = ["proyecto-1", "dos"]
        await run.ejecutar_issue(mock_update, mock_context)
        assert "ya tiene el trabajo" in mock_update.message.reply_text.call_args[0][0]
        # mientras corre, /trabajos responde (el bot no queda bloqueado)
        await run.trabajos(mock_update, mock_context)
        assert "proyecto-1" in mock_update.message.reply_text.call_args[0][0] and "Corriendo" in mock_update.message.reply_text.call_args[0][0]
        liberar.set()
        await manager.esperar(manager.store.ultimos()[0].id)
        assert manager.corriendo() == {}
