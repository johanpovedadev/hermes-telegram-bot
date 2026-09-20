import pytest
from bot.core.workflows import (
    Workflow, WorkflowStep, WorkflowBuilder, WorkflowStatus, StepStatus,
    get_workflow_template, list_workflow_templates
)

class TestWorkflowStep:
    def test_create_step(self):
        """Test: crear un paso."""
        step = WorkflowStep(
            name="test",
            description="Ejecutar tests",
            command="pytest"
        )

        assert step.name == "test"
        assert step.status == StepStatus.PENDING

    def test_step_to_dict(self):
        """Test: convertir paso a dict."""
        step = WorkflowStep(
            name="test",
            description="Ejecutar tests",
            command="pytest",
            requires_approval=False
        )

        d = step.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "pending"
        assert d["requires_approval"] == False

class TestWorkflow:
    @pytest.fixture
    def workflow(self):
        return Workflow(name="Test Workflow", proyecto="p1")

    def test_create_workflow(self, workflow):
        """Test: crear workflow."""
        assert workflow.name == "Test Workflow"
        assert workflow.status == WorkflowStatus.PENDING
        assert len(workflow.steps) == 0

    def test_add_step(self, workflow):
        """Test: agregar paso a workflow."""
        step = WorkflowStep("test", "Test suite", "pytest")
        workflow.add_step(step)

        assert len(workflow.steps) == 1
        assert workflow.steps[0].name == "test"

    def test_get_current_step(self, workflow):
        """Test: obtener paso actual."""
        step1 = WorkflowStep("test", "Test", "pytest")
        step2 = WorkflowStep("build", "Build", "make")

        workflow.add_step(step1).add_step(step2)

        current = workflow.get_current_step()
        assert current.name == "test"

    def test_mark_step_completed(self, workflow):
        """Test: marcar paso como completado."""
        workflow.add_step(WorkflowStep("test", "Test", "pytest"))
        workflow.add_step(WorkflowStep("build", "Build", "make"))

        workflow.mark_step_completed(0, "All tests passed")

        assert workflow.steps[0].status == StepStatus.COMPLETED
        assert workflow.current_step_index == 1

    def test_mark_step_failed(self, workflow):
        """Test: marcar paso como fallido."""
        workflow.add_step(WorkflowStep("test", "Test", "pytest"))

        workflow.mark_step_failed(0, "Test failed")

        assert workflow.steps[0].status == StepStatus.FAILED
        assert workflow.steps[0].error == "Test failed"

    def test_get_progress(self, workflow):
        """Test: obtener progreso del workflow."""
        workflow.add_step(WorkflowStep("test", "Test", "pytest"))
        workflow.add_step(WorkflowStep("build", "Build", "make"))
        workflow.add_step(WorkflowStep("deploy", "Deploy", "deploy"))

        progress = workflow.get_progress()
        assert progress["total"] == 3
        assert progress["completed"] == 0
        assert progress["pending"] == 3

        workflow.mark_step_completed(0)
        progress = workflow.get_progress()
        assert progress["completed"] == 1
        assert progress["pending"] == 2

    def test_is_complete(self, workflow):
        """Test: verificar si workflow está completo."""
        workflow.add_step(WorkflowStep("test", "Test", "pytest"))
        workflow.add_step(WorkflowStep("build", "Build", "make"))

        assert workflow.is_complete() == False

        workflow.mark_step_completed(0)
        workflow.mark_step_completed(1)

        assert workflow.is_complete() == True

    def test_has_failures(self, workflow):
        """Test: verificar si hay fallos."""
        workflow.add_step(WorkflowStep("test", "Test", "pytest"))

        assert workflow.has_failures() == False

        workflow.mark_step_failed(0, "Failed")

        assert workflow.has_failures() == True

class TestWorkflowBuilder:
    def test_build_workflow(self):
        """Test: construir workflow con builder."""
        workflow = (
            WorkflowBuilder("CI Pipeline", "p1")
            .description("Complete CI pipeline")
            .add_step("test", "pytest", "Run tests", auto_approve=True)
            .add_step("build", "make", "Build project", auto_approve=True)
            .add_step("deploy", "deploy", "Deploy to prod", requires_approval=True)
            .build()
        )

        assert workflow.name == "CI Pipeline"
        assert workflow.description == "Complete CI pipeline"
        assert len(workflow.steps) == 3
        assert workflow.steps[0].auto_approve == True
        assert workflow.steps[2].requires_approval == True

    def test_builder_fluent_api(self):
        """Test: API fluida del builder."""
        builder = WorkflowBuilder("Test", "p1")
        result = (
            builder
            .description("Test workflow")
            .add_step("s1", "cmd1")
            .add_step("s2", "cmd2")
        )

        # Builder devuelve self para encadenamiento
        assert isinstance(result, WorkflowBuilder)

class TestWorkflowTemplates:
    def test_list_templates(self):
        """Test: listar templates disponibles."""
        templates = list_workflow_templates()

        assert "test-build-deploy" in templates
        assert "lint-format-commit" in templates
        assert "ci-pipeline" in templates

    def test_get_template_test_build_deploy(self):
        """Test: obtener template test-build-deploy."""
        workflow = get_workflow_template("test-build-deploy", "p1")

        assert workflow is not None
        assert workflow.name == "Test → Build → Deploy"
        assert len(workflow.steps) == 3
        assert workflow.steps[0].auto_approve == True  # test
        assert workflow.steps[2].requires_approval == True  # deploy

    def test_get_template_ci_pipeline(self):
        """Test: obtener template ci-pipeline."""
        workflow = get_workflow_template("ci-pipeline", "p1")

        assert workflow is not None
        assert len(workflow.steps) == 5
        assert all(s.auto_approve for s in workflow.steps)  # Todo auto-aprobado

    def test_get_nonexistent_template(self):
        """Test: intentar obtener template que no existe."""
        workflow = get_workflow_template("nonexistent", "p1")

        assert workflow is None

    def test_template_independence(self):
        """Test: templates son independientes."""
        w1 = get_workflow_template("test-build-deploy", "p1")
        w2 = get_workflow_template("test-build-deploy", "p2")

        # Deben ser diferentes instancias
        assert w1.id != w2.id
        assert w1.proyecto == "p1"
        assert w2.proyecto == "p2"
