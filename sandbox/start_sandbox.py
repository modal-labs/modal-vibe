import modal

SANDBOX_TIMEOUT = 86400  # 24 hours
APP_BACKEND_PORT = 8001

sandbox_image = (
    modal.Image.from_registry("node:22-slim", add_python="3.12")
    .env(
        {
            "PNPM_HOME": "/root/.local/share/pnpm",
            "PATH": "$PNPM_HOME:$PATH",
            "SHELL": "/bin/bash",
        }
    )
    .run_commands(
        "corepack enable && corepack prepare pnpm@latest --activate && pnpm setup && pnpm add -g vite"
    )
    .pip_install(
        "fastapi[standard]",
    )
    .add_local_dir("sandbox", "/root/sandbox")
    .add_local_file("sandbox/server.py", "/root/server.py")
    .add_local_file("web/app_backend.py", "/root/app_backend.py")
    .add_local_dir("web/vite-app", "/root/vite-app")
)


def run_sandbox_server_with_tunnel(app: modal.App):
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    sb = modal.Sandbox.create(
        "sh",
        "-c",
        "pnpm install --dir /root/vite-app && pnpm --prefix /root/vite-app dev --host & python -m uvicorn app_backend:app --host 0.0.0.0 --port 8001 & python /root/server.py",
        image=sandbox_image,
        app=app,
        timeout=SANDBOX_TIMEOUT,
        encrypted_ports=[8000, 5173, 8001],
    )
    print(f"📋 Created sandbox with ID: {sb.object_id}")

    main_tunnel = sb.tunnels()[8000]
    user_tunnel = sb.tunnels()[5173]
    backend_tunnel = sb.tunnels()[8001]
    print(f"\n🚀 Creating HTTP Server with tunnel!")
    print(f"🌐 Public URL: {main_tunnel.url}")
    print(f"🔒 TLS Socket: {main_tunnel.tls_socket}")
    print("\n📡 Available endpoints:")
    print(f"  POST {main_tunnel.url}/edit - Update display text")
    print(f"  GET  {main_tunnel.url}/heartbeat - Health check")
    print(f"\n💡 You can now access these endpoints from anywhere on the internet!")

    print()
    print(f"🌐 Frontend URL: {user_tunnel.url} <-- Open this in your browser!")
    print(f"🔒 TLS Socket: {user_tunnel.tls_socket}")

    print()
    print(f"🚀 FastAPI Backend URL: {backend_tunnel.url}")
    print(f"🔒 TLS Socket: {backend_tunnel.tls_socket}")
    print("📡 Available backend endpoints:")
    print(f"  GET  {backend_tunnel.url}/ - Hello World endpoint")

    print("Sandbox server with tunnel running")
    return main_tunnel.url, user_tunnel.url, backend_tunnel.url


if __name__ == "__main__":
    app = modal.App("modal-vibe-sandbox-server")
    with modal.enable_output():
        run_sandbox_server_with_tunnel.remote(app)
