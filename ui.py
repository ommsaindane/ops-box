"""
ui.py

Minimal dashboard for Ops-Box execution engine.
Streams task thoughts, tool execution parameters, and sandbox stdout/stderr via SSE.
"""

import json
import httpx
import streamlit as st

st.set_page_config(
    page_title="Ops-Box Execution Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal CSS styling for execution blocks
st.markdown(
    """
    <style>
    .terminal-output {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 13px;
        line-height: 1.45;
        padding: 12px;
        border-radius: 4px;
        border: 1px solid #30363d;
        white-space: pre-wrap;
        word-break: break-all;
    }
    .agent-thought {
        background-color: #161b22;
        border-left: 3px solid #388bfd;
        padding: 8px 12px;
        border-radius: 2px;
        font-size: 14px;
        color: #8b949e;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Engine parameters
with st.sidebar:
    st.subheader("Configuration")
    api_url = st.text_input("Backend URL", value="http://localhost:8000")
    max_steps = st.slider("Max Execution Steps", min_value=1, max_value=25, value=10)

    st.markdown("---")
    st.caption("Isolation Policies")
    st.caption("- Network: None (Air-gapped)")
    st.caption("- Memory: 256MB Hard Limit")
    st.caption("- User: Non-root (UID 1000)")
    st.caption("- Capabilities: Dropped (ALL)")

st.title("Ops-Box")
st.caption("Autonomous sandboxed execution engine and verification runtime.")

default_prompt = (
    "Write a Python script named fibonacci.py that calculates the first 10 Fibonacci numbers "
    "and saves them as a JSON list in fib.json. Then run the script inside the sandbox, "
    "verify that fib.json exists and contains the correct list, and finish the task."
)

task_instruction = st.text_area(
    "Task Instruction",
    value=default_prompt,
    height=120,
)

execute_btn = st.button("Execute Task", type="primary")

if execute_btn:
    if not task_instruction.strip():
        st.error("Task instruction cannot be empty.")
        st.stop()

    status_area = st.empty()
    status_area.info("Dispatching task to execution queue...")

    # 1. Post task to FastAPI
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.post(
                f"{api_url.rstrip('/')}/api/v1/tasks",
                json={"instruction": task_instruction, "max_steps": max_steps},
            )
            if res.status_code != 202:
                status_area.error(f"Task rejected: {res.status_code} - {res.text}")
                st.stop()
            task_id = res.json()["task_id"]
    except Exception as exc:
        status_area.error(f"Failed to communicate with backend: {exc}")
        st.stop()

    status_area.info(f"Task active: {task_id}")

    steps_container = st.container()
    summary_area = st.empty()

    # 2. Listen to real-time execution stream
    event_url = f"{api_url.rstrip('/')}/api/v1/tasks/{task_id}/events"

    try:
        with httpx.stream("GET", event_url, timeout=180.0) as response:
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue

                event = json.loads(line[6:])

                if event.get("event") == "step":
                    step_num = event["step_number"]
                    tool_name = event["tool_name"]
                    thought = event.get("thought") or "Executing tool."
                    duration = event["duration_seconds"]
                    tool_input = event.get("tool_input", {})
                    tool_output = event.get("tool_output", "")
                    exit_code = event.get("exit_code")

                    with steps_container:
                        title = f"Step {step_num}: {tool_name} [{duration}s]"
                        with st.expander(title, expanded=True):
                            st.markdown(
                                f"<div class='agent-thought'>{thought}</div>",
                                unsafe_allow_html=True,
                            )

                            if tool_name == "write_file":
                                st.caption(f"Path: {tool_input.get('path')}")
                                st.code(tool_input.get("content", ""), language="python")
                            elif tool_name == "run_command":
                                st.caption(f"Command: {tool_input.get('command')}")
                            else:
                                st.json(tool_input)

                            if exit_code is not None:
                                st.caption(f"Exit Code: {exit_code}")

                            st.markdown(
                                f"<div class='terminal-output'>{tool_output}</div>",
                                unsafe_allow_html=True,
                            )

                elif event.get("event") == "done":
                    final_status = event.get("status")
                    final_summary = event.get("summary", "No summary returned.")

                    if final_status == "completed":
                        status_area.success(f"Status: {final_status}")
                        summary_area.markdown(f"**Execution Summary:**\n\n{final_summary}")
                    else:
                        status_area.error(f"Status: {final_status}")
                        summary_area.markdown(f"**Execution Summary:**\n\n{final_summary}")
                    break

    except Exception as exc:
        status_area.error(f"Stream connection dropped: {exc}")