import pytest
from bot.core.retry_policy import RetryPolicy, ErrorType, RetryConfig

class TestRetryPolicy:
    @pytest.fixture
    def policy(self):
        return RetryPolicy()

    def test_detect_network_error(self, policy):
        """Test: detectar errores de red."""
        assert policy.detect_error_type("Connection refused") == ErrorType.NETWORK
        assert policy.detect_error_type("Socket error") == ErrorType.NETWORK
        assert policy.detect_error_type("Network unreachable") == ErrorType.NETWORK

    def test_detect_timeout_error(self, policy):
        """Test: detectar timeouts."""
        assert policy.detect_error_type("Timeout after 30s") == ErrorType.TIMEOUT
        assert policy.detect_error_type("Request timed out") == ErrorType.TIMEOUT

    def test_detect_compile_error(self, policy):
        """Test: detectar errores de compilación."""
        assert policy.detect_error_type("SyntaxError at line 10") == ErrorType.COMPILE_ERROR
        assert policy.detect_error_type("Compilation failed") == ErrorType.COMPILE_ERROR

    def test_detect_rate_limit_error(self, policy):
        """Test: detectar rate limiting."""
        assert policy.detect_error_type("429 Too Many Requests") == ErrorType.RATE_LIMIT
        assert policy.detect_error_type("Rate limit exceeded") == ErrorType.RATE_LIMIT

    def test_detect_runtime_error(self, policy):
        """Test: detectar errores en tiempo de ejecución."""
        assert policy.detect_error_type("RuntimeError: invalid state") == ErrorType.RUNTIME_ERROR
        assert policy.detect_error_type("Division by zero") == ErrorType.RUNTIME_ERROR

    def test_should_retry_network_error(self, policy):
        """Test: reintentar 3 veces en errores de red."""
        for attempt in range(3):
            assert policy.should_retry(ErrorType.NETWORK, attempt) == True
        assert policy.should_retry(ErrorType.NETWORK, 3) == False

    def test_should_not_retry_compile_error(self, policy):
        """Test: no reintentar errores de compilación."""
        assert policy.should_retry(ErrorType.COMPILE_ERROR, 0) == False

    def test_should_retry_timeout_twice(self, policy):
        """Test: reintentar timeout máximo 2 veces."""
        assert policy.should_retry(ErrorType.TIMEOUT, 0) == True
        assert policy.should_retry(ErrorType.TIMEOUT, 1) == True
        assert policy.should_retry(ErrorType.TIMEOUT, 2) == False

    def test_retry_delay_exponential_backoff(self, policy, monkeypatch):
        """Test: delay con exponential backoff. El jitter (0.5x-1.5x) se fija en 1x: si no, a veces delay1 < delay0."""
        import random
        monkeypatch.setattr(random, "random", lambda: 0.5)
        delay0 = policy.get_retry_delay(ErrorType.NETWORK, 0)
        delay1 = policy.get_retry_delay(ErrorType.NETWORK, 1)

        # Sin jitter, delay1 debería ser ~2x delay0
        assert delay1 > delay0
        assert delay0 < 10  # initial_delay es 2.0

    def test_retry_delay_has_max(self, policy):
        """Test: delay tiene máximo."""
        delay_many = policy.get_retry_delay(ErrorType.NETWORK, 100)
        config = policy.get_retry_config(ErrorType.NETWORK)

        assert delay_many <= config.max_delay

    def test_rate_limit_longer_delay(self, policy):
        """Test: rate limiting tiene delay más largo."""
        network_delay = policy.get_retry_delay(ErrorType.NETWORK, 0)
        rate_limit_delay = policy.get_retry_delay(ErrorType.RATE_LIMIT, 0)

        # Rate limit debería tener initial_delay más largo
        assert rate_limit_delay > network_delay

    def test_get_retry_summary(self, policy):
        """Test: obtener resumen de reintentos."""
        summary = policy.get_retry_summary(ErrorType.NETWORK)

        assert summary["error_type"] == "network"
        assert summary["max_retries"] == 3
        assert summary["will_retry"] == True

        summary_compile = policy.get_retry_summary(ErrorType.COMPILE_ERROR)
        assert summary_compile["will_retry"] == False

    def test_custom_retry_config(self):
        """Test: configuración personalizada."""
        custom = {
            ErrorType.NETWORK: RetryConfig(max_retries=5)
        }
        policy = RetryPolicy(custom_config=custom)

        for attempt in range(5):
            assert policy.should_retry(ErrorType.NETWORK, attempt) == True
        assert policy.should_retry(ErrorType.NETWORK, 5) == False

class TestRetryPolicyIntegration:
    def test_all_error_types_configured(self):
        """Test: todos los tipos de error tienen configuración."""
        policy = RetryPolicy()

        for error_type in ErrorType:
            config = policy.get_retry_config(error_type)
            assert config is not None
            assert config.max_retries >= 0

    def test_error_detection_coverage(self):
        """Test: cobertura de detección de errores."""
        policy = RetryPolicy()

        test_cases = [
            ("Connection refused", ErrorType.NETWORK),
            ("Timeout", ErrorType.TIMEOUT),
            ("SyntaxError", ErrorType.COMPILE_ERROR),
            ("429 Too Many Requests", ErrorType.RATE_LIMIT),
            ("Something failed", ErrorType.RUNTIME_ERROR),
        ]

        for error_msg, expected_type in test_cases:
            detected = policy.detect_error_type(error_msg)
            assert detected == expected_type
