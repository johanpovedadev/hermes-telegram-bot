import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field

NOTIFICATIONS_FILE = os.path.expanduser("~/.jarvis/notifications.json")
METRICS_FILE = os.path.expanduser("~/.jarvis/metrics.json")

@dataclass
class Notification:
    id: str
    proyecto: str
    proceso: str
    timestamp: str
    estado: str  # "pendiente", "aprobado", "rechazado"
    resultado: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None

    def to_dict(self):
        return asdict(self)

class NotificationManager:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.notifications_file = os.path.join(data_dir, "notifications.json")
            self.metrics_file = os.path.join(data_dir, "metrics.json")
        else:
            self.notifications_file = NOTIFICATIONS_FILE
            self.metrics_file = METRICS_FILE

        self._ensure_files()

    def _ensure_files(self):
        """Crea directorios y archivos si no existen."""
        os.makedirs(os.path.dirname(self.notifications_file), exist_ok=True)

        if not os.path.exists(self.notifications_file):
            self._write_json(self.notifications_file, [])

        if not os.path.exists(self.metrics_file):
            self._write_json(self.metrics_file, {})

    def _read_json(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return [] if 'notifications' in filepath else {}

    def _write_json(self, filepath: str, data):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def crear_notificacion(self, notif_id: str, proyecto: str, proceso: str, resultado: Optional[str] = None) -> Notification:
        """Crea y almacena una nueva notificación."""
        notif = Notification(
            id=notif_id,
            proyecto=proyecto,
            proceso=proceso,
            timestamp=datetime.utcnow().isoformat() + "Z",
            estado="pendiente",
            resultado=resultado
        )

        notifs = self._read_json(self.notifications_file)
        notifs.append(notif.to_dict())
        self._write_json(self.notifications_file, notifs)

        return notif

    def obtener_pendientes(self) -> List[Notification]:
        """Obtiene todas las notificaciones pendientes."""
        notifs = self._read_json(self.notifications_file)
        return [
            Notification(**n) for n in notifs
            if n.get("estado") == "pendiente"
        ]

    def obtener_todas(self, limite: int = 10) -> List[Notification]:
        """Obtiene todas las notificaciones (últimas N)."""
        notifs = self._read_json(self.notifications_file)
        return [Notification(**n) for n in notifs[-limite:]]

    def obtener_por_proyecto(self, proyecto: str, limite: int = 10) -> List[Notification]:
        """Obtiene notificaciones de un proyecto específico."""
        notifs = self._read_json(self.notifications_file)
        return [
            Notification(**n) for n in notifs
            if n.get("proyecto") == proyecto
        ][-limite:]

    def aprobar(self, notif_id: str, user_id: Optional[int] = None) -> bool:
        """Aprueba una notificación."""
        notifs = self._read_json(self.notifications_file)

        for notif in notifs:
            if notif.get("id") == notif_id:
                notif["estado"] = "aprobado"
                notif["approved_at"] = datetime.utcnow().isoformat() + "Z"
                notif["approved_by"] = str(user_id) if user_id else None
                self._write_json(self.notifications_file, notifs)

                # Actualizar métricas
                self._actualizar_metrica(notif.get("proyecto"), notif.get("proceso"), "success")
                return True

        return False

    def rechazar(self, notif_id: str) -> bool:
        """Rechaza una notificación."""
        notifs = self._read_json(self.notifications_file)

        for notif in notifs:
            if notif.get("id") == notif_id:
                notif["estado"] = "rechazado"
                notif["approved_at"] = datetime.utcnow().isoformat() + "Z"
                self._write_json(self.notifications_file, notifs)

                # Actualizar métricas
                self._actualizar_metrica(notif.get("proyecto"), notif.get("proceso"), "failed")
                return True

        return False

    def _actualizar_metrica(self, proyecto: str, proceso: str, resultado: str):
        """Actualiza las métricas de éxito/fracaso."""
        metrics = self._read_json(self.metrics_file)

        if proyecto not in metrics:
            metrics[proyecto] = {}

        if proceso not in metrics[proyecto]:
            metrics[proyecto][proceso] = {"total": 0, "success": 0, "failed": 0}

        metrics[proyecto][proceso]["total"] += 1
        if resultado == "success":
            metrics[proyecto][proceso]["success"] += 1
        else:
            metrics[proyecto][proceso]["failed"] += 1

        self._write_json(self.metrics_file, metrics)

    def obtener_metricas(self, proyecto: Optional[str] = None) -> Dict:
        """Obtiene métricas de confiabilidad."""
        metrics = self._read_json(self.metrics_file)

        if proyecto:
            return metrics.get(proyecto, {})

        return metrics

    def obtener_estadisticas_proyecto(self, proyecto: str) -> Dict:
        """Obtiene estadísticas detalladas de un proyecto."""
        notifs = self.obtener_por_proyecto(proyecto, limite=100)

        return {
            "proyecto": proyecto,
            "total_procesos": len(notifs),
            "aprobados": len([n for n in notifs if n.estado == "aprobado"]),
            "rechazados": len([n for n in notifs if n.estado == "rechazado"]),
            "pendientes": len([n for n in notifs if n.estado == "pendiente"]),
            "metricas": self.obtener_metricas(proyecto)
        }
