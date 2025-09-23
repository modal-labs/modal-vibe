"""LLM logic for the sandbox app."""

import os
from dotenv import load_dotenv

from anthropic import AsyncAnthropic

load_dotenv()

def get_llm_client():
    return AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def generate_response(client, prompt, model="claude-sonnet-4-20250514", max_tokens=8192, temperature=0.5):
    message = await client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return message.content[0].text