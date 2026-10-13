"""
tests/test_workspace.py

Unit tests for WorkspaceManager: isolation, path traversal defense, and GC.
"""

import os
import time
import pytest
from pathlib import Path
from workspace.manager import WorkspaceManager


@pytest.fixture
def temp_workspace_mgr(tmp_path: Path) -> WorkspaceManager:
    return WorkspaceManager(base_dir=tmp_path / "workspaces", default_ttl_seconds=1)


def test_create_and_get_workspace(temp_workspace_mgr: WorkspaceManager):
    task_id = "test_task_123"
    ws_path = temp_workspace_mgr.create_workspace(task_id)
    assert ws_path.exists()
    assert ws_path.is_dir()
    assert temp_workspace_mgr.get_workspace_path(task_id) == ws_path


def test_write_and_read_file(temp_workspace_mgr: WorkspaceManager):
    task_id = "task_io"
    temp_workspace_mgr.create_workspace(task_id)

    file_path = temp_workspace_mgr.write_file(task_id, "script.py", "print('hello world')")
    assert file_path.exists()

    content = temp_workspace_mgr.read_file(task_id, "script.py")
    assert content == "print('hello world')"


def test_path_traversal_prevention(temp_workspace_mgr: WorkspaceManager):
    task_id = "task_security"
    temp_workspace_mgr.create_workspace(task_id)

    # Attempting to escape the workspace directory via relative navigation
    with pytest.raises(PermissionError):
        temp_workspace_mgr.write_file(task_id, "../escape.txt", "exploit")

    with pytest.raises(PermissionError):
        temp_workspace_mgr.read_file(task_id, "../escape.txt")


def test_list_files(temp_workspace_mgr: WorkspaceManager):
    task_id = "task_list"
    temp_workspace_mgr.create_workspace(task_id)
    temp_workspace_mgr.write_file(task_id, "a.py", "content a")
    temp_workspace_mgr.write_file(task_id, "sub/b.py", "content b")

    files = temp_workspace_mgr.list_files(task_id)
    file_names = {f.filename for f in files}
    assert "a.py" in file_names
    assert os.path.join("sub", "b.py") in file_names or "sub/b.py" in file_names


def test_garbage_collection(temp_workspace_mgr: WorkspaceManager):
    task_id = "task_to_purge"
    ws = temp_workspace_mgr.create_workspace(task_id)
    assert ws.exists()

    # Sleep briefly to exceed TTL of 1 second
    time.sleep(1.1)

    purged = temp_workspace_mgr.cleanup_expired_workspaces(custom_ttl_seconds=1)
    assert purged >= 1
    assert not ws.exists()