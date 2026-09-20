import pytest
from bot.core.integrations import AnomalyDetector, RateLimiter

class TestAnomalyDetector:
    def test_history(self):
        detector = AnomalyDetector()
        for i in range(5):
            detector.add_metric("latency", 100 + i)
        assert len(detector.history["latency"]) == 5

    def test_detect_extreme_anomaly(self):
        detector = AnomalyDetector()
        for i in range(10):
            detector.add_metric("latency", 100)
        # Valor 100x más alto es definitivamente anomalía
        assert detector.is_anomaly("latency", 10000) == True

class TestRateLimiter:
    def test_allow_requests(self):
        limiter = RateLimiter(max_per_minute=5)
        for i in range(5):
            assert limiter.is_allowed("user1") == True

    def test_block_over_limit(self):
        limiter = RateLimiter(max_per_minute=3)
        for i in range(3):
            limiter.is_allowed("user1")
        assert limiter.is_allowed("user1") == False

    def test_status(self):
        limiter = RateLimiter()
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")

        status = limiter.get_status("user1")
        assert status["requests_minute"] == 2
