"""TODO: useless now, remove?"""
import threading
import modal

SANDBOX_TIMEOUT = 86400


def run_sandbox_monitor_logs(sb: modal.Sandbox, write_to_file: bool = True):
    try:
        server_process = sb.exec("python", "/tmp/server.py")
        for line in server_process.stdout:
            print(f"[SERVER] {line.rstrip()}")
            if write_to_file:
                with open("/tmp/server.log", "a") as f:
                    f.write(f"[SERVER] {line.rstrip()}\n")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server and closing tunnel...")
    finally:
        sb.terminate()
        print("✅ Sandbox terminated and tunnel closed")


def run_sandbox_server_with_tunnel(app: modal.App, image: modal.Image):
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    with open("/root/sandbox/server.py", "r") as f:
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
    
    threading.Thread(target=run_sandbox_monitor_logs, args=(sb,)).start()

    return tunnel.url

if __name__ == "__main__":
    app = modal.App("likeable-sandbox-server")
    run_sandbox_server_with_tunnel.remote(app)