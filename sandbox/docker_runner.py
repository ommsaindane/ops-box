from pathlib import Path

import docker
from docker import DockerClient
from docker.errors import DockerException

from schemas.execution import ExecutionResult


class DockerRunner:
    def __init__(
        self,
        client: DockerClient | None = None,
        image: str = "python:3.11-slim",
        memory_limit: str = "512m",
        cpu_quota: int = 50000,
        timeout: int = 30,
    ):
        self.client = client or docker.from_env()

        self.image = image
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota
        self.timeout = timeout

    def run(
        self,
        workspace: Path,
        command: list[str],
    ) -> ExecutionResult:

        container = None

        try:
            container = self.client.containers.run(
                image=self.image,
                command=command,
                working_dir="/workspace",
                volumes={
                    str(workspace.resolve()): {
                        "bind": "/workspace",
                        "mode": "rw",
                    }
                },
                network_disabled=True,
                mem_limit=self.memory_limit,
                cpu_quota=self.cpu_quota,
                detach=True,
                stderr=True,
                stdout=True,
            )

            result = container.wait(timeout=self.timeout)

            stdout = container.logs(
                stdout=True,
                stderr=False,
            ).decode("utf-8")

            stderr = container.logs(
                stdout=False,
                stderr=True,
            ).decode("utf-8")

            exit_code = result["StatusCode"]

            return ExecutionResult(
                success=exit_code == 0,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
            )

        except DockerException as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                error=str(e),
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="",
                error=str(e),
            )

        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
