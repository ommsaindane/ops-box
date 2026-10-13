"""
workspace/manager.py

Manages ephemeral per-task workspaces on disk, ensuring safe path traversal boundaries,
atomic operations, and automated garbage collection of expired workspaces.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileInfo:
    filename: str
    size_bytes: int
    modified_at: float


class WorkspaceManager:
    """
    Provisions, inspects, and purges isolated disk directories per task.
    """

    def __init__(
        self,
        base_dir: str | Path = "data/workspaces",
        default_ttl_seconds: int = 3600,  # 1 hour workspace lifespan
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.default_ttl_seconds = default_ttl_seconds
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, task_id: Optional[str] = None) -> Path:
        """Creates and returns an isolated directory for a task."""
        resolved_id = task_id or uuid.uuid4().hex
        workspace_path = (self.base_dir / f"task_{resolved_id}").resolve()
        workspace_path.mkdir(parents=True, exist_ok=True)
        return workspace_path

    def get_workspace_path(self, task_id: str) -> Path:
        """Returns the absolute path to a workspace, ensuring it resides inside base_dir."""
        workspace_path = (self.base_dir / f"task_{task_id}").resolve()
        if not self._is_safe_path(workspace_path):
            raise PermissionError("Access denied: Traversal out of workspace boundaries.")
        return workspace_path

    def write_file(self, task_id: str, relative_path: str, content: str) -> Path:
        """
        Safely writes text to a file inside the task workspace.
        Prevents directory traversal attacks (e.g., ../../secrets).
        """
        workspace = self.get_workspace_path(task_id)
        target_path = (workspace / relative_path).resolve()

        if not str(target_path).startswith(str(workspace)):
            raise PermissionError(f"Directory traversal detected: {relative_path}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return target_path

    def read_file(self, task_id: str, relative_path: str) -> str:
        """Reads a file from the task workspace, preventing path traversal."""
        workspace = self.get_workspace_path(task_id)
        target_path = (workspace / relative_path).resolve()

        if not str(target_path).startswith(str(workspace)):
            raise PermissionError(f"Directory traversal detected: {relative_path}")

        if not target_path.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")

        return target_path.read_text(encoding="utf-8")

    def list_files(self, task_id: str) -> List[FileInfo]:
        """Lists all files present in a task workspace."""
        workspace = self.get_workspace_path(task_id)
        if not workspace.exists():
            return []

        files: List[FileInfo] = []
        for root, _, filenames in os.walk(workspace):
            for file in filenames:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(workspace)
                stat = full_path.stat()
                files.append(
                    FileInfo(
                        filename=str(rel_path),
                        size_bytes=stat.st_size,
                        modified_at=stat.st_mtime,
                    )
                )
        return files

    def delete_workspace(self, task_id: str) -> bool:
        """Removes the task workspace directory and all contained files."""
        try:
            workspace = self.get_workspace_path(task_id)
            if workspace.exists() and workspace.is_dir():
                shutil.rmtree(workspace)
                return True
        except Exception as exc:
            logger.error("Failed to delete workspace for task %s: %s", task_id, exc)
        return False

    def cleanup_expired_workspaces(self, custom_ttl_seconds: Optional[int] = None) -> int:
        """
        Garbage collection function: scans the base directory and purges
        any task workspace older than TTL.
        """
        ttl = custom_ttl_seconds or self.default_ttl_seconds
        now = time.time()
        purged_count = 0

        for entry in self.base_dir.iterdir():
            if entry.is_dir() and entry.name.startswith("task_"):
                try:
                    dir_mtime = entry.stat().st_mtime
                    if now - dir_mtime > ttl:
                        shutil.rmtree(entry)
                        purged_count += 1
                        logger.info("Purged expired workspace: %s", entry.name)
                except Exception as exc:
                    logger.warning("Error inspecting workspace %s during GC: %s", entry.name, exc)

        return purged_count

    def _is_safe_path(self, target_path: Path) -> bool:
        """Verifies that the target path does not escape the configured base directory."""
        return str(target_path).startswith(str(self.base_dir))