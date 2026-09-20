import pytest
from bot.core.alerts_rollback import (
    AlertManager, RollbackManager, AlertLevel, AlertConfig
)

class TestAlertConfig:
    def test_errors_only_level(self):
        """Test: notificar solo errores."""
        config = AlertConfig("p1", AlertLevel.ERRORS_ONLY)

        assert config.should_notify(is_error=True, is_important=False) == True
        assert config.should_notify(is_error=False, is_important=True) == False

    def test_important_changes_level(self):
        """Test: notificar errores e importantes."""
        config = AlertConfig("p1", AlertLevel.IMPORTANT_CHANGES)

        assert config.should_notify(is_error=True, is_important=False) == True
        assert config.should_notify(is_error=False, is_important=True) == True
        assert config.should_notify(is_error=False, is_important=False) == False

    def test_all_level(self):
        """Test: notificar todo."""
        config = AlertConfig("p1", AlertLevel.ALL)

        assert config.should_notify(is_error=True, is_important=False) == True
        assert config.should_notify(is_error=False, is_important=True) == True
        assert config.should_notify(is_error=False, is_important=False) == True

    def test_disabled_alerts(self):
        """Test: alertas desactivadas."""
        config = AlertConfig("p1", enabled=False)

        assert config.should_notify(is_error=True, is_important=True) == False

class TestRollbackManager:
    @pytest.fixture
    def manager(self):
        return RollbackManager()

    def test_create_rollback_point(self, manager):
        """Test: crear punto de rollback."""
        point = manager.create_rollback_point("p1", "abc123")

        assert point.proyecto == "p1"
        assert point.version_hash == "abc123"

    def test_should_rollback_threshold(self, manager):
        """Test: decidir si hacer rollback."""
        assert manager.should_rollback(2, "dep1") == False
        assert manager.should_rollback(3, "dep1") == True
        assert manager.should_rollback(5, "dep1") == True

    def test_list_rollback_points(self, manager):
        """Test: listar puntos de un proyecto."""
        manager.create_rollback_point("p1", "v1")
        manager.create_rollback_point("p1", "v2")
        manager.create_rollback_point("p2", "v3")

        p1_points = manager.list_rollback_points("p1")
        assert len(p1_points) == 2
        assert all(p.proyecto == "p1" for p in p1_points)

    def test_mark_for_rollback(self, manager):
        """Test: marcar punto para rollback."""
        point = manager.create_rollback_point("p1", "v1")

        assert manager.mark_for_rollback(point.id) == True
        assert point.metadata["marked_for_rollback"] == True

class TestAlertManager:
    @pytest.fixture
    def manager(self):
        return AlertManager()

    def test_set_alert_level(self, manager):
        """Test: configurar nivel de alertas."""
        manager.set_alert_level("p1", AlertLevel.ERRORS_ONLY)

        config = manager.get_alert_config("p1")
        assert config.level == AlertLevel.ERRORS_ONLY

    def test_should_alert(self, manager):
        """Test: decidir si alertar."""
        manager.set_alert_level("p1", AlertLevel.ERRORS_ONLY)

        assert manager.should_alert("p1", is_error=True, is_important=False) == True
        assert manager.should_alert("p1", is_error=False, is_important=True) == False

    def test_disable_enable_alerts(self, manager):
        """Test: desactivar/activar alertas."""
        manager.set_alert_level("p1", AlertLevel.ALL)

        manager.disable_alerts("p1")
        assert manager.should_alert("p1", True, True) == False

        manager.enable_alerts("p1")
        assert manager.should_alert("p1", True, True) == True

    def test_default_config_per_project(self, manager):
        """Test: config por defecto por proyecto."""
        config1 = manager.get_alert_config("p1")
        config2 = manager.get_alert_config("p2")

        assert config1.proyecto == "p1"
        assert config2.proyecto == "p2"
        assert config1 != config2

    def test_rollback_manager_integration(self, manager):
        """Test: integración con RollbackManager."""
        point = manager.rollback_manager.create_rollback_point("p1", "v1")

        assert point is not None
        retrieved = manager.rollback_manager.get_rollback_point(point.id)
        assert retrieved.version_hash == "v1"
