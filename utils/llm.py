
def generate_response(client, prompt):
    message = client.messages.create(
        model="claude-opus-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    return message.content[0].text