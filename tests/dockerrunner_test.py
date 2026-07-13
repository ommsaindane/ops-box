from workspace.manager import WorkspaceManager
from sandbox.docker_runner import DockerRunner


def test_run_hello_world(tmp_path):
    manager = WorkspaceManager(root=tmp_path)
    workspace = manager.create_workspace("demo")

    manager.write_file(
        workspace,
        "main.py",
        'print("Hello, OpsBox!")',
    )

    runner = DockerRunner()

    result = runner.run(
        workspace,
        ["python", "main.py"],
    )

    assert result.success
    assert result.exit_code == 0
    assert "Hello, OpsBox!" in result.stdout


def test_runtime_error(tmp_path):
    manager = WorkspaceManager(root=tmp_path)
    workspace = manager.create_workspace("demo")

    manager.write_file(
        workspace,
        "main.py",
        'raise RuntimeError("boom")',
    )

    runner = DockerRunner()

    result = runner.run(
        workspace,
        ["python", "main.py"],
    )

    assert not result.success
    assert result.exit_code != 0
    assert "boom" in result.stderr


def test_syntax_error(tmp_path):
    manager = WorkspaceManager(root=tmp_path)
    workspace = manager.create_workspace("demo")

    manager.write_file(
        workspace,
        "main.py",
        "print(",
    )

    runner = DockerRunner()

    result = runner.run(
        workspace,
        ["python", "main.py"],
    )

    assert not result.success
    assert result.exit_code != 0
    assert "SyntaxError" in result.stderr


def test_missing_file(tmp_path):
    manager = WorkspaceManager(root=tmp_path)
    workspace = manager.create_workspace("demo")

    runner = DockerRunner()

    result = runner.run(
        workspace,
        ["python", "main.py"],
    )

    assert not result.success
    assert result.exit_code != 0
