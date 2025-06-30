from pathlib import Path
import modal
import os


SANDBOX_TIMEOUT = 3600

app = modal.App("likeable-sandbox-server")

def read_server_script():
    """Read the FastAPI server script from file"""
    script_path = os.path.join(os.path.dirname(__file__), "server.py")
    with open(script_path, "r") as f:
        return f.read()

PATH = Path(__file__).parent
SERVER_PATH = PATH / "server.py"
if not SERVER_PATH.exists():
    raise FileNotFoundError(f"server.py not found at {SERVER_PATH}")
SERVER_SCRIPT = read_server_script()

image = (modal.Image.debian_slim()
    .pip_install("fastapi", "uvicorn", "pydantic")
    .add_local_file(str(SERVER_PATH), "/root/server.py")
)


@app.function(image=image, timeout=SANDBOX_TIMEOUT)
def run_sandbox_server_with_tunnel():
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    
    with open("/root/server.py", "r") as f:
        server_script = f.read()

    sb = modal.Sandbox.create(
        image=image,
        app=app,
        timeout=SANDBOX_TIMEOUT,
        encrypted_ports=[8000]
    )
    print(f"📋 Created sandbox with ID: {sb.object_id}")

    with sb.open("/tmp/server.py", "w") as f:
        f.write(server_script)
    
    print("Server script uploaded to sandbox")
    print("Starting HTTP server on port 8000...")

    tunnel = sb.tunnels()[8000]
    print(f"\n🚀 Creating HTTP Server with tunnel!")
    print(f"🌐 Public URL: {tunnel.url}")
    print(f"🔒 TLS Socket: {tunnel.tls_socket}")
    print("\n📡 Available endpoints:")
    print(f"  POST {tunnel.url}/edit - Update display text")
    print(f"  GET  {tunnel.url}/heartbeat - Health check")
    print(f"  GET  {tunnel.url}/display - View current text")
    print(f"\n💡 You can now access these endpoints from anywhere on the internet!")
    
    
    
    try:
        server_process = sb.exec("python", "/tmp/server.py")
        for line in server_process.stdout:
            print(f"[SERVER] {line.rstrip()}")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server and closing tunnel...")
    finally:
        sb.terminate()
        print("✅ Sandbox terminated and tunnel closed")

@app.local_entrypoint()
def main():
    """Main entrypoint for modal run command"""
    print("Starting Modal Sandbox HTTP Server with public tunnel...")
    run_sandbox_server_with_tunnel.remote()

if __name__ == "__main__":
    run_sandbox_server_with_tunnel.remote()