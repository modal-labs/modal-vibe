"""LLM logic for the sandbox app."""

import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

def get_llm_client():
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_response(client, prompt, model="claude-opus-4-20250514", max_tokens=8192):
    message = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return message.content[0].text