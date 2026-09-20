from typing import Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio

class ErrorType(Enum):
    """Tipos de errores reconocibles."""
    NETWORK = "network"        # ConnectionError, timeout de red
    TIMEOUT = "timeout"        # Timeout genérico
    RATE_LIMIT = "rate_limit"  # HTTP 429, rate limiting
    COMPILE_ERROR = "compile"  # Error de compilación, sintaxis
    RUNTIME_ERROR = "runtime"  # Error en tiempo de ejecución
    UNKNOWN = "unknown"        # Error desconocido

@dataclass
class RetryConfig:
    """Configuración de reintentos para cada tipo de error."""
    max_retries: int
    initial_delay: float = 2.0      # segundos
    max_delay: float = 32.0         # segundos
    exponential_base: float = 2.0   # factor de crecimiento
    jitter: bool = True             # agregar aleatoriedad

class RetryPolicy:
    """Política de reintentos inteligentes por tipo de error."""

    # Configuración por tipo de error
    DEFAULT_RETRY_CONFIG = {
        ErrorType.NETWORK: RetryConfig(max_retries=3),
        ErrorType.TIMEOUT: RetryConfig(max_retries=2),
        ErrorType.RATE_LIMIT: RetryConfig(max_retries=5, initial_delay=5.0),
        ErrorType.COMPILE_ERROR: RetryConfig(max_retries=0),  # No reintentar
        ErrorType.RUNTIME_ERROR: RetryConfig(max_retries=1),
        ErrorType.UNKNOWN: RetryConfig(max_retries=1),
    }

    def __init__(self, custom_config: Optional[Dict[ErrorType, RetryConfig]] = None):
        self.config = {**self.DEFAULT_RETRY_CONFIG}
        if custom_config:
            self.config.update(custom_config)

    def detect_error_type(self, stderr: str, exception: Optional[Exception] = None) -> ErrorType:
        """Detectar el tipo de error del mensaje de error."""
        error_lower = stderr.lower()

        # Compile errors
        if any(kw in error_lower for kw in ["syntaxerror", "parseerror", "compilation failed", "compile error"]):
            return ErrorType.COMPILE_ERROR

        # Network errors
        if any(kw in error_lower for kw in ["connection", "refused", "unreachable", "network", "socket"]):
            return ErrorType.NETWORK

        # Timeout errors
        if any(kw in error_lower for kw in ["timeout", "timed out", "deadline exceeded"]):
            return ErrorType.TIMEOUT

        # Rate limiting
        if any(kw in error_lower for kw in ["429", "rate limit", "too many requests", "throttle"]):
            return ErrorType.RATE_LIMIT

        # Runtime errors (pero no syntax)
        if any(kw in error_lower for kw in ["error", "exception", "failed", "fail", "zero", "invalid"]):
            if "syntaxerror" not in error_lower:
                return ErrorType.RUNTIME_ERROR

        return ErrorType.UNKNOWN

    def should_retry(self, error_type: ErrorType, attempt: int) -> bool:
        """Decidir si reintentar basado en el tipo de error y número de intento."""
        config = self.config.get(error_type, self.config[ErrorType.UNKNOWN])
        return attempt < config.max_retries

    def get_retry_delay(self, error_type: ErrorType, attempt: int) -> float:
        """Calcular el delay hasta el próximo intento (exponential backoff)."""
        config = self.config.get(error_type, self.config[ErrorType.UNKNOWN])

        # Exponential backoff
        delay = config.initial_delay * (config.exponential_base ** attempt)
        delay = min(delay, config.max_delay)

        # Jitter (agregar aleatoriedad para evitar thundering herd)
        if config.jitter:
            import random
            delay *= (0.5 + random.random())  # 0.5x a 1.5x del delay
            delay = min(delay, config.max_delay)  # Asegurar que jitter no excede max

        return delay

    def get_retry_config(self, error_type: ErrorType) -> RetryConfig:
        """Obtener configuración para un tipo de error."""
        return self.config.get(error_type, self.config[ErrorType.UNKNOWN])

    def get_retry_summary(self, error_type: ErrorType) -> Dict:
        """Obtener resumen de reintentos para un tipo de error."""
        config = self.get_retry_config(error_type)
        return {
            "error_type": error_type.value,
            "max_retries": config.max_retries,
            "initial_delay": config.initial_delay,
            "max_delay": config.max_delay,
            "exponential_base": config.exponential_base,
            "will_retry": config.max_retries > 0
        }

async def retry_with_backoff(
    func: Callable,
    *args,
    retry_policy: RetryPolicy,
    error_type: ErrorType = ErrorType.UNKNOWN,
    max_attempts: Optional[int] = None,
    **kwargs
) -> tuple:
    """
    Ejecutar una función con reintentos inteligentes.

    Returns:
        (success, result, attempts, final_error)
    """
    config = retry_policy.get_retry_config(error_type)
    max_attempts = max_attempts or config.max_retries + 1

    last_error = None

    for attempt in range(max_attempts):
        try:
            result = await func(*args, **kwargs)
            return True, result, attempt + 1, None
        except Exception as e:
            last_error = e
            stderr = str(e)
            detected_type = retry_policy.detect_error_type(stderr, e)

            if not retry_policy.should_retry(detected_type, attempt):
                return False, None, attempt + 1, str(e)

            delay = retry_policy.get_retry_delay(detected_type, attempt)
            await asyncio.sleep(delay)

    return False, None, max_attempts, str(last_error)
