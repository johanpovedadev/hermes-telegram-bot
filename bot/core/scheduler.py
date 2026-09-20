from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import uuid
from datetime import datetime

class ScheduleStatus(Enum):
    """Estado de una tarea programada."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"

@dataclass
class ScheduledTask:
    """Tarea programada con expresión cron."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    descripcion: str = ""
    proyecto: str = ""
    comando: str = ""
    cron_expression: str = ""  # "0 2 * * *" = 2 AM diarios
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "descripcion": self.descripcion,
            "proyecto": self.proyecto,
            "comando": self.comando,
            "cron_expression": self.cron_expression,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
        }

class CronValidator:
    """Validador de expresiones cron."""

    @staticmethod
    def validate(expression: str) -> tuple:
        """
        Validar expresión cron.
        Returns: (es_válida, mensaje_error)
        """
        parts = expression.split()

        if len(parts) != 5:
            return False, "Cron debe tener 5 campos: minute hour day month weekday"

        minute, hour, day, month, weekday = parts

        # Validaciones básicas
        validations = [
            (minute, 0, 59, "Minuto"),
            (hour, 0, 23, "Hora"),
            (day, 1, 31, "Día"),
            (month, 1, 12, "Mes"),
            (weekday, 0, 6, "Día de semana"),
        ]

        for value, min_val, max_val, field_name in validations:
            if value == "*":
                continue
            if value == "?":
                continue

            try:
                val = int(value)
                if not (min_val <= val <= max_val):
                    return False, f"{field_name} fuera de rango [{min_val}-{max_val}]"
            except ValueError:
                # Permite rangos como "0-6", listas como "1,3,5", etc.
                if not any(c in value for c in ["-", ",", "/", "?"]):
                    return False, f"{field_name} inválido: {value}"

        return True, "Válido"

class Scheduler:
    """Gestor de tareas programadas."""

    # Templates de cron comunes
    COMMON_EXPRESSIONS = {
        "hourly": "0 * * * *",           # Cada hora
        "daily": "0 0 * * *",            # Diariamente a las 00:00
        "daily-2am": "0 2 * * *",        # Diariamente a las 02:00
        "weekly": "0 0 * * 0",           # Semanalmente (domingo)
        "monthly": "0 0 1 * *",          # Mensualmente (día 1)
        "every-5min": "*/5 * * * *",     # Cada 5 minutos
        "every-30min": "*/30 * * * *",   # Cada 30 minutos
    }

    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}

    def create_task(self, nombre: str, proyecto: str, comando: str,
                   cron: str, descripcion: str = "") -> ScheduledTask:
        """Crear una nueva tarea programada."""
        is_valid, msg = CronValidator.validate(cron)
        if not is_valid:
            raise ValueError(f"Cron inválido: {msg}")

        task = ScheduledTask(
            name=nombre,
            proyecto=proyecto,
            comando=comando,
            cron_expression=cron,
            descripcion=descripcion or nombre
        )

        self.tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Obtener una tarea programada."""
        return self.tasks.get(task_id)

    def list_tasks(self, proyecto: Optional[str] = None,
                   status: Optional[ScheduleStatus] = None) -> List[ScheduledTask]:
        """Listar tareas programadas con filtros."""
        tasks = list(self.tasks.values())

        if proyecto:
            tasks = [t for t in tasks if t.proyecto == proyecto]

        if status:
            tasks = [t for t in tasks if t.status == status]

        return tasks

    def pause_task(self, task_id: str) -> bool:
        """Pausar una tarea."""
        if task_id in self.tasks:
            self.tasks[task_id].status = ScheduleStatus.PAUSED
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """Reanudar una tarea."""
        if task_id in self.tasks:
            self.tasks[task_id].status = ScheduleStatus.ACTIVE
            return True
        return False

    def delete_task(self, task_id: str) -> bool:
        """Eliminar una tarea."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False

    def mark_run(self, task_id: str, success: bool = True):
        """Marcar una tarea como ejecutada."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.run_count += 1
            task.last_run = datetime.utcnow().isoformat() + "Z"

    def get_common_expression(self, name: str) -> Optional[str]:
        """Obtener una expresión cron común."""
        return self.COMMON_EXPRESSIONS.get(name)

    def list_common_expressions(self) -> Dict[str, str]:
        """Listar expresiones cron comunes."""
        return self.COMMON_EXPRESSIONS.copy()
