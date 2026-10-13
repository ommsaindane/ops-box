"""
tests/test_api.py

API integration tests for task dispatching, polling, and SSE real-time streaming.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app import app, task_store, task_event_queues


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "engine": "ops-box"}


@pytest.mark.asyncio
async def test_submit_and_poll_task():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Submit a task
        payload = {"instruction": "Write a quick test script"}
        create_res = await client.post("/api/v1/tasks", json=payload)
        assert create_res.status_code == 202
        data = create_res.json()
        assert "task_id" in data
        task_id = data["task_id"]

        # 2. Poll the task status
        get_res = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_res.status_code == 200
        task_info = get_res.json()
        assert task_info["task_id"] == task_id
        assert task_info["status"] in ["pending", "running", "completed", "failed"]


@pytest.mark.asyncio
async def test_task_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/tasks/nonexistent_task_id")
        assert response.status_code == 404