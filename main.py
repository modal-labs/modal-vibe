from datetime import datetime
from enum import Enum
from utils.llm import generate_response
import modal
import uuid
import os
from dotenv import load_dotenv
import anthropic
import asyncio
import httpx
from pydantic import BaseModel

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
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
    .add_local_dir("utils", "/root/utils")
)
app = modal.App(name="modal-vibe", image=image)

class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"

    def __str__(self):
        return self.value

class Message(BaseModel):
    content: str
    type: MessageType

class App:
    id: str
    message_history: list[Message]
    current_html: str
    sandbox_tunnel_url: str
    _ready: bool

    def __init__(self, id: str):
        self.id = id
        self.message_history = []
        self.current_html = ""
        self._ready = False
        from sandbox.start_sandbox import run_sandbox_server_with_tunnel
        self.sandbox_tunnel_url = run_sandbox_server_with_tunnel(app=app, image=image)
        asyncio.create_task(self._wait_for_sandbox_alive())

    async def wait_for_ready(self, timeout: float = 300.0):
        """Wait for the sandbox server to be ready, with a timeout"""
        start_time = asyncio.get_event_loop().time()
        while not self._ready:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Sandbox server {self.id} did not become ready within {timeout} seconds")
            await asyncio.sleep(0.5)

    async def generate_edit(self, message: str, is_init: bool = False):
        await self.wait_for_ready()
        html_gen_prompt = f"""
        The existing HTML you are working with is this.
        {self.current_html}

        You are asked to make the following changes to the HTML:
        {message}
        """ if not is_init else f"""
        You are asked to generate an HTML that is a good example of the prompt.
        Prompt: {message}
        """

        prompt = f"""
        You are Jeffrey Zeldman's top web designer. You are given the following prompt and your job is to generate an HTML that is a good example of the prompt.
        Prompt: {message}

        {html_gen_prompt}


        RESPONSE FORMAT:
        <html>
            <body>
                <h1>Hello World</h1>
            </body>
        </html>

        DO NOT include any other text in your response. Only the HTML.
        """
        response = generate_response(client, prompt)
        self.message_history.append(Message(content=message, type=MessageType.USER))
        self.current_html = response
        print(f"Generated edit: {response}")
        return response

    def explain_edit(self, message: str, original_html: str, new_html: str):
        explaination = generate_response(client, f"""
        You generated the following HTML edit to the prompt:

        Prompt: {message}

        Original HTML: {original_html}

        New HTML: {new_html}

        Give a response that summarizes the changes you made. An example of a good response is:
        - "Sounds good! I've made the changes you requested. Yay :D"
        - "I colored the background red and added a new button. Let me know if you want anything else!"
        - "I updated the font to a more modern one and added a new section. Cheers!!"


        """, model="claude-3-5-haiku-20241022")   
        self.message_history.append(Message(content=explaination, type=MessageType.ASSISTANT))
        return explaination

    async def _wait_for_sandbox_alive(self, max_attempts: int = 30, delay: float = 2.0):
        """Wait for the sandbox server to be ready by polling the heartbeat endpoint"""
        heartbeat_url = f"{self.sandbox_tunnel_url}/heartbeat"
        
        for attempt in range(max_attempts):
            try:
                print(f"Health check attempt {attempt + 1}/{max_attempts} for {self.id}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        heartbeat_url,
                        timeout=30.0
                    )
                    if response.status_code == 200:
                        print(f"✅ Sandbox server {self.id} is ready!")
                        self._ready = True
                        return
            except Exception as e:
                print(f"Health check attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
        
        print(f"❌ Sandbox server {self.id} failed to become ready after {max_attempts} attempts")


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

    @web_app.get("/")
    async def home(request: Request):
        app_list = list(apps.keys())
        return templates.TemplateResponse(
            name="pages/home.html",
            context={"request": request, "apps": app_list}
        )

    @web_app.post("/api/create")
    async def create_app():
        time = datetime.now().strftime("%Y%m%d%H%M%S")
        app_id = str(uuid.uuid4()) + f"_{time}"
        apps[app_id] = App(app_id)
        return JSONResponse({"app_id": app_id})

    @web_app.get("/app/{app_id}")
    async def app_page(request: Request, app_id: str):
        app = apps[app_id]
        return templates.TemplateResponse(
            name="pages/app.html",
            context={
                "request": request,
                "app_id": app_id,
                "relay_url": app.sandbox_tunnel_url,
                "message_history": apps[app_id].message_history
            }
        )

    @web_app.post("/api/app/{app_id}/write")
    async def write_app(app_id: str, request: Request):
        data = await request.json()
        is_init = data.get("is_init", False)
        app = apps[app_id]
        edit_url = f"{app.sandbox_tunnel_url}/edit"
        try:
            data = await request.json()
            app = apps[app_id]
            async with httpx.AsyncClient() as client:
                edit = await app.generate_edit(data["text"], is_init=is_init)
                # TODO: explain at the same time of generation
                response = await client.post(
                    edit_url,
                    json={
                        "html": str(edit),
                    },
                    timeout=60.0
                )
                print(f"Write response status: {response.status_code}")
                if not is_init:
                    app.explain_edit(data["text"], app.current_html, str(edit))
                return JSONResponse(response.json(), status_code=response.status_code)
        except Exception as e:
            print(f"Error writing to relay with data: {data}: {str(e)}")
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    @web_app.get("/api/app/{app_id}/ping")
    async def ping_app(app_id: str):
        app = apps[app_id]
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
        app = apps[app_id]
        
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
                        background: white;
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
