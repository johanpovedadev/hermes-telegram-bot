import pytest
from bot.core.auto_approval import AutoApprovalEngine
from bot.core.notifications import NotificationManager

class TestAutoApprovalEngine:
    @pytest.fixture
    def engine(self):
        return AutoApprovalEngine()

    def test_auto_approve_safe_processes(self, engine):
        """Test: procesos seguros se auto-aprueban."""
        assert engine.should_auto_approve("p1", "test") == True
        assert engine.should_auto_approve("p1", "lint") == True
        assert engine.should_auto_approve("p1", "format code") == True
        assert engine.should_auto_approve("p1", "build project") == True
        assert engine.should_auto_approve("p1", "install dependencies") == True

    def test_manual_approve_dangerous_processes(self, engine):
        """Test: procesos peligrosos requieren aprobación."""
        assert engine.should_auto_approve("p1", "deploy") == False
        assert engine.should_auto_approve("p1", "deploy to production") == False
        assert engine.should_auto_approve("p1", "release v1.0") == False
        assert engine.should_auto_approve("p1", "publish to prod") == False

    def test_danger_keywords_block_approval(self, engine):
        """Test: palabras clave peligrosas bloquean auto-aprobación."""
        assert engine.should_auto_approve("p1", "run tests with delete flag") == False
        assert engine.should_auto_approve("p1", "drop database") == False
        assert engine.should_auto_approve("p1", "remove production data") == False
        assert engine.should_auto_approve("p1", "uninstall system") == False

    def test_failed_results_never_approve(self, engine):
        """Test: resultados fallidos nunca se auto-aprueban."""
        assert engine.should_auto_approve("p1", "test", resultado="error") == False
        assert engine.should_auto_approve("p1", "test", resultado="failed") == False
        assert engine.should_auto_approve("p1", "build", resultado="timeout") == False

    def test_successful_results_follow_pattern(self, engine):
        """Test: resultados exitosos siguen el patrón."""
        assert engine.should_auto_approve("p1", "test", resultado="success") == True
        assert engine.should_auto_approve("p1", "deploy", resultado="success") == False

    def test_case_insensitive_matching(self, engine):
        """Test: matching es case-insensitive."""
        assert engine.should_auto_approve("p1", "TEST") == True
        assert engine.should_auto_approve("p1", "DEPLOY") == False
        assert engine.should_auto_approve("p1", "LiNt") == True

    def test_get_auto_approve_list(self, engine):
        """Test: obtener lista de auto-aprobación."""
        auto_list = engine.get_auto_approve_list()
        assert "test" in auto_list
        assert "lint" in auto_list
        assert "format" in auto_list
        assert len(auto_list) > 5

    def test_get_manual_approve_list(self, engine):
        """Test: obtener lista de aprobación manual."""
        manual_list = engine.get_manual_approve_list()
        assert "deploy" in manual_list
        assert "release" in manual_list
        assert "delete" in manual_list

    def test_add_custom_auto_approve_pattern(self, engine):
        """Test: agregar patrón personalizado."""
        engine.add_auto_approve_pattern("custom-task")
        assert engine.should_auto_approve("p1", "custom-task") == True

    def test_add_custom_manual_approve_pattern(self, engine):
        """Test: agregar patrón que requiere aprobación."""
        engine.add_manual_approve_pattern("risky-operation")
        assert engine.should_auto_approve("p1", "risky-operation") == False

    def test_moving_pattern_between_lists(self, engine):
        """Test: mover patrón entre listas."""
        # Inicialmente test se auto-aprueba
        assert engine.should_auto_approve("p1", "test") == True

        # Moverlo a manual
        engine.add_manual_approve_pattern("test")
        assert engine.should_auto_approve("p1", "test") == False

        # Moverlo de vuelta a auto
        engine.add_auto_approve_pattern("test")
        assert engine.should_auto_approve("p1", "test") == True

    def test_custom_patterns_in_constructor(self):
        """Test: patrones personalizados en constructor."""
        custom = {"my-safe-task": True}
        engine = AutoApprovalEngine(custom_patterns=custom)

        assert engine.should_auto_approve("p1", "my-safe-task") == True
        assert engine.should_auto_approve("p1", "test") == True

class TestAutoApprovalIntegration:
    @pytest.fixture
    def nm(self, temp_data_dir):
        engine = AutoApprovalEngine()
        return NotificationManager(data_dir=str(temp_data_dir), auto_approval_engine=engine)

    def test_notification_manager_auto_approval_check(self, nm):
        """Test: verificar auto-aprobación en NotificationManager."""
        should_approve, reason = nm.debe_auto_aprobar("p1", "test")
        assert should_approve == True
        assert "Auto-aprobado" in reason

    def test_notification_manager_manual_approval_check(self, nm):
        """Test: verificar que deploy requiere aprobación manual."""
        should_approve, reason = nm.debe_auto_aprobar("p1", "deploy")
        assert should_approve == False
        assert "Requiere aprobación manual" in reason

    def test_notification_manager_with_error(self, nm):
        """Test: error siempre requiere aprobación."""
        should_approve, reason = nm.debe_auto_aprobar("p1", "test", resultado="error")
        assert should_approve == False
