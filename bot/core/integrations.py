import asyncio
import aiohttp
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

@dataclass
class WebhookEvent:
    type: str  # deployment_complete, test_failed, etc
    proyecto: str
    data: Dict

class WebhookDispatcher:
    """Enviar eventos a webhooks registrados."""

    async def dispatch(self, event: WebhookEvent, webhooks: List[Dict]) -> Dict[str, bool]:
        """Enviar evento a todos los webhooks registrados."""
        results = {}

        for webhook in webhooks:
            if webhook.get('event_type') != event.type or not webhook.get('active'):
                continue

            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "event": event.type,
                        "proyecto": event.proyecto,
                        "data": event.data
                    }
                    async with session.post(webhook['url'], json=payload, timeout=5) as resp:
                        results[webhook['id']] = resp.status == 200
            except:
                results[webhook['id']] = False

        return results

class AnomalyDetector:
    """Detectar anomalías en métricas."""

    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.history: Dict[str, List[int]] = {}

    def add_metric(self, key: str, value: int):
        """Agregar métrica."""
        if key not in self.history:
            self.history[key] = []

        self.history[key].append(value)
        if len(self.history[key]) > self.window_size:
            self.history[key].pop(0)

    def is_anomaly(self, key: str, value: int, threshold: float = 2.0) -> bool:
        """Detectar si es una anomalía (más de 2σ del promedio)."""
        if key not in self.history or len(self.history[key]) < 3:
            return False

        avg = sum(self.history[key]) / len(self.history[key])
        variance = sum((x - avg) ** 2 for x in self.history[key]) / len(self.history[key])
        std_dev = variance ** 0.5

        return abs(value - avg) > threshold * std_dev

class RateLimiter:
    """Limitar tasa de solicitudes."""

    def __init__(self, max_per_hour: int = 100, max_per_minute: int = 10):
        self.max_per_hour = max_per_hour
        self.max_per_minute = max_per_minute
        self.request_times: Dict[str, List[datetime]] = {}

    def is_allowed(self, key: str) -> bool:
        """Verificar si la solicitud es permitida."""
        now = datetime.utcnow()

        if key not in self.request_times:
            self.request_times[key] = []

        # Limpiar requests antiguos
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        self.request_times[key] = [t for t in self.request_times[key] if t > hour_ago]

        # Verificar límite por minuto
        recent = [t for t in self.request_times[key] if t > minute_ago]
        if len(recent) >= self.max_per_minute:
            return False

        # Verificar límite por hora
        if len(self.request_times[key]) >= self.max_per_hour:
            return False

        # Registrar request
        self.request_times[key].append(now)
        return True

    def get_status(self, key: str) -> Dict:
        """Obtener estado de rate limiting."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        if key not in self.request_times:
            return {"requests_minute": 0, "requests_hour": 0}

        times = self.request_times[key]
        minute_count = len([t for t in times if t > minute_ago])
        hour_count = len([t for t in times if t > hour_ago])

        return {
            "requests_minute": minute_count,
            "requests_hour": hour_count,
            "remaining_minute": max(0, self.max_per_minute - minute_count),
            "remaining_hour": max(0, self.max_per_hour - hour_count),
        }
