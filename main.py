"""Main entrypoint that runs the FastAPI controller that serves the web app and manages the sandbox apps."""

from datetime import datetime
import json
import os
from core.llm import get_llm_client
from core.models import SandboxApp
import modal
import uuid
from dotenv import load_dotenv
import asyncio

load_dotenv()
llm_client = get_llm_client()

# Persist Sandbox application metadata in a Modal Volume so it can be shared across containers and restarts.
# This will create the volume on first run if it does not already exist.
apps_volume = modal.Volume.from_name("sandbox-apps-volume", create_if_missing=True)
DATA_FILE = "/data/apps.json"

image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "jinja2",
        "python-multipart",
        "httpx",
        "python-dotenv",
        "anthropic",
    )
    .add_local_dir("web", "/root/web")
    .add_local_dir("sandbox", "/root/sandbox")
    .add_local_dir("core", "/root/core")
)
app = modal.App(name="modal-vibe", image=image,)


def load_apps_from_volume() -> dict[str, SandboxApp]:
    """Load apps from volume and return them as a dict"""
    try:
        apps_volume.reload()
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                content = f.read()
                print(f"Raw JSON content length: {len(content)}")
                if not content.strip():
                    print("JSON file is empty, returning empty dict")
                    return {}
                app_datas = json.loads(content)
            return {app_id: SandboxApp.from_dict(app_data, app, image, llm_client) for app_id, app_data in app_datas.items()}
        else:
            print(f"Data file {DATA_FILE} does not exist, creating it")
            with open(DATA_FILE, "w") as f:
                json.dump({}, f, indent=2)
        return {}
    except json.JSONDecodeError as e:
        print(f"JSON decode error loading apps from volume: {e}")
        print(f"Error at line {e.lineno}, column {e.colno}: {e.msg}")
        return {}
    except Exception as e:
        print(f"Error loading apps from volume: {e}")
        return {}

def save_app_to_volume(app_id: str, app_data: dict) -> None:
    """Save apps back to volume"""
    apps_volume.reload()
    try:
        existing_data = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                content = f.read()
                if content.strip():
                    existing_data = json.loads(content)
        
        existing_data[app_id] = app_data
        with open(DATA_FILE, "w") as f:
            json.dump(existing_data, f, indent=2)  # Add indentation for readability
        apps_volume.commit()
        print(f"Saved app {app_id} to volume")
    except json.JSONDecodeError as e:
        print(f"JSON decode error when saving apps to volume: {e}")
        print(f"Error at line {e.lineno}, column {e.colno}: {e.msg}")
    except Exception as e:
        print(f"Error saving apps to volume: {e}")


# @app.function(
#     image=image,
#     secrets=[modal.Secret.from_name("anthropic-secret")],
#     volumes={"/data": apps_volume},
# )
# @modal.concurrent(max_inputs=50)
# async def create_app_loadtest_function(num_apps: int = 10):
#     """Standalone Modal function to create multiple test apps and persist them to volume."""
#     from core.models import SandboxApp
#     from core.llm import get_llm_client, generate_response
    
#     llm_client = get_llm_client()
    
#     def _generate_fake_prompt():
#         """Use LLM to generate a fake prompt for the app"""
#         response = generate_response(
#             llm_client,
#             "Generate a prompt for an idea on an app to build. The prompt should be a single sentence that describes the app. The prompt should be in the format of 'Create a {app_type} app that {app_description}.'",
#         )
#         return response

#     async def create_single_app(i: int) -> SandboxApp:
#         app_id = str(uuid.uuid4())
#         prompt = _generate_fake_prompt()
#         print(f"Creating app {i+1}/{num_apps}: {app_id} with prompt: {prompt}")
        
#         sandbox_app = SandboxApp(app_id, app, image, llm_client)
#         await sandbox_app.edit(prompt, is_init=True)
#         print(f"Created app {app_id}")
#         return sandbox_app

#     print(f"Starting concurrent creation of {num_apps} apps...")
#     tasks = [create_single_app(i) for i in range(num_apps)]
#     created_apps = await asyncio.gather(*tasks, return_exceptions=True)
    
#     successful_apps = [
#         sandbox_app for sandbox_app in created_apps 
#         if isinstance(sandbox_app, SandboxApp)
#     ]
    
#     failed_count = len(created_apps) - len(successful_apps)
#     if failed_count > 0:
#         print(f"Warning: {failed_count} apps failed to create")
    
#     if successful_apps:
#         save_apps_to_volume(successful_apps)
    
#     return {
#         "created_apps": len(successful_apps), 
#         "failed_apps": failed_count,
#         "app_ids": [app.id for app in successful_apps]
#     }

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    volumes={"/data": apps_volume},
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import httpx


    web_app = FastAPI()
    web_app.mount("/static", StaticFiles(directory="/root/web/static"), name="static")

    templates = Jinja2Templates(directory="/root/web/templates")

    def _get_app_or_raise(app_id: str) -> SandboxApp:
        apps = load_apps_from_volume()
        if app_id not in apps:
            raise HTTPException(status_code=404, detail="App not found")
        return apps[app_id]

    async def _cleanup_dead_sandboxes():
        """Check all sandboxes and remove dead ones from the apps dictionary"""
        dead_apps = []
        apps = load_apps_from_volume()
        for app_id, sandbox_app in apps.items():
            try:
                if not await sandbox_app.is_alive():
                    print(f"🧹 Removing dead sandbox: {app_id}")
                    dead_apps.append(app_id)
            except Exception as e:
                print(f"Error checking sandbox {app_id}: {str(e)}")
                dead_apps.append(app_id)

        if dead_apps:
            existing_data = {}
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r") as f:
                    content = f.read()
                    if content.strip():
                        existing_data = json.loads(content)
            
            for app_id in dead_apps:
                if app_id in existing_data:
                    del existing_data[app_id]
                    print(f"✅ Removed dead sandbox from volume: {app_id}")
            
            with open(DATA_FILE, "w") as f:
                json.dump(existing_data, f, indent=2)
            apps_volume.commit()

    async def background_cleanup_task(interval: float = 60.0):
        while True:
            await asyncio.sleep(interval)
            try:
                load_apps_from_volume()
                await _cleanup_dead_sandboxes()
            except Exception as e:
                print(f"Error in background cleanup: {e}")

    @web_app.on_event("startup")
    async def start_background_cleanup():
        asyncio.create_task(background_cleanup_task())

    @web_app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return templates.TemplateResponse(
            name="pages/404.html", context={"request": request}, status_code=404
        )

    @web_app.exception_handler(503)
    async def service_unavailable_handler(request: Request, exc):
        return templates.TemplateResponse(
            name="pages/503.html", context={"request": request}, status_code=503
        )

    @web_app.get("/")
    async def home(request: Request):
        apps = load_apps_from_volume()
        app_list = list(apps.keys())
        return templates.TemplateResponse(
            name="pages/home.html", context={"request": request, "apps": app_list}
        )

    @web_app.get("/app/{app_id}")
    async def app_page(request: Request, app_id: str):
        app = _get_app_or_raise(app_id)
        return templates.TemplateResponse(
            name="pages/app.html",
            context={
                "request": request,
                "app_id": app_id,
                "relay_url": app.sandbox_tunnel_url,
                "message_history": app.message_history,
            },
        )

    @web_app.post("/api/create")
    async def create_app(request: Request):
        data = await request.json()
        time = datetime.now().strftime("%Y%m%d%H%M%S")
        app_id = str(uuid.uuid4()) + f"_{time}"
        apps = load_apps_from_volume()
        apps[app_id] = SandboxApp(app_id, app, image, llm_client)
        await apps[app_id].edit(data["prompt"], is_init=True)
        save_app_to_volume(app_id, apps[app_id].to_dict())
        return JSONResponse({"app_id": app_id})

    @web_app.post("/api/app/{app_id}/write")
    async def write_app(app_id: str, request: Request):
        data = await request.json()
        is_init = data.get("is_init", False)
        app = _get_app_or_raise(app_id)
        try:
            response = await app.edit(data["text"], is_init=is_init)
            return JSONResponse(response.json(), status_code=response.status_code)
        except Exception as e:
            print(f"Error writing to relay with data: {data}: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.get("/api/app/{app_id}/ping")
    async def ping_app(app_id: str):
        app = _get_app_or_raise(app_id)
        try:
            await app.wait_for_ready()
        except TimeoutError as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=503)

        heartbeat_url = f"{app.sandbox_tunnel_url}/heartbeat"
        try:
            print(f"Pinging relay at: {heartbeat_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(heartbeat_url, timeout=10.0)
                print(f"Ping response status: {response.status_code}")
                return JSONResponse(response.json(), status_code=response.status_code)
        except Exception as e:
            print(f"Error pinging relay: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.get("/api/app/{app_id}/display", response_class=HTMLResponse)
    async def display_app(app_id: str):
        app = _get_app_or_raise(app_id)

        try:
            await app.wait_for_ready()
        except TimeoutError:
            raise HTTPException(status_code=503, detail="Service Unavailable")

        display_url = app.sandbox_user_tunnel_url
        print(f"Embedding iframe from: {display_url}")

        iframe_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>App Preview</title>
            <style>
                body, html {{
                    margin: 0;
                    padding: 0;
                    height: 100%;
                }}
                iframe {{
                    width: 100%;
                    height: 100%;
                    border: none;
                }}
            </style>
        </head>
        <body>
            <iframe src="{display_url}" allow="clipboard-write"></iframe>
        </body>
        </html>
        """
        return HTMLResponse(content=iframe_html)

    return web_app


f = modal.Function.from_name("modal-vibe", "fastapi_app")
f.update_autoscaler(min_containers=1)