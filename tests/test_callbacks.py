import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.handlers.callbacks import (
    handle_approval, handle_rejection, handle_details, handle_later,
    crear_botones_notificacion
)
from bot.core.notifications import NotificationManager

@pytest.fixture
def nm_mock(monkeypatch, temp_data_dir):
    """Mock de NotificationManager."""
    nm = NotificationManager(data_dir=str(temp_data_dir))
    monkeypatch.setattr("bot.handlers.callbacks.nm", nm)
    return nm

class TestCallbacks:
    @pytest.mark.asyncio
    async def test_handle_approval(self, mock_update, mock_context, nm_mock, temp_data_dir):
        """Test: manejar botón de aprobación."""
        nm = NotificationManager(data_dir=str(temp_data_dir))
        nm.crear_notificacion("notif-001", "proyecto-1", "test")

        mock_update.callback_query.data = "approve:notif-001"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()
        mock_update.callback_query.message.text = "Test notification"
        mock_update.effective_user.id = 12345
        mock_update.effective_user.username = "testuser"

        await handle_approval(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_rejection(self, mock_update, mock_context, nm_mock, temp_data_dir):
        """Test: manejar botón de rechazo."""
        nm = NotificationManager(data_dir=str(temp_data_dir))
        nm.crear_notificacion("notif-001", "proyecto-1", "test")

        mock_update.callback_query.data = "reject:notif-001"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()
        mock_update.callback_query.message.text = "Test notification"
        mock_update.effective_user.id = 12345
        mock_update.effective_user.username = "testuser"

        await handle_rejection(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_details(self, mock_update, mock_context, nm_mock, temp_data_dir):
        """Test: mostrar detalles de notificación."""
        nm = NotificationManager(data_dir=str(temp_data_dir))
        nm.crear_notificacion("notif-001", "proyecto-1", "test")

        mock_update.callback_query.data = "details:notif-001"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        await handle_details(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

        call_args = mock_update.callback_query.edit_message_text.call_args
        assert "Detalles del Proceso" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_later(self, mock_update, mock_context):
        """Test: botón 'Después'."""
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.data = "later:notif-001"

        await handle_later(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()

    def test_crear_botones_notificacion(self):
        """Test: crear markup de botones."""
        keyboard = crear_botones_notificacion("test-123")

        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 2
        assert len(keyboard.inline_keyboard[0]) == 2  # Aprobar, Rechazar
        assert len(keyboard.inline_keyboard[1]) == 2  # Ver más, Después

        # Verificar texto de botones
        buttons_text = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                buttons_text.append(btn.text)

        assert "✅ Aprobar" in buttons_text
        assert "❌ Rechazar" in buttons_text
        assert "❓ Ver más" in buttons_text
        assert "⏳ Después" in buttons_text
