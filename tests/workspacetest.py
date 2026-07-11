from pathlib import Path

from workspace.manager import WorkspaceManager


def test_create_workspace(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    assert workspace.exists()
    assert workspace.is_dir()
    assert workspace.name == "demo"


def test_write_file(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    file_path = manager.write_file(
        workspace=workspace,
        relative_path="main.py",
        content='print("Hello")',
    )

    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == 'print("Hello")'


def test_write_nested_file(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    file_path = manager.write_file(
        workspace=workspace,
        relative_path="src/utils/helper.py",
        content="def helper():\n    pass",
    )

    assert file_path.exists()
    assert file_path.parent.exists()
    assert file_path.parent.name == "utils"


def test_read_file(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    manager.write_file(
        workspace=workspace,
        relative_path="README.md",
        content="# Ops Box",
    )

    content = manager.read_file(workspace, "README.md")

    assert content == "# Ops Box"


def test_list_files(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    manager.write_file(workspace, "main.py", "")
    manager.write_file(workspace, "requirements.txt", "")
    manager.write_file(workspace, "src/app.py", "")

    files = manager.list_files(workspace)

    assert files == [
        "main.py",
        "requirements.txt",
        "src/app.py",
    ]


def test_delete_workspace(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    manager.write_file(workspace, "main.py", "")

    assert workspace.exists()

    manager.delete_workspace(workspace)

    assert not workspace.exists()


def test_empty_workspace_lists_no_files(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    assert manager.list_files(workspace) == []


def test_overwrite_existing_file(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    manager.write_file(workspace, "main.py", "print(1)")
    manager.write_file(workspace, "main.py", "print(2)")

    assert manager.read_file(workspace, "main.py") == "print(2)"


def test_read_missing_file_raises(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = manager.create_workspace("demo")

    file = workspace / "missing.py"

    try:
        manager.read_file(workspace, "missing.py")
    except FileNotFoundError:
        pass
    else:
        assert False, f"Expected FileNotFoundError for {file}"


def test_delete_missing_workspace_does_not_raise(tmp_path):
    manager = WorkspaceManager(root=tmp_path)

    workspace = Path(tmp_path) / "does_not_exist"

    manager.delete_workspace(workspace)

    assert not workspace.exists()
