from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List
from datetime import datetime

class AlertLevel(Enum):
    ERRORS_ONLY = "errors_only"
    IMPORTANT_CHANGES = "important"
    ALL = "all"

@dataclass
class AlertConfig:
    """Configuración de alertas por proyecto."""
    proyecto: str
    level: AlertLevel = AlertLevel.IMPORTANT_CHANGES
    enabled: bool = True

    def should_notify(self, is_error: bool, is_important: bool) -> bool:
        """Decidir si notificar basado en configuración."""
        if not self.enabled:
            return False

        if self.level == AlertLevel.ERRORS_ONLY:
            return is_error
        elif self.level == AlertLevel.IMPORTANT_CHANGES:
            return is_error or is_important
        else:  # ALL
            return True

@dataclass
class RollbackPoint:
    """Punto de restauración para rollback."""
    id: str = field(default_factory=lambda: str(__import__('uuid').uuid4())[:8])
    proyecto: str = ""
    deployment_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    version_hash: str = ""
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "proyecto": self.proyecto,
            "deployment_id": self.deployment_id,
            "timestamp": self.timestamp,
            "version_hash": self.version_hash,
            "metadata": self.metadata,
        }

class RollbackManager:
    """Gestor de rollbacks automáticos."""

    def __init__(self):
        self.rollback_points: Dict[str, RollbackPoint] = {}
        self.rollback_threshold = 3  # Fallos consecutivos antes de rollback

    def create_rollback_point(self, proyecto: str, version_hash: str,
                             metadata: Dict = None) -> RollbackPoint:
        """Crear punto de restauración."""
        point = RollbackPoint(
            proyecto=proyecto,
            version_hash=version_hash,
            metadata=metadata or {}
        )
        self.rollback_points[point.id] = point
        return point

    def should_rollback(self, consecutive_failures: int, deployment_id: str) -> bool:
        """Decidir si hacer rollback."""
        return consecutive_failures >= self.rollback_threshold

    def get_rollback_point(self, punto_id: str) -> Optional[RollbackPoint]:
        """Obtener punto de restauración."""
        return self.rollback_points.get(punto_id)

    def list_rollback_points(self, proyecto: str) -> List[RollbackPoint]:
        """Listar puntos de restauración de un proyecto."""
        return [p for p in self.rollback_points.values() if p.proyecto == proyecto]

    def mark_for_rollback(self, punto_id: str) -> bool:
        """Marcar un punto para rollback."""
        point = self.get_rollback_point(punto_id)
        if point:
            point.metadata["marked_for_rollback"] = True
            point.metadata["rollback_time"] = datetime.utcnow().isoformat() + "Z"
            return True
        return False

class AlertManager:
    """Gestor centralizado de alertas."""

    def __init__(self):
        self.configs: Dict[str, AlertConfig] = {}
        self.rollback_manager = RollbackManager()

    def set_alert_level(self, proyecto: str, level: AlertLevel):
        """Configurar nivel de alertas."""
        if proyecto not in self.configs:
            self.configs[proyecto] = AlertConfig(proyecto=proyecto, level=level)
        else:
            self.configs[proyecto].level = level

    def get_alert_config(self, proyecto: str) -> AlertConfig:
        """Obtener configuración de alertas."""
        if proyecto not in self.configs:
            self.configs[proyecto] = AlertConfig(proyecto=proyecto)
        return self.configs[proyecto]

    def should_alert(self, proyecto: str, is_error: bool, is_important: bool) -> bool:
        """Decidir si generar alerta."""
        config = self.get_alert_config(proyecto)
        return config.should_notify(is_error, is_important)

    def disable_alerts(self, proyecto: str):
        """Desactivar alertas."""
        self.get_alert_config(proyecto).enabled = False

    def enable_alerts(self, proyecto: str):
        """Activar alertas."""
        self.get_alert_config(proyecto).enabled = True
