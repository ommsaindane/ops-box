from ollama import Client

from schemas.tool_calls import ToolCalls

from config import MODEL_NAME, OLLAMA_HOST


class LLMClient:
    def __init__(
        self,
        model: str = MODEL_NAME,
        host: str = OLLAMA_HOST,
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
