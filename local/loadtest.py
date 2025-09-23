
from core.llm import get_llm_client
import modal
from dotenv import load_dotenv
from modal import Dict

load_dotenv()
llm_client = get_llm_client()

# Persist Sandbox application metadata in a Modal Dict so it can be shared across containers and restarts.
# This will create the dict on first run if it does not already exist.
apps_dict = Dict.from_name("sandbox-apps", create_if_missing=True)

core_image = (
    modal.Image.debian_slim()
    .env({"PYTHONDONTWRITEBYTECODE": "1"})  # Prevent Python from creating .pyc files
    .pip_install(
        "fastapi[standard]",
        "jinja2",
        "python-multipart",
        "httpx",
        "python-dotenv",
        "anthropic",
        "tqdm",
    )
    .add_local_dir("core", "/root/core")
)
image = (
    core_image
    .add_local_dir("web", "/root/web")
    .add_local_dir("sandbox", "/root/sandbox")
    .add_local_dir("core", "/root/core")
)


app = modal.App(name="modal-vibe-loadtest", image=image)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=3600,
)
@modal.concurrent(max_inputs=1000)
async def make_create_app_request(prompt: str):
    import httpx

    API_URL = "https://modal-labs-joy-dev--modal-vibe-fastapi-app.modal.run"
    num_retries = 5
    for i in range(num_retries):
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(f"{API_URL}/api/create", json={"prompt": prompt})
                response.raise_for_status()
                result = response.json()
                app_id = result["app_id"]
                return app_id
        except Exception as e:
            continue
    raise Exception(f"Failed to create app after {num_retries} retries")


@app.function(
    image=core_image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=3600,
)
@modal.concurrent(max_inputs=1000)
async def create_app_loadtest_function(num_apps: int = 100):
    import time
    import asyncio
    from typing import Any

    start_time = time.time()

    requested_num = num_apps
    app_buffers = 30
    effective_num = requested_num + app_buffers

    API_URL = "https://modal-labs-joy-dev--modal-vibe-fastapi-app.modal.run"
    if not API_URL:
        raise ValueError("API_URL environment variable is not set")

    with open("/root/core/prompts.txt", "r") as f:
        prompts = [p.strip() for p in f if p.strip()]
    prompts = prompts[:effective_num]

    semaphore = asyncio.Semaphore(120)

    async def create_app_with_limit(prompt: str, index: int) -> Any | None:
        print(f"Creating app with prompt: {prompt}")
        async with semaphore:
            delays = [0, 0.1, 0.5]  # seconds
            for attempt, delay in enumerate([0, *delays], start=1):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    return await asyncio.wait_for(
                        make_create_app_request.remote.aio(prompt),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    if attempt == len(delays) + 1:
                        print(f"[{index}] timeout on prompt")
                except Exception as e:
                    if attempt == len(delays) + 1:
                        print(f"[{index}] failed: {e!r}")
            return None

    tasks = [asyncio.create_task(create_app_with_limit(p, i)) for i, p in enumerate(prompts)]
    results = await asyncio.gather(*tasks)  # no return_exceptions

    successful_apps = [r for r in results if r is not None]
    app_count = len(successful_apps)

    time_taken = time.time() - start_time
    print(f"Created {app_count} apps in {time_taken} seconds")
    return {
        "requested": requested_num,
        "effective": len(prompts),
        "created": app_count,
        "duration_sec": time_taken,
    }
