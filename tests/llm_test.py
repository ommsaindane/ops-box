import pytest
from ollama import ResponseError

from llm.client import LLMClient


@pytest.fixture
def client():
    return LLMClient(
        model="qwen2.5-coder:7b",
    )


def test_generate_returns_non_empty_string(client):
    response = client.generate("say only the word 'hello'.")

    assert isinstance(response, str)
    assert len(response.strip()) > 0


def test_generate_contains_expected_word(client):
    response = client.generate("Respind with exactly one word: hello")

    assert "hello" in response.lower()


def test_invalid_model_raises():
    client = LLMClient(model="this-model-does-not-exist")

    with pytest.raises(ResponseError):
        client.generate("Hello")
