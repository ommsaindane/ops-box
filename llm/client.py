from ollama import Client

from schemas.tool_calls import ToolCalls


class LLMClient:
    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        host: str = "http://localhost:11434",
        client: Client | None = None,
    ):
        self.model = model
        self.client = client or Client(host=host)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ToolCalls:
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            format=ToolCalls.model_json_schema(),
        )

        return ToolCalls.model_validate_json(response.message.content)
