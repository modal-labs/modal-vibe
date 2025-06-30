# Modal Vibe
Example application that lets users programmatically create Sandboxed applications that service HTML through a UI.

Each application lives on a Modal Sandbox and contains a webserver accessible through Modal Tunnels.


## Structure
- `web` contains the Modal Vibe website that users see and interact with, as well as the api server that manages Sandboxes.
- `sandbox` contains a small HTTP server that gets put inside every Sandbox that's created, as well as some sandbox lifecycle management code.

## How to run

Set-up the local environment.

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

### Deploy
To deploy to Modal, copy the `.env.example` and add your `ANTHROPIC_API_KEY`. Also, add the `ANTHROPIC_API_KEY` to `Secret` under the name `anthropic-secret` so our applications can access it.

Then, run the following code block:

```bash
MODAL_PROFILE=modal-labs modal deploy --env=joy-dev main.py
```

### Local Development

Run an example sandbox HTTP server:
```bash
MODAL_PROFILE=modal-labs python sandbox/server.py --env=joy-dev
```

Run the webserver locally for fast development:
```bash
python local.py
```

