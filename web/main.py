import modal
import uuid
import os
from pathlib import Path
import httpx
import asyncio
from dotenv import load_dotenv
import anthropic
from dotenv import load_dotenv

load_dotenv()
# Remove trailing slash to avoid double slashes in URL construction
RELAY_URL = os.getenv("RELAY_URL", "https://snft5ergfn03bp.r402.modal.host").rstrip('/')
if not RELAY_URL:
    raise ValueError("RELAY_URL is not set")


print(f"Using RELAY_URL: {RELAY_URL}")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def generate_response(prompt):
    message = client.messages.create(
        model="claude-opus-4-20250514",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return message.content[0].text

def generate_edit(prompt: str):
    prompt = f"""
    You are Jeffrey Zeldman's top web designer. You are given the following prompt and your job is to generate an HTML that is a good example of the prompt.
    Prompt: {prompt}

    RESPONSE FORMAT:
    <html>
        <body>
            <h1>Hello World</h1>
        </body>
    </html>

    DO NOT include any other text in your response. Only the HTML.
    """
    response = generate_response(prompt)
    print(f"Generated edit: {response}")
    return response

# Create Modal image with all required dependencies
image = (modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
        "jinja2",
        "python-multipart",
        "httpx",
        "python-dotenv",
        "anthropic"
    )
    .copy_local_dir("web/static", "/root/static")
    .copy_local_dir("web/templates", "/root/templates")
)
app = modal.App(image=image)


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic-secret")])
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import httpx
    
    current_relay_url = RELAY_URL

    web_app = FastAPI()
    
    web_app.mount("/static", StaticFiles(directory="/root/static"), name="static")
    
    templates = Jinja2Templates(directory="/root/templates")

    @web_app.get("/")
    async def home(request: Request):
        return templates.TemplateResponse(
            name="pages/home.html",
            context={"request": request}
        )

    @web_app.get("/health")
    async def health_check():
        """Health check endpoint that shows current configuration"""
        return JSONResponse({
            "status": "ok",
            "relay_url": current_relay_url,
            "timestamp": str(uuid.uuid4())  # Quick timestamp substitute
        })

    @web_app.post("/api/create")
    async def create_app():
        app_id = str(uuid.uuid4())
        return JSONResponse({"app_id": app_id})

    @web_app.get("/app/{app_id}")
    async def app_page(request: Request, app_id: str):
        return templates.TemplateResponse(
            name="pages/app.html",
            context={
                "request": request,
                "app_id": app_id,
                "relay_url": current_relay_url
            }
        )

    @web_app.post("/api/app/{app_id}/write")
    async def write_app(app_id: str, request: Request):
        edit_url = f"{current_relay_url}/edit"
        try:
            data = await request.json()
            print(f"Writing to relay at: {edit_url} with data: {data}")
            async with httpx.AsyncClient() as client:
                edit = generate_edit(data["text"])
                response = await client.post(
                    edit_url,
                    json={
                        "html": str(edit),
                    },
                    timeout=30.0
                )
                print(f"Write response status: {response.status_code}")
                return JSONResponse(response.json(), status_code=response.status_code)
        except Exception as e:
            print(f"Error writing to relay with data: {data}: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.get("/api/app/{app_id}/ping")
    async def ping_app(app_id: str):
        heartbeat_url = f"{current_relay_url}/heartbeat"
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
        display_url = f"{current_relay_url}/display"
        print(f"Attempting to fetch display from: {display_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    display_url,
                    timeout=30.0
                )
                print(f"Relay response status: {response.status_code}")
                if response.status_code == 200:
                    return HTMLResponse(content=response.text, status_code=response.status_code)
                else:
                    print(f"Relay returned non-200 status: {response.status_code}, text: {response.text}")
                    raise Exception(f"Relay server returned {response.status_code}")
        except Exception as e:
            print(f"Error connecting to relay: {str(e)}")
            # Fallback HTML in case relay is down
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Display - Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; color: #666; }}
                </style>
            </head>
            <body>
                <h1>Service Unavailable</h1>
                <p>Cannot connect to app server: {str(e)}</p>
                <p><small>Attempted URL: {display_url}</small></p>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=503)

    return web_app
