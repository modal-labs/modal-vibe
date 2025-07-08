"""
This is a simple FastAPI server that can be used to test the sandbox server.

This file is read in by the sandbox server and executed in the sandbox.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

fastapi_app = FastAPI()

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def is_component_valid(component: str) -> bool:
    return "export default" in component


class EditRequest(BaseModel):
    component: str


@fastapi_app.post("/edit")
async def edit_text(request: EditRequest):
    global display_html
    llm_react_app = request.component
    if not is_component_valid(llm_react_app):
        print(f"Invalid component: {llm_react_app}")
        return {"status": "error", "message": "Invalid component"}

    print(f"Existing component: {llm_react_app}")
    with open("/root/vite-app/src/LLMComponent.tsx", "w+") as f:
        f.write(llm_react_app)
    print(f"Component edited to: {llm_react_app}")
    return {"status": "ok"}


@fastapi_app.get("/heartbeat")
async def heartbeat():
    print("Heartbeat received")
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)
