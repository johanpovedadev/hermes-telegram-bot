import pytest
import asyncio
from bot.core.voice import VoiceCommandParser, TextToSpeech, VoiceEventStreamer

class TestVoiceCommandParser:
    def test_parse_run_command(self):
        cmd, arg = VoiceCommandParser.parse("ejecutar tests en proyecto1")
        assert cmd == "ejecutar"
        assert "proyecto1" in arg

    def test_parse_status_command(self):
        cmd, arg = VoiceCommandParser.parse("cómo está el sistema")
        assert cmd == "status"

    def test_parse_notifications_command(self):
        cmd, arg = VoiceCommandParser.parse("dame las notificaciones")
        assert cmd == "notificaciones"

    def test_parse_history_command(self):
        cmd, arg = VoiceCommandParser.parse("historial de tareas")
        assert cmd == "historial"

    def test_parse_unknown_command(self):
        cmd, arg = VoiceCommandParser.parse("algo aleatorio")
        assert cmd == "unknown"

class TestTextToSpeech:
    @pytest.mark.asyncio
    async def test_synthesize(self):
        tts = TextToSpeech()
        result = await tts.synthesize("Hola mundo", "/tmp/test.mp3")
        assert result == True

class TestVoiceEventStreamer:
    @pytest.mark.asyncio
    async def test_queue_event(self):
        streamer = VoiceEventStreamer()
        await streamer.queue_event("deployment", "Deploy completado")
        assert not streamer.event_queue.empty()

    @pytest.mark.asyncio
    async def test_stream_empty(self):
        streamer = VoiceEventStreamer()
        result = await streamer.stream_events()
        assert result is None
