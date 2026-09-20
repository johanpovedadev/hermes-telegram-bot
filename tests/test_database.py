import pytest
import os
from bot.core.database import Database

class TestDatabase:
    @pytest.fixture
    def db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return Database(db_path=db_path)

    def test_save_notification(self, db):
        """Test: guardar notificación."""
        notif = {
            'id': 'n1',
            'proyecto': 'p1',
            'proceso': 'test',
            'timestamp': '2026-09-20T10:00:00Z',
            'estado': 'pendiente',
            'resultado': None,
            'approved_at': None,
            'approved_by': None,
        }

        assert db.save_notification(notif) == True

    def test_save_workflow(self, db):
        """Test: guardar workflow."""
        workflow = {
            'id': 'w1',
            'name': 'Test Workflow',
            'proyecto': 'p1',
            'status': 'running',
            'created_at': '2026-09-20T10:00:00Z',
            'started_at': None,
            'completed_at': None,
            'steps': [],
        }

        assert db.save_workflow(workflow) == True

    def test_save_scheduled_task(self, db):
        """Test: guardar tarea programada."""
        task = {
            'id': 't1',
            'name': 'Daily Test',
            'proyecto': 'p1',
            'comando': 'test',
            'cron_expression': '0 2 * * *',
            'status': 'active',
            'created_at': '2026-09-20T10:00:00Z',
            'last_run': None,
            'run_count': 0,
        }

        assert db.save_scheduled_task(task) == True

    def test_save_webhook(self, db):
        """Test: guardar webhook."""
        webhook = {
            'id': 'wh1',
            'name': 'Slack Webhook',
            'url': 'https://hooks.slack.com/...',
            'event_type': 'deployment_complete',
            'proyecto': 'p1',
            'active': True,
            'created_at': '2026-09-20T10:00:00Z',
        }

        assert db.save_webhook(webhook) == True

    def test_record_metric(self, db):
        """Test: registrar métrica."""
        assert db.record_metric('p1', 'test', 'success', 1500) == True

    def test_get_notifications(self, db):
        """Test: obtener notificaciones."""
        notif1 = {'id': 'n1', 'proyecto': 'p1', 'proceso': 'test', 'timestamp': '2026-09-20T10:00:00Z', 'estado': 'pendiente', 'resultado': None, 'approved_at': None, 'approved_by': None}
        notif2 = {'id': 'n2', 'proyecto': 'p1', 'proceso': 'build', 'timestamp': '2026-09-20T10:01:00Z', 'estado': 'aprobado', 'resultado': None, 'approved_at': None, 'approved_by': None}

        db.save_notification(notif1)
        db.save_notification(notif2)

        notifs = db.get_notifications(proyecto='p1')
        assert len(notifs) == 2

    def test_delete_notification(self, db):
        """Test: eliminar notificación."""
        notif = {'id': 'n1', 'proyecto': 'p1', 'proceso': 'test', 'timestamp': '2026-09-20T10:00:00Z', 'estado': 'pendiente', 'resultado': None, 'approved_at': None, 'approved_by': None}

        db.save_notification(notif)
        assert db.delete_notification('n1') == True

        notifs = db.get_notifications()
        assert len(notifs) == 0
