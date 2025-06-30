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
display_html = "<html><body><h1>Hello World</h1></body></html>"

class EditRequest(BaseModel):
    html: str

@app.post("/edit")
async def edit_text(request: EditRequest):
    global display_html
    display_html = request.html
    print(f"HTML edited to: {display_html}")
    return {"status": "ok"}

@app.get("/heartbeat")
async def heartbeat():
    print("Heartbeat received")
    return {"status": "ok"}

@app.get("/display", response_class=HTMLResponse)
async def display():
    global display_html
    print(f"Displaying HTML: {display_html}")
    return HTMLResponse(content=display_html)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 