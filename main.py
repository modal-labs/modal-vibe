"""Main entrypoint that runs the FastAPI controller that serves the web app and manages the sandbox apps."""

from datetime import datetime
from core.llm import get_llm_client
from core.models import SandboxApp
import modal
import uuid
from dotenv import load_dotenv
import asyncio

load_dotenv()
llm_client = get_llm_client()
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
app = modal.App(name="modal-vibe", image=image)


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic-secret")])
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import httpx

    apps = {}

    web_app = FastAPI()
    web_app.mount("/static", StaticFiles(directory="/root/web/static"), name="static")

    templates = Jinja2Templates(directory="/root/web/templates")

    def _get_app_or_raise(app_id: str) -> SandboxApp:
        if app_id not in apps:
            raise HTTPException(status_code=404, detail="App not found")
        return apps[app_id]

    async def _cleanup_dead_sandboxes():
        """Check all sandboxes and remove dead ones from the apps dictionary"""
        dead_apps = []
        for app_id, sandbox_app in apps.items():
            try:
                if not await sandbox_app.is_alive():
                    print(f"🧹 Removing dead sandbox: {app_id}")
                    dead_apps.append(app_id)
            except Exception as e:
                print(f"Error checking sandbox {app_id}: {str(e)}")
                dead_apps.append(app_id)

        for app_id in dead_apps:
            del apps[app_id]
            print(f"✅ Removed dead sandbox: {app_id}")

    async def background_cleanup_task(interval: float = 60.0):
        while True:
            try:
                await _cleanup_dead_sandboxes()
            except Exception as e:
                print(f"Error in background cleanup: {e}")
            await asyncio.sleep(interval)

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
        apps[app_id] = SandboxApp(app_id, app, image, llm_client)
        await apps[app_id].edit(data["prompt"], is_init=True)
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
