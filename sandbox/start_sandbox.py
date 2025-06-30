"""TODO: useless now, remove?"""
import modal

SANDBOX_TIMEOUT = 86400


sandbox_image = (modal.Image.debian_slim()
    .pip_install(
        "fastapi[standard]",
    )
    .add_local_dir("sandbox", "/root/sandbox")
    .add_local_file("sandbox/server.py", "/tmp/server.py")
)

def run_sandbox_server_with_tunnel(app: modal.App):
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    with open("/root/sandbox/server.py", "r") as f:
        server_script = f.read()

    sb = modal.Sandbox.create(
        "python", "/tmp/server.py",
        image=sandbox_image,
        app=app,
        timeout=SANDBOX_TIMEOUT,
        encrypted_ports=[8000]
    )
    print(f"📋 Created sandbox with ID: {sb.object_id}")

    tunnel = sb.tunnels()[8000]
    print(f"\n🚀 Creating HTTP Server with tunnel!")
    print(f"🌐 Public URL: {tunnel.url}")
    print(f"🔒 TLS Socket: {tunnel.tls_socket}")
    print("\n📡 Available endpoints:")
    print(f"  POST {tunnel.url}/edit - Update display text")
    print(f"  GET  {tunnel.url}/heartbeat - Health check")
    print(f"  GET  {tunnel.url}/display - View current text")
    print(f"\n💡 You can now access these endpoints from anywhere on the internet!")
    
    return tunnel.url

if __name__ == "__main__":
    app = modal.App("modal-vibe-sandbox-server")
    run_sandbox_server_with_tunnel.remote(app)