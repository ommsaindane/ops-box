from pathlib import Path
import shutil


class WorkspaceManager:
    def __init__(self, root: Path | str = "workspace"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, name: str) -> Path:
        workspace = self.root / name
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def write_file(self, workspace: Path, relative_path: str, content: str) -> Path:
        file_path = workspace / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")
        return file_path

    def read_file(self, workspace: Path, relative_path: str) -> str:
        file_path = workspace / relative_path
        return file_path.read_text(encoding="utf-8")

    def list_files(self, workspace: Path) -> list[str]:
        return sorted(
            str(path.relative_to(workspace))
            for path in workspace.rglob("*")
            if path.is_file()
        )

    def delete_workspace(self, workspace: Path) -> None:
        if workspace.exists():
            shutil.rmtree(workspace)
