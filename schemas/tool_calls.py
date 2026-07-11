from enum import Enum
from pydantic import BaseModel


class ToolName(str, Enum):
    WRITE_FILE = "write_file"
    READ_FILE = "read_file"
    LIST_FILES = "list_files"
    INSTALL_PACKAGE = "install_package"


class WriteFileArgs(BaseModel):
    path: str
    content: str


class ReadFileArgs(BaseModel):
    path: str


class ToolCall(BaseModel):
    tool: ToolName
    arguments: dict
