"""
This is a simple FastAPI server that can be used to test the sandbox server.

This file is read in by the sandbox server and executed in the sandbox.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global state to track display text
display_text = "Hello World"

class EditRequest(BaseModel):
    text: str

@app.post("/edit")
async def edit_text(request: EditRequest):
    global display_text
    display_text = request.text
    print(f"Text edited to: {display_text}")
    return {"status": "ok"}

@app.get("/heartbeat")
async def heartbeat():
    print("Heartbeat received")
    return {"status": "ok"}

@app.get("/display", response_class=HTMLResponse)
async def display():
    global display_text
    print(f"Displaying text: {display_text}")
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Display</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            h1 {{ color: #333; }}
        </style>
    </head>
    <body>
        <h1>{display_text}</h1>
        <p><em>Last updated: <span id="timestamp"></span></em></p>
        <script>
            document.getElementById('timestamp').textContent = new Date().toLocaleString();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 