from typing import Dict, List, Optional
import re

# Procesos que se aprueban automáticamente (confiables)
AUTO_APPROVE_PATTERNS = {
    "test": True,
    "lint": True,
    "format": True,
    "build": True,
    "install": True,
    "dependencies": True,
    "docs": True,
    "scan": True,
}

# Procesos que SIEMPRE requieren aprobación manual (peligrosos)
MANUAL_APPROVE_PATTERNS = {
    "deploy": True,
    "production": True,
    "prod": True,
    "release": True,
    "publish": True,
    "delete": True,
    "drop": True,
    "remove": True,
    "database": True,
}

# Palabras clave que hacen que algo requiera aprobación extra
DANGER_KEYWORDS = {
    "delete",
    "drop",
    "remove",
    "uninstall",
    "production",
    "prod",
    "database",
    "db",
    "backup",
}

class AutoApprovalEngine:
    """Motor para decidir si aprobar automáticamente un proceso."""

    def __init__(self, custom_patterns: Optional[Dict[str, bool]] = None):
        self.auto_approve = {**AUTO_APPROVE_PATTERNS}
        self.manual_approve = {**MANUAL_APPROVE_PATTERNS}

        if custom_patterns:
            self.auto_approve.update(custom_patterns)

    def should_auto_approve(self, proyecto: str, proceso: str, resultado: Optional[str] = None) -> bool:
        """
        Decidir si aprobar automáticamente.

        Returns:
            True si se debe aprobar automáticamente
            False si requiere aprobación manual
        """
        proceso_lower = proceso.lower()

        # Si el resultado es un error, nunca auto-aprobar
        if resultado and resultado.lower() in ["error", "failed", "timeout"]:
            return False

        # Si contiene palabras clave peligrosas, requiere aprobación
        if self._contains_danger_keywords(proceso_lower):
            return False

        # Si está en lista de manual approve, requiere aprobación
        for pattern in self.manual_approve:
            if pattern in proceso_lower:
                return False

        # Si está en lista de auto approve, auto-aprobar
        for pattern in self.auto_approve:
            if pattern in proceso_lower:
                return True

        # Por defecto, requerir aprobación
        return False

    def _contains_danger_keywords(self, text: str) -> bool:
        """Verificar si contiene palabras clave peligrosas."""
        for keyword in DANGER_KEYWORDS:
            if keyword in text:
                return True
        return False

    def get_auto_approve_list(self) -> List[str]:
        """Obtener lista de procesos que se auto-aprueban."""
        return list(self.auto_approve.keys())

    def get_manual_approve_list(self) -> List[str]:
        """Obtener lista de procesos que requieren aprobación."""
        return list(self.manual_approve.keys())

    def add_auto_approve_pattern(self, pattern: str):
        """Agregar un nuevo patrón de auto-aprobación."""
        self.auto_approve[pattern] = True
        # Remover de manual si estaba
        self.manual_approve.pop(pattern, None)

    def add_manual_approve_pattern(self, pattern: str):
        """Agregar un nuevo patrón que requiere aprobación manual."""
        self.manual_approve[pattern] = True
        # Remover de auto si estaba
        self.auto_approve.pop(pattern, None)
