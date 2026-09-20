import pytest
import os
from bot.core.notifications import NotificationManager, Notification

class TestNotificationManager:
    @pytest.fixture
    def nm(self, temp_data_dir):
        """NotificationManager con directorio temporal."""
        return NotificationManager(data_dir=str(temp_data_dir))

    def test_crear_notificacion(self, nm):
        """Test: crear una notificación."""
        notif = nm.crear_notificacion(
            notif_id="test-001",
            proyecto="mi-proyecto",
            proceso="instalar dependencias"
        )

        assert notif.id == "test-001"
        assert notif.proyecto == "mi-proyecto"
        assert notif.proceso == "instalar dependencias"
        assert notif.estado == "pendiente"

    def test_obtener_pendientes(self, nm):
        """Test: obtener notificaciones pendientes."""
        nm.crear_notificacion("t1", "p1", "test")
        nm.crear_notificacion("t2", "p1", "build")
        nm.crear_notificacion("t3", "p2", "deploy")

        pendientes = nm.obtener_pendientes()
        assert len(pendientes) == 3
        assert all(n.estado == "pendiente" for n in pendientes)

    def test_aprobar_notificacion(self, nm):
        """Test: aprobar una notificación."""
        nm.crear_notificacion("t1", "p1", "test")

        assert nm.aprobar("t1", user_id=12345)

        pendientes = nm.obtener_pendientes()
        assert len(pendientes) == 0

        todas = nm.obtener_todas()
        assert todas[0].estado == "aprobado"
        assert todas[0].approved_by == "12345"

    def test_rechazar_notificacion(self, nm):
        """Test: rechazar una notificación."""
        nm.crear_notificacion("t1", "p1", "test")

        assert nm.rechazar("t1")

        todas = nm.obtener_todas()
        assert todas[0].estado == "rechazado"

    def test_obtener_por_proyecto(self, nm):
        """Test: obtener notificaciones por proyecto."""
        nm.crear_notificacion("t1", "proyecto-a", "test")
        nm.crear_notificacion("t2", "proyecto-a", "build")
        nm.crear_notificacion("t3", "proyecto-b", "deploy")

        notifs_a = nm.obtener_por_proyecto("proyecto-a")
        assert len(notifs_a) == 2
        assert all(n.proyecto == "proyecto-a" for n in notifs_a)

    def test_metricas_confiabilidad(self, nm):
        """Test: calcular métricas de confiabilidad."""
        nm.crear_notificacion("t1", "p1", "test")
        nm.crear_notificacion("t2", "p1", "test")
        nm.crear_notificacion("t3", "p1", "build")

        nm.aprobar("t1")
        nm.rechazar("t2")
        nm.aprobar("t3")

        metricas = nm.obtener_metricas("p1")

        assert metricas["test"]["total"] == 2
        assert metricas["test"]["success"] == 1
        assert metricas["test"]["failed"] == 1
        assert metricas["build"]["success"] == 1

    def test_estadisticas_proyecto(self, nm):
        """Test: obtener estadísticas completas de un proyecto."""
        nm.crear_notificacion("t1", "p1", "test")
        nm.crear_notificacion("t2", "p1", "build")
        nm.crear_notificacion("t3", "p1", "deploy")

        nm.aprobar("t1")
        nm.rechazar("t2")
        # t3 sigue pendiente

        stats = nm.obtener_estadisticas_proyecto("p1")

        assert stats["proyecto"] == "p1"
        assert stats["total_procesos"] == 3
        assert stats["aprobados"] == 1
        assert stats["rechazados"] == 1
        assert stats["pendientes"] == 1

    def test_persistencia(self, temp_data_dir):
        """Test: datos persisten entre instancias."""
        nm1 = NotificationManager(data_dir=str(temp_data_dir))
        nm1.crear_notificacion("t1", "p1", "test")

        nm2 = NotificationManager(data_dir=str(temp_data_dir))
        todas = nm2.obtener_todas()

        assert len(todas) == 1
        assert todas[0].id == "t1"
