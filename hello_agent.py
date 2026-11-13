"""Quick check that the API key works: ask the AI model one question."""

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from app.config import get_settings

settings = get_settings()

model = AnthropicModel(
    settings.ai_model,
    provider=AnthropicProvider(api_key=settings.anthropic_api_key),
)

agent = Agent(
    model,
    instructions="You are a friendly customer support assistant. Keep answers short.",
)

result = agent.run_sync("Say hello and tell me in one sentence what you can help with.")

print(result.output)
print()
print("Tokens used:", result.usage.total_tokens)
