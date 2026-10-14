# Ops-Box

An autonomous development sandbox that generates Python projects with an LLM, validates them through structured tool calls, executes them inside an isolated Docker container, and automatically retries using execution feedback.

---

## Architecture

<img width="521" height="421" alt="Image" src="https://github.com/user-attachments/assets/42310077-0cdf-412c-b40a-a8c0a0a9c74f" />

---

## Example Output

<img width="960" and height="540" alt="12fps" src="https://github.com/user-attachments/assets/9c747f04-8122-4317-9aef-0f052d2f7945"/>

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Design Decisions](#design-decisions)
- [Testing](#testing)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [Tech Stack](#tech-stack)
- [Motivation](#motivation)

---

# Features

- Structured LLM outputs using tool-calling schemas
- FastAPI asynchronous REST API with background task execution
- Real-time step and execution streaming via Server-Sent Events (SSE)
- Minimal Streamlit web interface for task visualization
- Secure Docker sandbox execution
- Path traversal defense and automatic TTL garbage collection for workspaces
- Automatic retry and self-healing using runtime execution feedback
- Universal LLM provider support (local Ollama or free cloud inference via Groq)
- Docker resource and security constraints
    - Memory limit and disabled swap
    - CPU quota
    - Network disabled by default
    - Dropped kernel capabilities (`ALL`)
    - Non-root user execution (`1000:1000`)
    - Process limits (`pids_limit`)
    - No new privileges flag
- Deterministic circuit breakers and step limits
- Pytest test suite with async mocking

---

# Project Structure

```text
ops-box/
│
├── api/
├── llm/
├── orchestrator/
├── sandbox/
├── schemas/
├── workspace/
├── tests/
│
├── app.py
├── ui.py
├── config.py
└── README.md

```

---

# Getting Started

## Prerequisites

* Python 3.11+
* Docker Desktop
* Ollama or a Groq API Key
* Git

### Using Local Ollama

Install and start Ollama.

Pull the model used by the project:

```bash
ollama pull qwen2.5-coder:7b

```

### Using Groq Cloud

Export your Groq API key:

Windows (PowerShell)

```powershell
$env:GROQ_API_KEY="gsk_your_key_here"

```

Linux/macOS

```bash
export GROQ_API_KEY="gsk_your_key_here"

```

---

## Installation

Clone the repository.

```bash
git clone [https://github.com/](https://github.com/)<your-username>/ops-box.git

```


Create a virtual environment and activate it.

```bash
python -m venv .venv

```


Install dependencies.

```bash
pip install .

```

Ensure Docker Desktop is running.

---

# Usage

Start the API.

```bash
uvicorn app:app --reload

```

Start the Streamlit dashboard in a separate terminal.

```bash
streamlit run ui.py

```

Open the API documentation.

```
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

```

Or open the web dashboard.

```
[http://127.0.0.1:8501](http://127.0.0.1:8501)

```

Example request

```json
POST /api/v1/tasks
{
    "instruction": "Write a Python script that calculates the first 10 Fibonacci numbers and saves them to fib.json. Verify the file and finish the task."
}

```

Example response (`202 Accepted`)

```json
{
    "task_id": "d97773ef3cd94b848e869e171caee0e9",
    "status": "pending",
    "summary": null,
    "total_duration_seconds": null,
    "error": null,
    "step_count": 0
}

```

Stream execution events in real time.

```bash
GET /api/v1/tasks/{task_id}/events

```

---

# Design Decisions

## Structured Tool Calls

The LLM never writes directly to the host filesystem.

Instead, every action is validated as a structured function call (`write_file`, `read_file`, `list_files`, `run_command`, `finish_task`) before execution.

---

## Docker Sandbox

All generated code executes inside an isolated Docker container rather than on the host machine.

Security measures include:

* Disabled networking (`network_mode="none"`)
* Hard memory limits and disabled swap
* CPU quotas
* PID limits to prevent fork bombs
* Dropped kernel capabilities (`ALL`)
* Non-root execution
* Automatic container cleanup on timeout or completion

---

## Asynchronous Execution Lifecycle

Long-running agent workflows are detached from standard request lifecycles.

Tasks are accepted immediately (`202 Accepted`) and handled by background workers, while incremental thought traces and command outputs are streamed to clients via Server-Sent Events (SSE).

---

## Execution Feedback Loop

If execution fails, the runtime output and exit codes are sent back to the model.

```
Generate Code
      │
      ▼
Execute
      │
      ▼
Success?
  │        │
 Yes      No
  │        │
 Return  Retry

```

This allows the agent to automatically repair simple runtime errors and verify its own work.

---

# Testing

Run the full test suite.

```bash
pytest -v

```

Individual test files can also be executed.

```bash
pytest tests/test_workspace.py
pytest tests/test_orchestrator.py
pytest tests/test_api.py

```

---

# Limitations

Current verification is designed for non-interactive Python programs.

Interactive CLI applications, GUI applications, and long-running services are outside the scope of the current implementation.

---

# Roadmap

* Support for additional programming languages
* Project artifact download endpoint
* Container image pre-warming and pooling
* Multi-container network topologies for distributed services
* Token budget calculation and tracking per session
* Configurable base images per task

---

# Tech Stack

| Component | Technology |
| --- | --- |
| API | FastAPI |
| Dashboard | Streamlit |
| Streaming | Server-Sent Events (SSE) |
| LLM | Ollama / Groq |
| Validation | Pydantic |
| Sandbox | Docker SDK |
| Testing | Pytest / pytest-asyncio |
| Language | Python 3.11 |

---

# Motivation

The objective of Ops-Box is not to replace existing coding assistants, but to implement the execution infrastructure required by autonomous development agents.

The project demonstrates structured LLM interaction, secure code execution, execution-driven self-correction, and clean backend architecture using production-oriented engineering practices.

```