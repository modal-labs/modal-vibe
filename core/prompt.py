"""Prompting texts used to build the sandbox app."""

from core.llm import generate_response
import anthropic
from core.models import Message

async def _generate_init_edit(client: anthropic.Anthropic, message: str) -> str:
    prompt = f"""
    You are given the following prompt and your job is to generate a React component that is a good example of the prompt.
    You should use Tailwind CSS for styling. Please make sure to export the component as default.
    This is incredibly important for my job, please be careful and don't make any mistakes.
    Make sure you import all necessary dependencies.

    Prompt: {message}

    RESPONSE FORMAT:
    import React from 'react';
    export default function LLMComponent() {{
        return (
            <div className="bg-red-500">
                <h1>LLM Component</h1>
            </div>
        )
    }}

    DO NOT include any other text in your response. Only the React component. MAKE SURE TO NAME THE COMPONENT "LLMComponent". DO NOT WRAP THE CODE IN A CODE BLOCK.
    """
    response = await generate_response(client, prompt)
    return response

async def _explain_init_edit(
    message: str, html: str, client: anthropic.Anthropic
) -> str:
    prompt = f"""
    You were given the following prompt and you generated the following React component:

    Prompt: {message}

    You generated the following React component: {html}

    Give a response that summarizes the changes you made. An example of a good response is:
    - "That sounds great! I made a donut chart for you. Let me know if you want anything else!"

    Be as concise as possible, but always be friendly!
    """

    explanation = await generate_response(
        client,
        prompt,
        model="claude-3-5-haiku-20241022",
        max_tokens=64,
    )
    return explanation

async def generate_and_explain_init_edit(client: anthropic.Anthropic, message: str) -> tuple[str, str]:
    edit = await _generate_init_edit(client, message)
    explanation = await _explain_init_edit(message, edit, client)
    return edit, explanation

async def _generate_followup_edit(client: anthropic.Anthropic, message: str, original_html: str, message_history: list[Message]) -> str:
    message_history = '\n'.join([f"{msg.type}: {msg.content}" for msg in message_history])

    prompt = f"""
    You should use Tailwind CSS for styling. Please make sure to export the component as default.
    This is incredibly important for my job, please be careful and don't make any mistakes.
    Make sure you import all necessary dependencies.

    The existing React component you are working with is this.
    {original_html}

    You are asked to make the following changes to the React component:
    {message}

    Here is the history of messages between the user and the assistant:
    {message_history}

    You are asked to generate a React component that is a good example of the prompt.
    Prompt: {message}

    RESPONSE FORMAT:
    import React from 'react';
    export default function LLMComponent() {{
        return (
            <div className="bg-red-500">
                <h1>LLM Component</h1>
            </div>
        )
    }}

    DO NOT include any other text in your response. Only the React component. MAKE SURE TO NAME THE COMPONENT "LLMComponent". DO NOT WRAP THE CODE IN A CODE BLOCK.
    """
    return await generate_response(client, prompt)


async def _explain_followup_edit(client: anthropic.Anthropic, message: str, original_html: str, new_html: str) -> str:
    prompt = f"""
    You generated the following React component edit to the prompt:

    Prompt: {message}

    Original React component: {original_html}
    Generated React component: {new_html}

    Give a response that summarizes the changes you made. An example of a good response is:
    - "Sounds good! I've made the changes you requested. Yay :D"
    - "I colored the background red and added a new button. Let me know if you want anything else!"
    - "I updated the font to a more modern one and added a new section. Cheers!!"

    Be as concise as possible, but always be friendly!
    """
    
    explanation = await generate_response(
        client,
        prompt,
        model="claude-3-5-haiku-20241022",
        max_tokens=64,
    )
    return explanation
    