"""Core models for the sandbox app."""

from enum import Enum
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
    current_component: str
    sandbox_tunnel_url: str
    sandbox_user_tunnel_url: str
    sandbox_object_id: str
    _ready: bool

    def __init__(
        self, 
        id: str, 
        app: modal.App, 
        image: modal.Image, 
        client: anthropic.Anthropic,
        sandbox_tunnel_url: str = None,
        sandbox_user_tunnel_url: str = None,
        sandbox_object_id: str = None,
        current_component: str = "",
        message_history: list[Message] = None
    ):
        self.id = id
        self.message_history = message_history or []
        self.current_component = current_component
        self._ready = False
        self.client = client
        
        if sandbox_tunnel_url and sandbox_user_tunnel_url and sandbox_object_id:
            self.sandbox_tunnel_url = sandbox_tunnel_url
            self.sandbox_user_tunnel_url = sandbox_user_tunnel_url
            self.sandbox_object_id = sandbox_object_id
            print(f"Restoring existing sandbox {id} with URL: {sandbox_tunnel_url}")
        else:
            from sandbox.start_sandbox import run_sandbox_server_with_tunnel
            self.sandbox_tunnel_url, self.sandbox_user_tunnel_url, self.sandbox_object_id = (
                run_sandbox_server_with_tunnel(app=app)
            )
            print(f"Created new sandbox {id} with URL: {self.sandbox_tunnel_url}")
        
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

    async def _generate_edit(self, message: str, is_init: bool = False):
        html_gen_prompt = (
            f"""
        The existing React component you are working with is this.
        {self.current_component}

        You are asked to make the following changes to the React component:
        {message}
        """
            if not is_init
            else f"""
        You are asked to generate a React component that is a good example of the prompt.
        Prompt: {message}
        """
        )

        prompt = f"""
        You are Jeffrey Zeldman's top web designer. You are given the following prompt and your job is to generate a React component that is a good example of the prompt.
        You should use Tailwind CSS for styling. Please make sure to export the component as default.
        This is incredibly important for my job, please be careful and don't make any mistakes.
        Make sure you import all necessary dependencies.

        Prompt: {message}

        {html_gen_prompt}

        RESPONSE FORMAT:
        import React from 'react';
        export default function LLMComponent() {{
            return (
                <div className="bg-red-500">
                    <h1>LLM Component</h1>
                </div>
            )
        }}

        DO NOT include any other text in your response. Only the React component. MAKE SURE TO NAME THE COMPONENT "LLMComponent". DO NOT WRAP THE CODE IN A CODE BLOCK.
        """
        response = generate_response(self.client, prompt)
        self.message_history.append(Message(content=message, type=MessageType.USER))
        self.current_component = response
        print(f"Generated edit: {response}")
        return response

    async def edit(
        self,
        message: str,
        is_init: bool = False,
    ) -> httpx.Response:
        original_html = self.current_component
        edit_url = f"{self.sandbox_tunnel_url}/edit"
        async with httpx.AsyncClient() as client:
            edit = await self._generate_edit(message, is_init=is_init)
            self.explain_edit(message, original_html, self.current_component, is_init)
            await self.wait_for_ready()
            response = await client.post(
                edit_url,
                json={
                    "component": str(edit),
                },
                timeout=60.0,
            )
            print(f"Write response status: {response.status_code}")
            return response

    def explain_edit(
        self, message: str, original_html: str, new_html: str, is_init: bool = False
    ):
        if is_init:
            prompt = f"""
            You are Jeffrey Zeldman's top web designer. You were given the following prompt and you generated the following React component:

            Prompt: {message}

            You generated the following React component: {new_html}

            Give a response that summarizes the changes you made. An example of a good response is:
            - "That sounds great! I made a donut chart for you. Let me know if you want anything else!"

            Be as concise as possible, but always be friendly!
            """
        else: 
            prompt = f"""
        You generated the following React component edit to the prompt:

        Prompt: {message}

        {f"Original React component: {original_html}" if not is_init else ""}
       
        Generated React component: {new_html}
    

        Give a response that summarizes the changes you made. An example of a good response is:
        - "Sounds good! I've made the changes you requested. Yay :D"
        - "I colored the background red and added a new button. Let me know if you want anything else!"
        - "I updated the font to a more modern one and added a new section. Cheers!!"

        Be as concise as possible, but always be friendly!
        """
        
        explaination = generate_response(
            self.client,
            prompt,
            model="claude-3-5-haiku-20241022",
            max_tokens=128,
        )
        self.message_history.append(
            Message(content=explaination, type=MessageType.ASSISTANT)
        )
        return explaination

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
    
    def terminate(self) -> bool:
        """Terminate the sandbox using its object_id"""
        try:
            sandbox = modal.Sandbox.from_id(self.sandbox_object_id)
            sandbox.terminate()
            print(f"✅ Successfully terminated sandbox {self.id} (object_id: {self.sandbox_object_id})")
            return True
        except Exception as e:
            print(f"❌ Failed to terminate sandbox {self.id}: {str(e)}")
            return False
    
    def to_dict(self) -> dict:
        """Serialize the SandboxApp to a dictionary for volume storage"""
        return {
            "id": self.id,
            "sandbox_tunnel_url": self.sandbox_tunnel_url,
            "sandbox_user_tunnel_url": self.sandbox_user_tunnel_url,
            "sandbox_object_id": self.sandbox_object_id,
            "current_component": self.current_component,
            "message_history": [
                {"content": msg.content, "type": msg.type.value} 
                for msg in self.message_history
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict, app: modal.App, image: modal.Image, client: anthropic.Anthropic) -> 'SandboxApp':
        """Deserialize a SandboxApp from a dictionary loaded from volume storage"""
        message_history = [
            Message(content=msg["content"], type=MessageType(msg["type"]))
            for msg in data.get("message_history", [])
        ]
        
        return cls(
            id=data["id"],
            app=app,
            image=image,
            client=client,
            sandbox_tunnel_url=data.get("sandbox_tunnel_url"),
            sandbox_user_tunnel_url=data.get("sandbox_user_tunnel_url"),
            sandbox_object_id=data.get("sandbox_object_id"),
            current_component=data.get("current_component", ""),
            message_history=message_history
        )
