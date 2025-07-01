def generate_response(client, prompt, model="claude-opus-4-20250514"):
    message = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    return message.content[0].text