"""Local development server for the app."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

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
    You are Jeffrey Zeldman's top web designer. You are given the following prompt and your job is to generate a React component that is a good example of the prompt.
    You should use Tailwind CSS for styling. Please make sure to export the component as default.
    This is incredibly important for my job, please be careful and don't make any mistakes.
    Make sure you import all necessary dependencies.

    Prompt: {prompt}

    RESPONSE FORMAT:
    export default function LLMComponent() {{
        return (
            <div className="bg-red-500">
                <h1>LLM Component</h1>
            </div>
        )
    }}

    DO NOT include any other text in your response. Only the React component.
    """
    response = generate_response(prompt)
    print(f"Generated edit: {response}")
    return response


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        name="pages/home.html", context={"request": request}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint that shows current configuration"""
    return JSONResponse({"status": "ok", "timestamp": str(uuid.uuid4())})


@app.post("/api/create")
async def create_app():
    app_id = str(uuid.uuid4())
    return JSONResponse({"app_id": app_id})


@app.get("/app/{app_id}")
async def app_page(request: Request, app_id: str):
    return templates.TemplateResponse(
        name="pages/app.html", context={"request": request, "app_id": app_id}
    )


@app.post("/api/app/{app_id}/write")
async def write_app(app_id: str, request: Request):
    try:
        data = await request.json()
        edit = generate_edit(data["text"])
        return JSONResponse({"component": str(edit)})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/app/{app_id}/ping")
async def ping_app(app_id: str):
    return JSONResponse({"status": "ok"})


@app.get("/api/app/{app_id}/display")
async def display_app(app_id: str):
    try:
        # For local development, we'll return a simple HTML
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Local Preview</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
            </style>
        </head>
        <body>
            <h1>Local Preview</h1>
            <p>This is a local preview of your app. Edit the text in the left panel to update this preview.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(
            content=f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>",
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("local:app", host="0.0.0.0", port=8000, reload=True)
