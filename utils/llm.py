def generate_response(client, prompt, model="claude-opus-4-20250514", max_tokens=8192):
    message = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return message.content[0].text