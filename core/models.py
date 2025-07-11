"""Core models for the sandbox app."""

from enum import Enum
from core.app_planner import AppPlan, AppPlanner
from core.llm import generate_response
import asyncio
import httpx
from pydantic import BaseModel
import modal
import anthropic


class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"

    def __str__(self):
        return self.value


class Message(BaseModel):
    content: str
    type: MessageType


class SandboxApp:
    id: str
    message_history: list[Message]
    current_planner: AppPlanner
    plan_history: list[AppPlan]
    sandbox_tunnel_url: str
    _ready: bool

    def __init__(
        self, id: str, app: modal.App, image: modal.Image, client: anthropic.Anthropic
    ):
        self.id = id
        self.message_history = []
        self.current_planner = AppPlanner(client=client)
        self._ready = False
        from sandbox.start_sandbox import run_sandbox_server_with_tunnel

        self.sandbox_tunnel_url, self.sandbox_user_tunnel_url, self.sandbox_backend_tunnel_url = (
            run_sandbox_server_with_tunnel(app=app)
        )
        self.client = client
        asyncio.create_task(self._wait_for_sandbox_alive())

    async def wait_for_ready(self, timeout: float = 300.0):
        """Wait for the sandbox server to be ready, with a timeout"""
        start_time = asyncio.get_event_loop().time()
        while not self._ready:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(
                    f"Sandbox server {self.id} did not become ready within {timeout} seconds"
                )
            await asyncio.sleep(0.5)

    async def _generate_edit(self, message: str):
        await self.wait_for_ready()
        await self.current_planner.generate(message)
        self.message_history.append(Message(content=message, type=MessageType.USER))
        self.plan_history.append(self.current_planner.plan)
        print(f"Generated edit: {self.current_planner.plan.overview}")

    async def edit(
        self,
        message: str,
    ) -> httpx.Response:
        edit_url = f"{self.sandbox_tunnel_url}/edit"
        async with httpx.AsyncClient() as client:
            await self._generate_edit(message)
            explaination = self.current_planner.explain(message, self.plan_history[-1], self.current_planner.plan)
            self.message_history.append(Message(content=explaination, type=MessageType.ASSISTANT))
            response = await client.post(
                edit_url,
                json={
                    "component": str(self.current_planner.plan.frontend_component),
                    "backend_code": str(self.current_planner.plan.backend_code),
                },
                timeout=60.0,
            )
            print(f"Write response status: {response.status_code}")
            return response

    
    async def _wait_for_sandbox_alive(self, max_attempts: int = 30, delay: float = 2.0):
        """Wait for the sandbox server to be ready by polling the heartbeat endpoint"""
        heartbeat_url = f"{self.sandbox_tunnel_url}/heartbeat"

        for attempt in range(max_attempts):
            try:
                print(
                    f"Health check attempt {attempt + 1}/{max_attempts} for {self.id}"
                )
                async with httpx.AsyncClient() as client:
                    response = await client.get(heartbeat_url, timeout=30.0)
                    if response.status_code == 200:
                        print(f"✅ Sandbox server {self.id} is ready!")
                        self._ready = True
                        return
            except Exception as e:
                print(f"Health check attempt {attempt + 1} failed: {str(e)}")

            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

        print(
            f"❌ Sandbox server {self.id} failed to become ready after {max_attempts} attempts"
        )

    async def is_alive(self) -> bool:
        """Check if the sandbox server is alive by making a heartbeat request"""
        if not self._ready:
            return False

        heartbeat_url = f"{self.sandbox_tunnel_url}/heartbeat"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(heartbeat_url, timeout=10.0)
                return response.status_code == 200
        except Exception as e:
            print(f"Health check failed for {self.id}: {str(e)}")
            return False
