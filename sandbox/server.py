"""
This is a simple FastAPI server that can be used to test the sandbox server.

This file is read in by the sandbox server and executed in the sandbox.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

fastapi_app = FastAPI()
templates = Jinja2Templates(directory="web/templates")

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global state to track the React component
llm_react_app = """
"use client";

import { useEffect } from "react";

export default function HomePage() {
  return (
    <main className="p-6 text-center">
      <h1 className="text-3xl font-bold">Simple React App</h1>
    </main>
}
"""


class EditRequest(BaseModel):
    html: str


@fastapi_app.post("/edit")
async def edit_text(request: EditRequest):
    global display_html
    llm_react_app = request.html
    # TODO: Some basic validation on the component - e.g. contains 'export'
    print(f"Existing component: {llm_react_app}")
    with open("/root/vite-app/src/LLMComponent.tsx", "w+") as f:
        f.write(llm_react_app)
    print(f"Component edited to: {llm_react_app}")
    return {"status": "ok"}


@fastapi_app.get("/heartbeat")
async def heartbeat():
    print("Heartbeat received")
    return {"status": "ok"}


@fastapi_app.get("/display", response_class=HTMLResponse)
async def display():
    return HTMLResponse(content="<main>WIP</main>")


@fastapi_app.get("/display/{preview_url}", response_class=HTMLResponse)
async def display_preview(preview_url: str):
    return templates.TemplateResponse(
        "display.html",
        {
            "preview_url": preview_url,
        },
    )


if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
