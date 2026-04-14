"""
DeepSeek API client — shared across all agents.
DeepSeek is OpenAI-compatible, so we use the openai SDK with a custom base_url.
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DEEPSEEK_KEY")
        if not api_key:
            raise EnvironmentError(
                "DEEPSEEK_KEY not found in environment. "
                "Make sure your .env file contains DEEPSEEK_KEY=sk-..."
            )
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
    return _client
