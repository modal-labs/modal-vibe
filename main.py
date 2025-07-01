"""Main entrypoint that runs the FastAPI controller that serves the web app and manages the sandbox apps."""

from datetime import datetime
from core.llm import get_client
from core.models import SandboxApp
import modal
import uuid
from dotenv import load_dotenv
import asyncio

load_dotenv()
client = get_client()
image = (modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "jinja2",
        "python-multipart",
        "httpx",
        "python-dotenv",
        "anthropic"
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
            name="pages/404.html",
            context={"request": request},
            status_code=404
        )
    
    @web_app.exception_handler(503)
    async def service_unavailable_handler(request: Request, exc):
        return templates.TemplateResponse(
            name="pages/503.html",
            context={"request": request},
            status_code=503
        )

    @web_app.get("/")
    async def home(request: Request):
        app_list = list(apps.keys())
        return templates.TemplateResponse(
            name="pages/home.html",
            context={"request": request, "apps": app_list}
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
                "message_history": app.message_history
            }
        )

    @web_app.post("/api/create")
    async def create_app(request: Request):
        data = await request.json()
        time = datetime.now().strftime("%Y%m%d%H%M%S")
        app_id = str(uuid.uuid4()) + f"_{time}"
        apps[app_id] = SandboxApp(app_id, app, image, client)
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
                response = await client.get(
                    heartbeat_url,
                    timeout=10.0
                )
                print(f"Ping response status: {response.status_code}")
                return JSONResponse(response.json(), status_code=response.status_code)
        except Exception as e:
            print(f"Error pinging relay: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.get("/api/app/{app_id}/display")
    async def display_app(app_id: str):
        app = _get_app_or_raise(app_id)
        
        try:
            await app.wait_for_ready()
        except TimeoutError as e:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Loading...</title>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif; 
                        text-align: center; 
                        padding: 50px; 
                        color: #666;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .loading-container {{
                        background: rgba(30, 41, 59, 0.95);
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    }}
                    .spinner {{
                        border: 4px solid #f3f3f3;
                        border-top: 4px solid #667eea;
                        border-radius: 50%;
                        width: 40px;
                        height: 40px;
                        animation: spin 1s linear infinite;
                        margin: 0 auto 20px;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
            </head>
            <body>
                <div class="loading-container">
                    <div class="spinner"></div>
                    <h2>Starting your app...</h2>
                    <p>Please wait while we initialize your sandbox environment.</p>
                    <p><small>This usually takes 10-30 seconds</small></p>
                </div>
                <script>
                    // Auto-refresh every 5 seconds
                    setTimeout(() => {{
                        window.location.reload();
                    }}, 5000);
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=503)
        
        display_url = f"{app.sandbox_tunnel_url}/display"
        print(f"Attempting to fetch display from: {display_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    display_url,
                    timeout=120.0
                )
                print(f"Relay response status: {response.status_code}")
                if response.status_code == 200:
                    return HTMLResponse(content=response.text, status_code=response.status_code)
                else:
                    print(f"Relay returned non-200 status: {response.status_code}, text: {response.text}")
                    raise Exception(f"Relay server returned {response.status_code}")
        except Exception as e:
            print(f"Error connecting to relay: {str(e)}")
            raise HTTPException(status_code=503, detail="Service Unavailable")

    return web_app
