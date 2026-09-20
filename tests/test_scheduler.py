import pytest
from bot.core.scheduler import Scheduler, CronValidator, ScheduleStatus, ScheduledTask

class TestCronValidator:
    def test_valid_cron(self):
        """Test: cron válido."""
        is_valid, msg = CronValidator.validate("0 2 * * *")
        assert is_valid == True

    def test_invalid_cron_wrong_fields(self):
        """Test: cron con campos incorrectos."""
        is_valid, msg = CronValidator.validate("0 2 * *")
        assert is_valid == False
        assert "5 campos" in msg

    def test_invalid_hour(self):
        """Test: hora fuera de rango."""
        is_valid, msg = CronValidator.validate("0 25 * * *")
        assert is_valid == False

    def test_cron_with_wildcards(self):
        """Test: cron con comodines."""
        is_valid, msg = CronValidator.validate("* * * * *")
        assert is_valid == True

    def test_cron_with_ranges(self):
        """Test: cron con rangos."""
        is_valid, msg = CronValidator.validate("0-30 9-17 * * *")
        assert is_valid == True

class TestScheduler:
    @pytest.fixture
    def scheduler(self):
        return Scheduler()

    def test_create_task(self, scheduler):
        """Test: crear tarea programada."""
        task = scheduler.create_task(
            nombre="daily-test",
            proyecto="p1",
            comando="test",
            cron="0 2 * * *"
        )

        assert task.name == "daily-test"
        assert task.cron_expression == "0 2 * * *"
        assert task.status == ScheduleStatus.ACTIVE

    def test_create_task_invalid_cron(self, scheduler):
        """Test: crear tarea con cron inválido."""
        with pytest.raises(ValueError):
            scheduler.create_task(
                nombre="bad",
                proyecto="p1",
                comando="test",
                cron="invalid"
            )

    def test_list_tasks(self, scheduler):
        """Test: listar tareas."""
        scheduler.create_task("t1", "p1", "test", "0 2 * * *")
        scheduler.create_task("t2", "p1", "build", "0 3 * * *")
        scheduler.create_task("t3", "p2", "deploy", "0 4 * * *")

        all_tasks = scheduler.list_tasks()
        assert len(all_tasks) == 3

        p1_tasks = scheduler.list_tasks(proyecto="p1")
        assert len(p1_tasks) == 2

    def test_pause_resume_task(self, scheduler):
        """Test: pausar y reanudar tarea."""
        task = scheduler.create_task("t1", "p1", "test", "0 2 * * *")

        assert scheduler.pause_task(task.id) == True
        assert scheduler.get_task(task.id).status == ScheduleStatus.PAUSED

        assert scheduler.resume_task(task.id) == True
        assert scheduler.get_task(task.id).status == ScheduleStatus.ACTIVE

    def test_delete_task(self, scheduler):
        """Test: eliminar tarea."""
        task = scheduler.create_task("t1", "p1", "test", "0 2 * * *")

        assert scheduler.delete_task(task.id) == True
        assert scheduler.get_task(task.id) is None

    def test_mark_run(self, scheduler):
        """Test: marcar ejecución."""
        task = scheduler.create_task("t1", "p1", "test", "0 2 * * *")

        assert task.run_count == 0
        scheduler.mark_run(task.id)

        updated_task = scheduler.get_task(task.id)
        assert updated_task.run_count == 1
        assert updated_task.last_run is not None

    def test_common_expressions(self, scheduler):
        """Test: expresiones cron comunes."""
        assert scheduler.get_common_expression("hourly") == "0 * * * *"
        assert scheduler.get_common_expression("daily") == "0 0 * * *"
        assert scheduler.get_common_expression("daily-2am") == "0 2 * * *"

    def test_list_common_expressions(self, scheduler):
        """Test: listar expresiones comunes."""
        exprs = scheduler.list_common_expressions()

        assert "hourly" in exprs
        assert "daily" in exprs
        assert "weekly" in exprs
        assert "monthly" in exprs
