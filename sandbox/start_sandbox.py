"""TODO: useless now, remove?"""

import modal
import threading

SANDBOX_TIMEOUT = 86400  # 24 hours


sandbox_image = (
    modal.Image.from_registry("node:22-slim")
    # LUCY: This is the old pnpm install node and nvm
    # .apt_install("curl")
    # .run_commands(
    #     'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm install 22 && nvm use node',
    #     "curl -fsSL https://get.pnpm.io/install.sh | SHELL=/bin/bash sh -",
    # )
    # .env({"PATH": "/root/.local/share/pnpm:/root/.nvm/versions/node/v22.0.0/bin:$PATH"})
    .pip_install(
        "fastapi[standard]",
    )
    .add_local_dir("sandbox", "/root/sandbox")
    .add_local_dir("web/vite-app", "/root/vite-app")
    .add_local_file("sandbox/server.py", "/root/server.py")
)


# LUCY: this was from your old code that you sent for threading, prob can be deleted
def run_frontend_server(sb: modal.Sandbox):
    print("Running frontend server")
    try:
        server_process = sb.exec()
        print(server_process)
        print(server_process.stdout)
        print(server_process.stderr)
        for line in server_process.stdout:
            print(f"[SERVER] {line.rstrip()}")
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server and closing tunnel...")
    finally:
        print("✅ Frontend server terminated and tunnel closed")


def run_sandbox_server_with_tunnel(app: modal.App):
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    with open("/root/sandbox/server.py", "r") as f:
        server_script = f.read()

    # LUCY: trying to debug this
    sb = modal.Sandbox.create(
        # "python",
        # "/root/server.py",
        # &&
        "pnpm",
        "--prefix",
        "/root/vite-app",
        "run",
        "dev",
        image=sandbox_image,
        app=app,
        timeout=SANDBOX_TIMEOUT,
        encrypted_ports=[8000, 5173],
    )
    print(f"📋 Created sandbox with ID: {sb.object_id}")

    main_tunnel = sb.tunnels()[8000]
    user_tunnel = sb.tunnels()[5173]
    print(f"\n🚀 Creating HTTP Server with tunnel!")
    print(f"🌐 Public URL: {main_tunnel.url}")
    print(f"🔒 TLS Socket: {main_tunnel.tls_socket}")
    print("\n📡 Available endpoints:")
    print(f"  POST {main_tunnel.url}/edit - Update display text")
    print(f"  GET  {main_tunnel.url}/heartbeat - Health check")
    print(f"  GET  {main_tunnel.url}/display - View current text")
    print(f"\n💡 You can now access these endpoints from anywhere on the internet!")

    print()
    print(f"🌐 User URL: {user_tunnel.url}")
    print(f"🔒 TLS Socket: {user_tunnel.tls_socket}")

    # LUCY: this was from your old code that you sent for threading, prob can be deleted
    # threading.Thread(target=run_frontend_server, args=(sb,)).start()
    # run_frontend_server(sb)

    print("Sandbox server with tunnel running")
    return main_tunnel.url, user_tunnel.url


if __name__ == "__main__":
    app = modal.App("modal-vibe-sandbox-server")
    with modal.enable_output():
        run_sandbox_server_with_tunnel.remote(app)
