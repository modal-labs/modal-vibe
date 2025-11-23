# Modal Vibe: A scalable AI coding platform

<center>
<video controls playsinline class="w-full aspect-[16/9]" poster="https://modal-cdn.com/blog/videos/modal-vibe-scaleup-poster.png">
<source src="https://modal-cdn.com/blog/videos/modal-vibe-scaleup.mp4" type="video/mp4">
<track kind="captions" />
</video>
</center>

The [Modal Vibe repo](https://github.com/modal-labs/modal-vibe) demonstrates how you can build
a scalable AI coding platform on Modal.

Users of the application can prompt an LLM to create sandboxed applications that service React through a UI.

Each application lives on a [Modal Sandbox](https://modal.com/docs/guide/sandbox)
and contains a webserver accessible through
[Modal Tunnels](https://modal.com/docs/guide/tunnels).

For a high-level overview of Modal Vibe, including performance numbers and why they matter, see
[the accompanying blog post](https://modal.com/blog/modal-vibe).
For details on the implementation, read on.

## How it's structured

![Architecture diagram for Modal Vibe](https://modal-cdn.com/modal-vibe/architecture.png)

- `main.py` is the entrypoint that runs the FastAPI controller that serves the web app and manages the sandbox apps.
- `core` contains the logic for `SandboxApp` model and LLM logic.
- `sandbox` contains a small HTTP server that gets put inside every Sandbox that's created, as well as some sandbox lifecycle management code.
- `web` contains the Modal Vibe website that users see and interact with, as well as the api server that manages Sandboxes.

## How to run

First, set up the local environment:

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.dev.txt
```

### Deploy

To deploy Modal Vibe to Modal, follow these steps:

1. **Set up environment variables:**

   Copy `.env.example` to `.env`.

   Edit your `.env` file and provide values for:
   - `ANTHROPIC_API_KEY`
   - `ADMIN_SECRET`

2. **Configure Modal Secrets:**

   - Create a [Modal Secret](https://modal.com/docs/guide/secrets) named `anthropic-secret` containing your `ANTHROPIC_API_KEY`.
   - Create a Modal Secret named `admin-secret` containing your `ADMIN_SECRET`.

   These steps ensure your app has secure access to environment credentials on Modal.

3. **Deploy the application:**

    ```bash
   modal deploy -m main
   ```

   **Note:** If your account is not on Modal's Team or Enterprise plan, you won't be able to use custom domain from the FastAPI function in `main.py`:

   ```python
   @app.function(
       image=image,
       secrets=[modal.Secret.from_name("anthropic-secret")],
       min_containers=1
   )
   @modal.concurrent(max_inputs=100)
   @modal.asgi_app(custom_domains=["vibes.modal.chat"])  # REMOVE CUSTOM DOMAINS ARGUMENT IF NO ACCESS
   def fastapi_app():
       ...
   ```

### Local Development

Run a load test:

```bash
modal run main.py::create_app_loadtest_function --num-apps 10
```

Delete a sandbox:

```bash
modal run main.py::delete_sandbox_admin_function --app-id <APP_ID>
```

Run an example sandbox HTTP server:

```bash
python -m sandbox.server
```
