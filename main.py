"""Main entrypoint that runs the FastAPI controller that serves the web app and manages the sandbox apps."""

import os
from datetime import datetime

from core.llm import get_llm_client
from core.sandbox import AppDirectory, SandboxApp
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


app = modal.App(name="modal-vibe", image=image)

sandbox_image = (
    modal.Image.from_registry("node:22-slim", add_python="3.12")
    .env(
        {
            "PNPM_HOME": "/root/.local/share/pnpm",
            "PATH": "$PNPM_HOME:$PATH",
            "SHELL": "/bin/bash",
        }
    )
    .run_commands(
        "apt-get update && apt-get install -y curl netcat-openbsd procps net-tools"
    )
    .run_commands(
        "corepack enable && corepack prepare pnpm@latest --activate && pnpm setup && pnpm add -g vite"
    )
    .pip_install(
        "fastapi[standard]",
    )
    .pip_install(
        "httpx",
    )
    .add_local_dir("web/vite-app", "/root/vite-app", copy=True)
    .run_commands(
        "pnpm install --dir /root/vite-app --force"
    )
    .add_local_file("sandbox/startup.sh", "/root/startup.sh", copy=True)
    .run_commands("chmod +x /root/startup.sh")
    .add_local_dir("sandbox", "/root/sandbox")
    .add_local_file("sandbox/server.py", "/root/server.py")
)

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret")],
    timeout=3600,
)
async def create_sandbox_app(prompt: str) -> str:    
    print(f"Creating sandbox app with prompt: {prompt}")
    
    app_directory = AppDirectory(apps_dict, app, llm_client)
    print("Initialized app directory")
    sandbox_app = await SandboxApp.create(app, llm_client, prompt, image=sandbox_image)
    app_directory.set_app(sandbox_app)
    print(f"Created image {sandbox_image.object_id}")
    print(f"Created and saved sandbox app with ID: {sandbox_app.id}")
    
    return sandbox_app.id

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-secret"), modal.Secret.from_name("admin-secret")],
    min_containers=1
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app(custom_domains=["vibes.modal.chat"])
def fastapi_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from pydantic import BaseModel
    import httpx

    app_directory = AppDirectory(apps_dict, app, llm_client)
    app_directory.load()


    class CreateAppRequest(BaseModel):
        prompt: str
        
    class CreateAppResponse(BaseModel):
        app_id: str
    
    class WriteAppRequest(BaseModel):
        text: str
        
    class TerminateAppRequest(BaseModel):
        admin_secret: str
    
    class ToggleFeatureRequest(BaseModel):
        admin_secret: str

    class SnapshotAppRequest(BaseModel):
        admin_secret: str
        

    web_app = FastAPI(
        title="Modal Sandbox API",
        description="API for creating and managing sandbox applications",
        version="1.0.0"
    )
    web_app.mount("/static", StaticFiles(directory="/root/web/static"), name="static")

    templates = Jinja2Templates(directory="/root/web/templates")

    def _get_app_or_raise(app_id: str) -> SandboxApp:
        sandbox_app = app_directory.get_app(app_id)
        if not sandbox_app:
            raise HTTPException(status_code=404, detail="App not found")
        return sandbox_app

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
        print("Fetching home page")
        apps_dict = await _get_apps_dict()
        return templates.TemplateResponse(
            name="pages/home.html", context={"request": request, "apps": apps_dict}
        )

    async def _get_apps_dict():
        # app_directory already loaded on startup
        # TODO(joy): Passing in the client is unclean, figure out a better way to do this.
        # async with httpx.AsyncClient() as client:
        #     await app_directory.cleanup(client)
        app_directory.load()
        apps_dict = {}
        count = 0
        for app_id, app_metadata in app_directory.apps.items():
            count += 1
            apps_dict[app_id] = {
                "url": app_metadata.sandbox_user_tunnel_url,
                "title": app_metadata.title if hasattr(app_metadata, 'title') else "",
                "is_featured": app_metadata.is_featured if hasattr(app_metadata, 'is_featured') else False
            }
        return apps_dict
        

    @web_app.get("/app/{app_id}")
    async def app_page(request: Request, app_id: str):
        app = _get_app_or_raise(app_id)
        return templates.TemplateResponse(
            name="pages/app.html",
            context={
                "request": request,
                "app_id": app_id,
                "app_url": app.data.sandbox_user_tunnel_url,
                "relay_url": app.data.sandbox_tunnel_url,
                "message_history": app.data.message_history,
                "app_title": app.metadata.title if hasattr(app.metadata, 'title') else "",
                "is_featured": app.metadata.is_featured if hasattr(app.metadata, 'is_featured') else False,
            },
        )

    @web_app.get("/api/apps")
    async def get_apps():
        """Get the list of all apps for live updates"""
        apps_dict = await _get_apps_dict()
        print(f"[API /api/apps] Returning {len(apps_dict)} apps")
        return JSONResponse({"apps": apps_dict})

    @web_app.post("/api/create", response_model=CreateAppResponse)
    async def create_app(request_data: CreateAppRequest) -> CreateAppResponse:
        app_id = await create_sandbox_app.remote.aio(request_data.prompt)
        return CreateAppResponse(app_id=app_id)

    @web_app.post("/api/app/{app_id}/write")
    async def write_app(app_id: str, request_data: WriteAppRequest):
        app = _get_app_or_raise(app_id)
        try:
            print(f"Starting edit for app {app_id} with text: {request_data.text[:100] if request_data.text else ''}...")
            response = await app.edit(request_data.text)
            print(f"Edit completed, response status: {response.status_code}")
            app_directory.set_app(app)
            
            # Try to parse JSON response, handle both sync and async json() methods
            try:
                import inspect
                json_method = response.json()
                # Check if json() returns a coroutine (async) or a dict (sync)
                if inspect.iscoroutine(json_method):
                    response_data = await json_method
                else:
                    response_data = json_method
                print(f"Successfully parsed response JSON: {response_data}")
            except Exception as json_error:
                print(f"Failed to parse JSON response: {json_error}")
                # If JSON parsing fails, return a generic success response
                response_data = {"status": "ok"}
                
            return JSONResponse(response_data, status_code=response.status_code)
        except Exception as e:
            print(f"Error writing to relay with data: {request_data}: {str(e)}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.get("/api/app/{app_id}/history")
    async def get_message_history(app_id: str):
        """Get the message history for an app"""
        app = _get_app_or_raise(app_id)
        history_data = [
            {"content": msg.content, "type": msg.type.value}
            for msg in app.data.message_history
        ]
        return JSONResponse(
            {"message_history": history_data},
            headers={
                # TODO(joy): Figure out what this does so I'm not blindly vibe coding.
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    @web_app.get("/api/app/{app_id}/status")
    async def get_app_status(app_id: str):
        """Return the current metadata status for the requested app without pinging the sandbox."""
        app = _get_app_or_raise(app_id)
        return JSONResponse({"status": app.metadata.status.value})

    @web_app.get("/api/app/{app_id}/ping")
    async def ping_app(app_id: str):
        app = _get_app_or_raise(app_id)
        heartbeat_url = f"{app.data.sandbox_tunnel_url}/heartbeat"
        try:
            print(f"Pinging relay at: {heartbeat_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(heartbeat_url, timeout=2.0)
                print(f"Ping response status: {response.status_code}")
                # Handle both sync and async json() methods
                import inspect
                json_method = response.json()
                if inspect.iscoroutine(json_method):
                    response_data = await json_method
                else:
                    response_data = json_method
                return JSONResponse(response_data, status_code=response.status_code)
        except Exception as e:
            print(f"Error pinging relay: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.post("/api/app/{app_id}/terminate")
    async def terminate_app(app_id: str, request_data: TerminateAppRequest):
        """Terminate a sandbox app with admin authentication"""
        admin_secret = os.getenv("ADMIN_SECRET")
        if not admin_secret:
            return JSONResponse({"status": "error", "message": "Admin functionality not configured"}, status_code=503)
        
        if request_data.admin_secret != admin_secret:
            return JSONResponse({"status": "error", "message": "Invalid admin secret"}, status_code=403)
        
        app = _get_app_or_raise(app_id)
        try:
            success = app.terminate()
            if success:
                app_directory.remove_app(app_id)
                return JSONResponse({"status": "success", "message": f"Sandbox {app_id} terminated successfully"})
            else:
                return JSONResponse({"status": "error", "message": "Failed to terminate sandbox"}, status_code=500)
        except Exception as e:
            print(f"Error terminating sandbox {app_id}: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    
    @web_app.post("/api/app/{app_id}/snapshot")
    async def snapshot_app(app_id: str, request_data: SnapshotAppRequest):
        """Snapshot an app with admin authentication"""
        admin_secret = os.environ.get("ADMIN_SECRET", "")
        if not admin_secret or request_data.admin_secret != admin_secret:
            raise HTTPException(status_code=403, detail="Invalid admin secret")
        
        app = _get_app_or_raise(app_id)
        sandbox = modal.Sandbox.from_object_id(app.data.sandbox_object_id)
        image = sandbox.snapshot_filesystem()
        return JSONResponse({"status": "success", "image": image.object_id}, status_code=200)

    @web_app.post("/api/app/{app_id}/toggle-feature")
    async def toggle_feature_app(app_id: str, request_data: ToggleFeatureRequest):
        """Toggle featured status for an app with admin authentication"""
        admin_secret = os.environ.get("ADMIN_SECRET", "")
        if not admin_secret or request_data.admin_secret != admin_secret:
            raise HTTPException(status_code=403, detail="Invalid admin secret")
        
        app = _get_app_or_raise(app_id)
        
        try:
            app.metadata.is_featured = not getattr(app.metadata, 'is_featured', False)
            app.metadata.updated_at = datetime.now()
            
            app_directory.set_app(app)
            
            return JSONResponse({
                "status": "success", 
                "is_featured": app.metadata.is_featured,
                "message": f"App {app_id} is now {'featured' if app.metadata.is_featured else 'not featured'}"
            })
        except Exception as e:
            print(f"Error toggling feature status for {app_id}: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.post("/api/admin/terminate-all")
    async def terminate_all_sandboxes(request_data: TerminateAppRequest):
        """Terminate all sandbox apps with admin authentication"""
        admin_secret = os.getenv("ADMIN_SECRET")
        if not admin_secret:
            return JSONResponse({"status": "error", "message": "Admin functionality not configured"}, status_code=503)
        
        if request_data.admin_secret != admin_secret:
            return JSONResponse({"status": "error", "message": "Invalid admin secret"}, status_code=403)
        
        app_directory.load()  # Ensure we have the latest apps
        apps = app_directory.apps.keys()
        terminated_count = 0
        failed_count = 0
        apps_copy = list(apps)
        
        for app_id in apps_copy:
            try:
                sandbox_app = app_directory.get_app(app_id)
                if not sandbox_app:
                    print(f"❌ App {app_id} not found in catalogue")
                    continue
                success = sandbox_app.terminate()
                app_directory.remove_app(app_id)
                if success:
                    terminated_count += 1
                    print(f"✅ Terminated sandbox: {app_id}")
                else:
                    failed_count += 1
                    print(f"❌ Failed to terminate sandbox: {app_id}")
            except Exception as e:
                failed_count += 1
                print(f"❌ Error terminating sandbox {app_id}: {str(e)}")
        
        for sandbox in modal.Sandbox.list(app_id=app.app_id):
            print(f"Sandbox: {sandbox.object_id}")
            sandbox.terminate()

        return JSONResponse({
            "status": "success", 
            "message": f"Terminated {terminated_count} sandboxes successfully, {failed_count} failed",
            "terminated": terminated_count,
            "failed": failed_count
        })

    return web_app

@app.function(schedule=modal.Period(minutes=1))
async def clean_up_dead_apps():
    import httpx

    app_directory = AppDirectory(apps_dict, app, llm_client)
    app_directory.load()  # Load apps for cleanup
    # TODO(joy): I do not like how these async clients are created. Unclean.
    # Use more resilient client settings for cleanup
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    timeout = httpx.Timeout(timeout=30.0, connect=10.0, read=10.0)
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        await app_directory.cleanup(client)
