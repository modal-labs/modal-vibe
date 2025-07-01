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
    current_html: str
    sandbox_tunnel_url: str
    _ready: bool

    def __init__(self, id: str, app: modal.App, image: modal.Image, client: anthropic.Anthropic):
        self.id = id
        self.message_history = []
        self.current_html = ""
        self._ready = False
        from sandbox.start_sandbox import run_sandbox_server_with_tunnel
        self.sandbox_tunnel_url = run_sandbox_server_with_tunnel(app=app, image=image)
        self.client = client
        asyncio.create_task(self._wait_for_sandbox_alive())

    async def wait_for_ready(self, timeout: float = 300.0):
        """Wait for the sandbox server to be ready, with a timeout"""
        start_time = asyncio.get_event_loop().time()
        while not self._ready:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Sandbox server {self.id} did not become ready within {timeout} seconds")
            await asyncio.sleep(0.5)

    async def _generate_edit(self, message: str, is_init: bool = False):
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
        response = generate_response(self.client, prompt)
        self.message_history.append(Message(content=message, type=MessageType.USER))
        self.current_html = response
        print(f"Generated edit: {response}")
        return response
    
    async def edit(
        self, 
        message: str, 
        is_init: bool = False,
    ) -> httpx.Response:
        original_html = self.current_html
        edit_url = f"{self.sandbox_tunnel_url}/edit"
        async with httpx.AsyncClient() as client:
            edit = await self._generate_edit(message, is_init=is_init)
            self.explain_edit(message, original_html, self.current_html, is_init)
            response = await client.post(
                edit_url,
                json={
                    "html": str(edit),
                },
                timeout=60.0
            )
            print(f"Write response status: {response.status_code}")
            return response

    def explain_edit(self, message: str, original_html: str, new_html: str, is_init: bool = False):
        explaination = generate_response(self.client, f"""
        You generated the following HTML edit to the prompt:

        Prompt: {message}

        {f"Original HTML: {original_html}" if not is_init else ""}
       
        Generated HTML: {new_html}
    

        Give a response that summarizes the changes you made. An example of a good response is:
        - "Sounds good! I've made the changes you requested. Yay :D"
        - "I colored the background red and added a new button. Let me know if you want anything else!"
        - "I updated the font to a more modern one and added a new section. Cheers!!"

        Be as concise as possible, but always be friendly!
        """, model="claude-3-5-haiku-20241022", max_tokens=128)   
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

    async def is_alive(self) -> bool:
        """Check if the sandbox server is alive by making a heartbeat request"""
        if not self._ready:
            return False
        
        heartbeat_url = f"{self.sandbox_tunnel_url}/heartbeat"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    heartbeat_url,
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            print(f"Health check failed for {self.id}: {str(e)}")
            return False
