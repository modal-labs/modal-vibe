import modal
import uuid
import os
from pathlib import Path

# Create Modal image with all required dependencies
image = (modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "jinja2",
        "python-multipart"
    )
    .copy_local_dir("web/static", "/root/static")
    .copy_local_dir("web/templates", "/root/templates")
)
app = modal.App(image=image)

apps = {}

@app.function(image=image)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates

    web_app = FastAPI()
    
    # Mount static files
    web_app.mount("/static", StaticFiles(directory="/root/static"), name="static")
    
    # Templates
    templates = Jinja2Templates(directory="/root/templates")

    @web_app.get("/")
    async def home(request: Request):
        return templates.TemplateResponse(
            name="pages/home.html",
            context={"request": request}
        )

    @web_app.post("/api/create")
    async def create_app():
        app_id = str(uuid.uuid4())
        apps[app_id] = {"content": ""}
        return JSONResponse({"app_id": app_id})

    @web_app.get("/app/{app_id}")
    async def app_page(request: Request, app_id: str):
        if app_id not in apps:
            # If app doesn't exist, create it
            apps[app_id] = {"content": ""}
        return templates.TemplateResponse(
            name="pages/app.html",
            context={
                "request": request,
                "app_id": app_id
            }
        )

    @web_app.post("/api/app/{app_id}/write")
    async def write_app(app_id: str, text: str):
        if app_id in apps:
            apps[app_id]["content"] = text
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "error", "message": "App not found"}, status_code=404)

    @web_app.get("/api/app/{app_id}/ping")
    async def ping_app(app_id: str):
        if app_id in apps:
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "error", "message": "App not found"}, status_code=404)

    return web_app