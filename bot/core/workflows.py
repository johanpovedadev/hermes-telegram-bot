from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from enum import Enum
import uuid
from datetime import datetime

class WorkflowStatus(Enum):
    """Estados de un workflow."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class StepStatus(Enum):
    """Estados de un paso."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class WorkflowStep:
    """Paso en un workflow."""
    name: str
    description: str
    command: str  # El comando/proceso a ejecutar
    requires_approval: bool = False  # Requiere aprobación antes de ejecutar
    auto_approve: bool = False  # Auto-aprobar si el paso anterior fue exitoso
    retry_on_failure: bool = True
    timeout_seconds: int = 300

    # Runtime state
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "command": self.command,
            "requires_approval": self.requires_approval,
            "auto_approve": self.auto_approve,
            "retry_on_failure": self.retry_on_failure,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }

@dataclass
class Workflow:
    """Flujo de trabajo con múltiples pasos."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    proyecto: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)

    # Runtime state
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_step_index: int = 0

    def add_step(self, step: WorkflowStep) -> "Workflow":
        """Agregar un paso al workflow."""
        self.steps.append(step)
        return self

    def get_current_step(self) -> Optional[WorkflowStep]:
        """Obtener paso actual."""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def mark_step_completed(self, index: int, result: str = ""):
        """Marcar paso como completado."""
        if index < len(self.steps):
            self.steps[index].status = StepStatus.COMPLETED
            self.steps[index].completed_at = datetime.utcnow().isoformat() + "Z"
            self.steps[index].result = result
            self.current_step_index = index + 1

    def mark_step_failed(self, index: int, error: str = ""):
        """Marcar paso como fallido."""
        if index < len(self.steps):
            self.steps[index].status = StepStatus.FAILED
            self.steps[index].completed_at = datetime.utcnow().isoformat() + "Z"
            self.steps[index].error = error

    def mark_step_skipped(self, index: int):
        """Marcar paso como omitido."""
        if index < len(self.steps):
            self.steps[index].status = StepStatus.SKIPPED
            self.steps[index].completed_at = datetime.utcnow().isoformat() + "Z"

    def get_progress(self) -> Dict:
        """Obtener progreso del workflow."""
        total = len(self.steps)
        completed = len([s for s in self.steps if s.status == StepStatus.COMPLETED])
        failed = len([s for s in self.steps if s.status == StepStatus.FAILED])

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": total - completed - failed,
            "percentage": int((completed / total * 100)) if total > 0 else 0,
        }

    def is_complete(self) -> bool:
        """Verificar si el workflow está completo."""
        return all(s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for s in self.steps)

    def has_failures(self) -> bool:
        """Verificar si hay pasos fallidos."""
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "proyecto": self.proyecto,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_step_index": self.current_step_index,
            "steps": [s.to_dict() for s in self.steps],
            "progress": self.get_progress(),
        }

class WorkflowBuilder:
    """Constructor fluido para crear workflows."""

    def __init__(self, name: str, proyecto: str):
        self.workflow = Workflow(name=name, proyecto=proyecto)

    def description(self, desc: str) -> "WorkflowBuilder":
        self.workflow.description = desc
        return self

    def add_step(self, name: str, command: str, description: str = "",
                 requires_approval: bool = False, auto_approve: bool = False) -> "WorkflowBuilder":
        step = WorkflowStep(
            name=name,
            command=command,
            description=description or name,
            requires_approval=requires_approval,
            auto_approve=auto_approve
        )
        self.workflow.add_step(step)
        return self

    def build(self) -> Workflow:
        return self.workflow

# Workflow templates predefinidos
WORKFLOW_TEMPLATES = {
    "test-build-deploy": lambda proyecto: (
        WorkflowBuilder("Test → Build → Deploy", proyecto)
        .description("Ejecutar tests, compilar, y desplegar a producción")
        .add_step("test", "test", "Ejecutar test suite", auto_approve=True)
        .add_step("build", "build", "Compilar proyecto", auto_approve=True)
        .add_step("deploy", "deploy to production", "Desplegar a producción", requires_approval=True)
        .build()
    ),
    "lint-format-commit": lambda proyecto: (
        WorkflowBuilder("Lint → Format → Commit", proyecto)
        .description("Verificar linter, formatear código, hacer commit")
        .add_step("lint", "lint", "Verificar estilo de código", auto_approve=True)
        .add_step("format", "format", "Formatear código automáticamente", auto_approve=True)
        .add_step("commit", "commit changes", "Hacer commit de los cambios", requires_approval=True)
        .build()
    ),
    "ci-pipeline": lambda proyecto: (
        WorkflowBuilder("CI Pipeline", proyecto)
        .description("Pipeline de integración continua completo")
        .add_step("install", "install dependencies", "Instalar dependencias", auto_approve=True)
        .add_step("test", "test", "Ejecutar tests", auto_approve=True)
        .add_step("lint", "lint", "Verificar linter", auto_approve=True)
        .add_step("build", "build", "Compilar proyecto", auto_approve=True)
        .add_step("scan", "security scan", "Escanear seguridad", auto_approve=True)
        .build()
    ),
}

def get_workflow_template(template_name: str, proyecto: str) -> Optional[Workflow]:
    """Obtener un template predefinido."""
    if template_name in WORKFLOW_TEMPLATES:
        return WORKFLOW_TEMPLATES[template_name](proyecto)
    return None

def list_workflow_templates() -> List[str]:
    """Listar templates disponibles."""
    return list(WORKFLOW_TEMPLATES.keys())
