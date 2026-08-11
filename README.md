# Ops-Box

An autonomous development sandbox that generates Python projects with an LLM, validates them through structured tool calls, executes them inside an isolated Docker container, and automatically retries using execution feedback.

---

## Architecture

<img width="1042" height="842" alt="Image" src="https://github.com/user-attachments/assets/42310077-0cdf-412c-b40a-a8c0a0a9c74f" />

---

## Example Output


<img width="1918" height="898" alt="Image" src="https://github.com/user-attachments/assets/e0123e26-6b6b-41f7-9685-1383d7f7fb3b" />
<img width="1918" height="936" alt="Image" src="https://github.com/user-attachments/assets/ca7f98e5-6fd5-4ac9-a2ab-5d26e057c2ed" />

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Design Decisions](#design-decisions)
- [Roadmap](#roadmap)
- [Tech Stack](#tech-stack)
- [Motivation](#motivation)

---

# Features

- Structured LLM outputs using Pydantic schemas
- FastAPI REST API
- Secure Docker sandbox execution
- Workspace isolation for generated projects
- Automatic retry using runtime feedback
- Docker resource constraints
    - Memory limit
    - CPU quota
    - Network disabled
- Typed request and response models
- Modular architecture with dependency injection
- Pytest test suite

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
├── config.py
└── README.md
```

---

# Getting Started

## Prerequisites

- Python 3.11+
- Docker Desktop
- Ollama
- Git

Install and start Ollama.

Pull the model used by the project.

```bash
ollama pull qwen2.5-coder:7b
```

---

## Installation

Clone the repository.

```bash
git clone https://github.com/<your-username>/ops-box.git
```

Enter the project.

```bash
cd ops-box
```

Create a virtual environment.

```bash
python -m venv .venv
```

Activate it.

Windows

```bash
.venv\Scripts\activate
```

Linux/macOS

```bash
source .venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Ensure Docker Desktop and Ollama are running.

---

# Usage

Start the API.

```bash
uvicorn app:app --reload
```

Open

```
http://127.0.0.1:8000/docs
```

Example request

```json
{
    "prompt": "Write a Python script that prints the first 20 Fibonacci numbers."
}
```

Example response

```json
{
    "success": true,
    "attempts": 1,
    "execution": {
        "success": true,
        "exit_code": 0,
        "stdout": "...",
        "stderr": "",
        "error": null
    }
}
```

---

# Design Decisions

## Structured Tool Calls

The LLM never writes directly to the filesystem.

Instead, every action is validated using Pydantic before execution.

---

## Docker Sandbox

All generated code executes inside an isolated Docker container rather than on the host machine.

Security measures include:

- Disabled networking
- Memory limits
- CPU quota
- Automatic container cleanup

---

## Execution Feedback Loop

If execution fails, the runtime output is sent back to the model.

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

This allows the agent to automatically repair simple runtime errors.

---

# Testing

Run the full test suite.

```bash
pytest -v
```

Individual test files can also be executed.

```bash
pytest tests/workspacetest.py
pytest tests/docker_test.py
pytest tests/orchestrator_test.py
```

---

# Limitations

Current verification is designed for non-interactive Python programs.

Interactive CLI applications, GUI applications, and long-running services are outside the scope of the current implementation.

---

# Roadmap

- Improved execution verification strategies
- Project download endpoint
- Rich execution logs
- Support for additional programming languages
- Container image caching
- Better retry prompting
- Configurable execution commands

---

# Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI |
| LLM | Ollama |
| Validation | Pydantic |
| Sandbox | Docker SDK |
| Testing | Pytest |
| Language | Python 3.11 |

---

# Motivation

The objective of Ops-Box is not to replace existing coding assistants, but to implement the execution infrastructure required by autonomous development agents.

The project demonstrates structured LLM interaction, secure code execution, execution-driven self-correction, and clean backend architecture using production-oriented engineering practices.
