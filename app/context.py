"""Who is talking. Set by the API from the request body, never by the model."""
from dataclasses import dataclass
from langchain_anthropic import ChatAnthropic

MODEL_NAME = "claude-haiku-5-5"

def make_model(max_tokens=700):
    return ChatAnthropic(model=MODEL_NAME, max_tokens=max_tokens, timeout=30, max_retries=2)

@dataclass
class AdContext:
    user_id: str = "demo"
