import pytest
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def temp_data_dir(tmp_path):
    """Crea directorio temporal para datos de prueba."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir

@pytest.fixture
def mock_update():
    """Mock de Update de Telegram."""
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.edit_text = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_chat.id = 12345
    update.effective_user.id = 67890
    return update

@pytest.fixture
def mock_context():
    """Mock de Context de Telegram."""
    context = MagicMock()
    context.bot.edit_message_text = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.bot.send_photo = AsyncMock()
    context.args = []
    return context

@pytest.fixture
def sample_notification():
    """Notificación de ejemplo."""
    return {
        "id": "test-001",
        "proyecto": "mi-proyecto",
        "proceso": "instalar dependencias",
        "timestamp": "2026-09-20T10:30:00Z",
        "estado": "pendiente",
        "resultado": None,
        "approved_at": None
    }

@pytest.fixture
def sample_metrics():
    """Métricas de ejemplo."""
    return {
        "mi-proyecto": {
            "test": {"total": 10, "success": 10, "failed": 0},
            "build": {"total": 5, "success": 5, "failed": 0},
            "deploy": {"total": 2, "success": 1, "failed": 1}
        }
    }
