from fastapi import FastAPI

from api.dependencies import get_orchestrator
from schemas.request import TaskRequest
from schemas.response import TaskResponse

app = FastAPI(title="Ops_Box", version="0.1.0")

orchestrator = get_orchestrator()


@app.post(
    "/execute",
    response_model=TaskResponse,
)
def execute(request: TaskRequest) -> TaskResponse:
    return orchestrator.run(request)


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }
