from llm.client import LLMClient
from orchestrator.orchestrator import Orchestrator
from sandbox.docker_runner import DockerRunner
from workspace.manager import WorkspaceManager


def get_orchestrator() -> Orchestrator:
    llm = LLMClient()

    workspace_manager = WorkspaceManager()

    docker_runner = DockerRunner()

    return Orchestrator(
        llm=llm,
        workspace_manager=workspace_manager,
        docker_runner=docker_runner,
    )
