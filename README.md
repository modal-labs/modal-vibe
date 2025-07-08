# Modal Vibe
Example application that lets users programmatically create Sandboxed applications that service HTML through a UI.

Each application lives on a Modal Sandbox and contains a webserver accessible through Modal Tunnels.


## Structure
- `main.py` is the entrypoint that runs the FastAPI controller that serves the web app and manages the sandbox apps.
- `core` contains the logic for `SandboxApp` model and LLM logic.
- `sandbox` contains a small HTTP server that gets put inside every Sandbox that's created, as well as some sandbox lifecycle management code.
- `web` contains the Modal Vibe website that users see and interact with, as well as the api server that manages Sandboxes.


## How to run
Set-up the local environment.

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.dev.txt
```

### Deploy
To deploy to Modal, copy the `.env.example` and add your `ANTHROPIC_API_KEY`. Also, create a Modal Secret called `anthropic-secret` so our applications can access it.

Then, run the following code block:

```bash
modal deploy -m main
```

### Local Development

Run an example sandbox HTTP server:
```bash
python -m sandbox.server
```

Run the webserver locally for fast development:
```bash
python -m local
```

