import asyncio
from core.models import AppData, AppMetadata, AppStatus, Message, MessageType
from core.prompt import generate_and_explain_init_edit, _generate_followup_edit, _explain_followup_edit
import httpx
import modal
import anthropic
from datetime import datetime
import typing as t


class SandboxApp:
    id: str
    metadata: t.Optional[AppMetadata] = None
    data: t.Optional[AppData] = None
    _wait_for_sandbox_alive_task: t.Optional[asyncio.Task] = None

    @property
    def edit_url(self) -> str:
        if self.data is None:
            raise ValueError("Data is not set")
        return f"{self.data.sandbox_tunnel_url}/edit"

    def __init__(
        self,
        app_id: str,
        client: anthropic.Anthropic,
        metadata: AppMetadata,
        data: AppData,
    ):
        self.id = app_id
        self.client = client
        self.metadata = metadata
        self.data = data

    @staticmethod
    async def create(
        app: modal.App, 
        client: anthropic.Anthropic,
        message: str,
        image: modal.Image,
    ) -> "SandboxApp":
        from sandbox.start_sandbox import run_sandbox_server_with_tunnel

        create_sandbox_task = asyncio.create_task(
            run_sandbox_server_with_tunnel(app=app, image=image)
        )
        create_init_edit_task = asyncio.create_task(
            generate_and_explain_init_edit(client, message)
        )
        sandbox, init_edit = await asyncio.gather(create_sandbox_task, create_init_edit_task)
        sandbox_tunnel_url, sandbox_user_tunnel_url, sandbox_object_id = sandbox
        edit, explanation = init_edit

        sandbox_app = SandboxApp(
            app_id=sandbox_object_id,
            client=client,
            metadata=AppMetadata(
                id=sandbox_object_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status=AppStatus.CREATED,
                sandbox_user_tunnel_url=sandbox_user_tunnel_url,
                title=message,
            ),
            data=AppData(
                id=sandbox_object_id,
                message_history=[
                    Message(content=message, type=MessageType.USER),
                    Message(content=explanation, type=MessageType.ASSISTANT),
                ],
                current_component=edit,
                sandbox_tunnel_url=sandbox_tunnel_url,
                sandbox_user_tunnel_url=sandbox_user_tunnel_url,
                sandbox_object_id=sandbox_object_id,
            ),
        )
        await sandbox_app._wait_for_sandbox_alive()
        async with httpx.AsyncClient() as web_client:

            response = await web_client.post(
                    sandbox_app.edit_url,
                    json={"component": str(edit)},
                    timeout=60.0,
            )
            print(f"Wrote initial edit to sandbox app: {response.status_code}")
            response.raise_for_status()
        return sandbox_app
            
    
    async def edit(
        self,
        message: str,
    ) -> httpx.Response:
        if self.metadata.status not in (AppStatus.READY, AppStatus.ACTIVE):
            raise ValueError("Sandbox is not ready or active")
        self.data.message_history.append(
            Message(content=message, type=MessageType.USER)
        )
        
        original_html = self.data.current_component
        async with httpx.AsyncClient() as web_client:
            self.metadata.updated_at = datetime.now()
            edit = await _generate_followup_edit(self.client, message, self.data.current_component, self.data.message_history)
            self.data.current_component = edit
            response = await web_client.post(
                self.edit_url,
                json={"component": str(edit)},
                timeout=60.0,
            )
            response.raise_for_status()
            explanation = await _explain_followup_edit(self.client, message, original_html, edit)
            self.data.message_history.append(
                Message(content=explanation, type=MessageType.ASSISTANT)
            )
            print(f"Write response status: {response.status_code}")

        self.metadata.status = AppStatus.ACTIVE
        return response


    async def _wait_for_sandbox_alive(self, max_attempts: int = 30, delay: float = 1.0):
        """Wait for the sandbox server to be ready by polling the heartbeat endpoint"""
        async with httpx.AsyncClient() as client:
            for attempt in range(max_attempts):
                try:
                    print(
                        f"Health check attempt {attempt + 1}/{max_attempts} for {self.id}"
                    )
                    if await self.is_alive(client):
                        print(f"✅ Sandbox server {self.id} is ready!")
                        self.metadata.status = AppStatus.READY
                        return
                except Exception as e:
                    print(f"Health check attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
            print(
                f"❌ Sandbox server {self.id} failed to become ready after {max_attempts} attempts"
            )
            self.metadata.status = AppStatus.TERMINATED

    async def is_alive(self, client: httpx.AsyncClient) -> bool:
        """Check if the sandbox server is alive by making a heartbeat request"""
        if self.metadata.status == AppStatus.TERMINATED:
            return False
        heartbeat_url = f"{self.data.sandbox_tunnel_url}/heartbeat"
        try:
            response = await client.get(heartbeat_url, timeout=10.0)
            return response.status_code == 200
        except Exception as e:
            # TODO(joy): if it is not alive, instead of deleting it, we should allow sandboxes to be reactivated.
            print(f"Health check failed for {self.id}: {str(e)}")
            return False
    
    def terminate(self) -> bool:
        """Terminate the sandbox using its object_id"""
        try:
            sandbox = modal.Sandbox.from_id(self.data.sandbox_object_id)
            sandbox.terminate()
            self.metadata.status = AppStatus.TERMINATED
            print(f"✅ Successfully terminated sandbox {self.id} (object_id: {self.data.sandbox_object_id})")
            return True
        except Exception as e:
            print(f"❌ Failed to terminate sandbox {self.id}: {str(e)}")
            return False

class AppDirectory:
    """Manages the directory of created sandbox apps."""
    apps: dict[str, AppMetadata] = {}

    def __init__(self, apps_dict: modal.Dict, app: modal.App, client: anthropic.Anthropic):
        self.apps_dict = apps_dict
        self.app = app
        self.client = client
        self.apps = {}


    def load(self) -> None:
        try:
            catalogue_data = self.apps_dict.get("catalogue", {})
            self.apps = {app_id: AppMetadata.model_validate(app_data) 
                        for app_id, app_data in catalogue_data.items()}
            print(f"[AppDirectory.load] Loaded {len(self.apps)} apps from Modal Dict")
        except Exception as e:
            print(f"Error loading apps from dict: {e}")
            self.apps = {}
    
    async def cleanup(self, client: httpx.AsyncClient) -> None:
        """Cleanup dead apps from the dict"""
        print("Cleaning up dead apps")
        self.load()
        apps = self.apps.copy()
        for app_id, metadata in apps.items():
            print(f"Checking app {app_id}, last updated at {metadata.updated_at}, status {metadata.status}")
            app = self.get_app(app_id)
            if not app:
                print(f"App {app_id} not found in directory")
                self.remove_app(app_id)
                continue
            if not await app.is_alive(client):
                print(f"App {app_id} is not alive")
                self.remove_app(app_id)
                continue
            if app.metadata.status == AppStatus.TERMINATED:
                print(f"App {app_id} is terminated")
                print(f"Removing terminated app {app_id}")
                self.remove_app(app_id)

    def set_app(self, app: SandboxApp) -> None:
        """Save or update an app in the directory"""
        try:
            self.apps[app.id] = app.metadata
            
            catalogue_data = self.apps_dict.get("catalogue", {})
            
            catalogue_data[app.id] = app.metadata.model_dump()
            
            self.apps_dict["catalogue"] = catalogue_data
            
            app_data_dict = app.data.model_dump()
            self.apps_dict[f"app_{app.id}"] = app_data_dict
                
            print(f"[AppDirectory.set_app] Saved app {app.id} to Modal Dict with {len(app.data.message_history)} messages and component of length {len(app.data.current_component)}")
            print(f"[AppDirectory.set_app] Total apps in catalogue: {len(catalogue_data)}")
        except Exception as e:
            print(f"Error saving app {app.id} to dict: {e}")
    
    def remove_app(self, app_id: str) -> None:
        del self.apps[app_id]
        
        catalogue_data = {}
        for remaining_app_id, metadata in self.apps.items():
            catalogue_data[remaining_app_id] = metadata.model_dump()
        
        if f"app_{app_id}" in self.apps_dict:
            self.apps_dict.pop(f"app_{app_id}")
        self.apps_dict.put("catalogue", catalogue_data)
        
        if f"app_{app_id}" in self.apps_dict:
            del self.apps_dict[f"app_{app_id}"]
    
    def get_app(self, app_id: str) -> t.Optional[SandboxApp]:
        """Get an app from the directory"""
        if app_id not in self.apps:
            catalogue_data = self.apps_dict.get("catalogue", {})
            if app_id not in catalogue_data:
                return None
            try:
                self.apps[app_id] = AppMetadata.model_validate(catalogue_data[app_id])
            except Exception as e:
                print(f"Error loading metadata for app {app_id}: {e}")
                return None
        
        app_metadata = self.apps[app_id]
        
        app_data_dict = self.apps_dict.get(f"app_{app_id}")
        if app_data_dict is None:
            print(f"Inconsistent state: App data for {app_id} does not exist but app {app_id} is in the catalogue")
            return None
        
        message_history = []
        for msg_data in app_data_dict.get("message_history", []):
            message_history.append(Message.model_validate(msg_data))
        
        app_data = AppData(
            id=app_data_dict["id"],
            message_history=message_history,
            current_component=app_data_dict["current_component"],
            sandbox_tunnel_url=app_data_dict["sandbox_tunnel_url"],
            sandbox_user_tunnel_url=app_data_dict["sandbox_user_tunnel_url"],
            sandbox_object_id=app_data_dict["sandbox_object_id"],
        )
        
        return SandboxApp(app_id, self.client, app_metadata, app_data)
