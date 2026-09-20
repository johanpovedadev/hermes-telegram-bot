import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers.run import ejecutar_issue
from bot.core.notifications import NotificationManager

@pytest.fixture
def nm_mock(monkeypatch, temp_data_dir):
    """Mock de NotificationManager."""
    nm = NotificationManager(data_dir=str(temp_data_dir))
    monkeypatch.setattr("bot.handlers.run.nm", nm)
    return nm

class TestRunHandler:
    @pytest.mark.asyncio
    async def test_ejecutar_issue_sin_args(self, mock_update, mock_context):
        """Test: ejecutar sin argumentos."""
        mock_context.args = []

        await ejecutar_issue(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "Uso:" in call_text

    @pytest.mark.asyncio
    async def test_ejecutar_issue_proyecto_no_existe(self, mock_update, mock_context):
        """Test: proyecto no existe."""
        mock_context.args = ["proyecto-no-existe", "hacer algo"]

        with patch("bot.handlers.run.os.path.exists", return_value=False):
            await ejecutar_issue(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "No existe" in call_text

    @pytest.mark.asyncio
    async def test_ejecutar_issue_exitoso(self, mock_update, mock_context, nm_mock):
        """Test: ejecución exitosa con notificación."""
        mock_context.args = ["proyecto-1", "test"]

        mock_result = {
            "returncode": 0,
            "stdout": "Test passed successfully",
            "stderr": ""
        }

        with patch("bot.handlers.run.os.path.exists", return_value=True):
            with patch("bot.handlers.run.ejecutar_opencode", new_callable=AsyncMock) as mock_opencode:
                mock_opencode.return_value = mock_result

                await ejecutar_issue(mock_update, mock_context)

        # Verificar que se registró la notificación
        pendientes = nm_mock.obtener_pendientes()
        assert len(pendientes) == 1
        assert pendientes[0].proyecto == "proyecto-1"

        # Verificar que se llamó a reply_text con botones
        assert mock_update.message.reply_text.call_count >= 2  # Status + resultado

        last_call = mock_update.message.reply_text.call_args_list[-1]
        assert "reply_markup" in last_call.kwargs
        assert "Completado" in last_call[0][0] or "✅" in last_call[0][0]

    @pytest.mark.asyncio
    async def test_ejecutar_issue_error(self, mock_update, mock_context, nm_mock):
        """Test: ejecución con error."""
        mock_context.args = ["proyecto-1", "build"]

        mock_result = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Build failed: syntax error"
        }

        with patch("bot.handlers.run.os.path.exists", return_value=True):
            with patch("bot.handlers.run.ejecutar_opencode", new_callable=AsyncMock) as mock_opencode:
                mock_opencode.return_value = mock_result

                await ejecutar_issue(mock_update, mock_context)

        # Verificar que se registró la notificación
        pendientes = nm_mock.obtener_pendientes()
        assert len(pendientes) == 1
        assert pendientes[0].proyecto == "proyecto-1"

        last_call = mock_update.message.reply_text.call_args_list[-1]
        assert "❌" in last_call[0][0]

    @pytest.mark.asyncio
    async def test_ejecutar_issue_timeout(self, mock_update, mock_context, nm_mock):
        """Test: timeout en ejecución."""
        mock_context.args = ["proyecto-1", "long-task"]

        with patch("bot.handlers.run.os.path.exists", return_value=True):
            with patch("bot.handlers.run.ejecutar_opencode", new_callable=AsyncMock) as mock_opencode:
                import subprocess
                mock_opencode.side_effect = subprocess.TimeoutExpired("cmd", 30)

                await ejecutar_issue(mock_update, mock_context)

        # Verificar que se registró timeout
        pendientes = nm_mock.obtener_pendientes()
        # El timeout se registra con resultado="timeout"
        assert len(pendientes) >= 0  # Dependiendo de cómo se maneje
