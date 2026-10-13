"""
run_test.py

Submits an autonomous task to ops-box, streams execution logs in real-time,
and prints the final summary.
"""

import asyncio
import json
import httpx


async def run():
    base_url = "http://localhost:8000"
    prompt = (
        "Write a Python script named fibonacci.py that calculates the first 10 Fibonacci numbers "
        "and saves them as a JSON list in fib.json. Then run the script inside the sandbox, "
        "verify that fib.json exists and contains the correct list, and finish the task."
    )

    print("=" * 70)
    print("Submitting prompt to Ops-Box:")
    print(f"'{prompt}'")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Submit the task
        res = await client.post(f"{base_url}/api/v1/tasks", json={"instruction": prompt})
        if res.status_code != 202:
            print(f"Failed to submit task: {res.status_code} - {res.text}")
            return

        task_id = res.json()["task_id"]
        print(f"\n[+] Task Accepted! ID: {task_id}")
        print("[*] Connecting to real-time event stream...\n")

        # 2. Connect to the SSE stream
        async with client.stream("GET", f"{base_url}/api/v1/tasks/{task_id}/events") as response:
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                raw_json = line[6:]
                event = json.loads(raw_json)

                if event.get("event") == "step":
                    step_num = event["step_number"]
                    tool_name = event["tool_name"]
                    thought = event.get("thought") or "(No chain-of-thought emitted)"
                    duration = event["duration_seconds"]

                    print(f"--- [STEP {step_num}] ({duration}s) ---")
                    print(f"THOUGHT: {thought.strip()}")
                    print(f"TOOL   : {tool_name}")
                    print(f"INPUT  : {json.dumps(event['tool_input'], indent=2)}")
                    print(f"OUTPUT :\n{event['tool_output']}")
                    print("-" * 70 + "\n")

                elif event.get("event") == "done":
                    print("=" * 70)
                    print(f"[COMPLETED] Status: {event['status']}")
                    print(f"Final Summary:\n{event['summary']}")
                    print("=" * 70)
                    break


if __name__ == "__main__":
    asyncio.run(run())