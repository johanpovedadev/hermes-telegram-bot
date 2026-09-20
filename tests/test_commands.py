import pytest
from unittest.mock import AsyncMock
from bot.handlers.commands import (
    start, notificaciones, historial, estadisticas, audit, confiabilidad
)
from bot.core.notifications import NotificationManager

@pytest.fixture
def nm_mock(monkeypatch, temp_data_dir):
    """Mock de NotificationManager."""
    nm = NotificationManager(data_dir=str(temp_data_dir))
    monkeypatch.setattr("bot.handlers.commands.nm", nm)
    return nm

class TestNewCommands:
    @pytest.mark.asyncio
    async def test_start_command(self, mock_update, mock_context):
        """Test: comando /start."""
        await start(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Jarvis León" in call_text
        assert "Notificaciones" in call_text or "notificaciones" in call_text.lower()

    @pytest.mark.asyncio
    async def test_notificaciones_sin_datos(self, mock_update, mock_context, nm_mock):
        """Test: /notificaciones sin datos."""
        await notificaciones(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "No hay tareas pendientes" in call_text

    @pytest.mark.asyncio
    async def test_notificaciones_con_datos(self, mock_update, mock_context, nm_mock):
        """Test: /notificaciones con datos."""
        nm_mock.crear_notificacion("t1", "proyecto-1", "test")
        nm_mock.crear_notificacion("t2", "proyecto-1", "build")

        await notificaciones(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Tareas Pendientes" in call_text
        assert "proyecto-1" in call_text
        assert "2" in call_text

    @pytest.mark.asyncio
    async def test_historial_sin_datos(self, mock_update, mock_context, nm_mock):
        """Test: /historial sin datos."""
        await historial(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "No hay historial" in call_text

    @pytest.mark.asyncio
    async def test_historial_con_datos(self, mock_update, mock_context, nm_mock):
        """Test: /historial con datos."""
        nm_mock.crear_notificacion("t1", "p1", "test")
        nm_mock.crear_notificacion("t2", "p1", "build")
        nm_mock.aprobar("t1")
        nm_mock.rechazar("t2")

        await historial(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Últimas" in call_text
        assert "✅" in call_text or "❌" in call_text

    @pytest.mark.asyncio
    async def test_estadisticas_sin_datos(self, mock_update, mock_context, nm_mock):
        """Test: /estadisticas sin datos."""
        await estadisticas(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "No hay datos" in call_text

    @pytest.mark.asyncio
    async def test_estadisticas_con_datos(self, mock_update, mock_context, nm_mock):
        """Test: /estadisticas con datos."""
        nm_mock.crear_notificacion("t1", "p1", "test")
        nm_mock.crear_notificacion("t2", "p1", "build")
        nm_mock.crear_notificacion("t3", "p2", "deploy")

        nm_mock.aprobar("t1")
        nm_mock.rechazar("t2")

        await estadisticas(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Estadísticas" in call_text
        assert "p1" in call_text or "p2" in call_text

    @pytest.mark.asyncio
    async def test_audit_sin_datos(self, mock_update, mock_context, nm_mock):
        """Test: /audit sin datos."""
        await audit(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "No hay registro" in call_text

    @pytest.mark.asyncio
    async def test_audit_con_datos(self, mock_update, mock_context, nm_mock):
        """Test: /audit con datos."""
        nm_mock.crear_notificacion("t1", "p1", "test")
        nm_mock.aprobar("t1", user_id=12345)

        await audit(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Audit Log" in call_text
        assert "p1" in call_text

    @pytest.mark.asyncio
    async def test_confiabilidad_sin_datos(self, mock_update, mock_context, nm_mock):
        """Test: /confiabilidad sin datos."""
        await confiabilidad(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Sin datos" in call_text

    @pytest.mark.asyncio
    async def test_confiabilidad_con_datos(self, mock_update, mock_context, nm_mock):
        """Test: /confiabilidad con datos."""
        nm_mock.crear_notificacion("t1", "p1", "test")
        nm_mock.crear_notificacion("t2", "p1", "test")
        nm_mock.aprobar("t1")
        nm_mock.rechazar("t2")

        await confiabilidad(mock_update, mock_context)

        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Confiabilidad" in call_text
        assert "50%" in call_text or "50.0%" in call_text
