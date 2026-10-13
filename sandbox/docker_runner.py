"""
sandbox/docker_runner.py

Hardened, isolated container execution environment for running untrusted LLM-generated code.
Includes CPU/memory limits, capability stripping, network isolation, deterministic timeouts,
and async execution wrappers to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
from docker.errors import APIError, DockerException, ImageNotFound
from docker.models.containers import Container

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable result structure for sandboxed command execution."""
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error_message: Optional[str] = None


class HardenedDockerRunner:
    """
    Manages isolated, ephemeral container lifecycles to safely execute arbitrary code.
    """

    def __init__(
        self,
        base_image: str = "python:3.11-slim",
        default_timeout_seconds: int = 15,
        max_output_bytes: int = 200 * 1024,  # 200 KB output buffer cap
        memory_limit: str = "256m",
        cpu_quota_cores: float = 1.0,
        max_pids: int = 64,
    ) -> None:
        self.base_image = base_image
        self.default_timeout_seconds = default_timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.memory_limit = memory_limit
        self.nano_cpus = int(cpu_quota_cores * 1_000_000_000)
        self.max_pids = max_pids

        try:
            self.client = docker.from_env()
            self.client.ping()
        except DockerException as exc:
            logger.error("Unable to connect to Docker daemon: %s", exc)
            raise RuntimeError(
                "Docker daemon is unreachable. Verify Docker is running and active."
            ) from exc

        self._ensure_image_present()

    def _ensure_image_present(self) -> None:
        """Pulls the configured base image if not available locally."""
        try:
            self.client.images.get(self.base_image)
        except ImageNotFound:
            logger.info("Image '%s' not found locally. Pulling...", self.base_image)
            try:
                self.client.images.pull(self.base_image)
            except DockerException as exc:
                logger.error("Failed to pull image '%s': %s", self.base_image, exc)
                raise RuntimeError(f"Could not pull sandbox image {self.base_image}") from exc

    def run_command_sync(
        self,
        workspace_host_path: str | Path,
        command: List[str] | str,
        timeout: Optional[int] = None,
        allow_network: bool = False,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """
        Synchronously runs a command in an isolated container.
        """
        resolved_path = Path(workspace_host_path).resolve()
        if not resolved_path.is_dir():
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=f"Workspace path does not exist or is not a directory: {resolved_path}",
            )

        effective_timeout = timeout if timeout is not None else self.default_timeout_seconds
        container: Optional[Container] = None

        environment = {
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": "/tmp",
        }
        if env_vars:
            environment.update(env_vars)

        # Host security & resource boundaries
        host_config_kwargs: Dict[str, Any] = {
            "mem_limit": self.memory_limit,
            "memswap_limit": self.memory_limit,  # Disables swap to enforce hard memory cap
            "nano_cpus": self.nano_cpus,
            "pids_limit": self.max_pids,
            "cap_drop": ["ALL"],                # Drop all kernel capabilities
            "security_opt": ["no-new-privileges:true"],
            "network_mode": "bridge" if allow_network else "none",
        }

        # Mount workspace to /workspace
        volumes = {
            str(resolved_path): {
                "bind": "/workspace",
                "mode": "rw",
            }
        }

        try:
            # Note: stdout and stderr are not parameters for containers.create
            container = self.client.containers.create(
                image=self.base_image,
                command=command,
                working_dir="/workspace",
                volumes=volumes,
                environment=environment,
                detach=True,
                **host_config_kwargs,
            )

            container.start()

            timed_out = False
            try:
                result = container.wait(timeout=effective_timeout)
                exit_code = result.get("StatusCode", -1)
            except Exception:
                timed_out = True
                exit_code = 124  # POSIX standard timeout exit code
                try:
                    container.kill()
                except APIError:
                    pass

            raw_stdout = container.logs(stdout=True, stderr=False)[: self.max_output_bytes]
            raw_stderr = container.logs(stdout=False, stderr=True)[: self.max_output_bytes]

            return ExecutionResult(
                exit_code=exit_code,
                stdout=raw_stdout.decode("utf-8", errors="replace"),
                stderr=raw_stderr.decode("utf-8", errors="replace"),
                timed_out=timed_out,
                error_message="Execution timed out" if timed_out else None,
            )

        except DockerException as exc:
            logger.exception("Docker runtime encountered an error: %s", exc)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="",
                error_message=f"Docker runtime error: {exc}",
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception as exc:
                    logger.debug("Container cleanup failed for %s: %s", container.id, exc)

    async def run_command(
        self,
        workspace_host_path: str | Path,
        command: List[str] | str,
        timeout: Optional[int] = None,
        allow_network: bool = False,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """
        Non-blocking async wrapper that offloads Docker execution to a worker thread.
        """
        return await asyncio.to_thread(
            self.run_command_sync,
            workspace_host_path=workspace_host_path,
            command=command,
            timeout=timeout,
            allow_network=allow_network,
            env_vars=env_vars,
        )