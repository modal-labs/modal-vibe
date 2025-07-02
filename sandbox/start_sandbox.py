import modal

SANDBOX_TIMEOUT = 86400  # 24 hours


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
    .add_local_dir("web/vite-app/public", "/root/vite-app/public")
    .add_local_dir("web/vite-app/src", "/root/vite-app/src")
    .add_local_file("web/vite-app/eslint.config.js", "/root/vite-app/eslint.config.js")
    .add_local_file("web/vite-app/index.html", "/root/vite-app/index.html")
    .add_local_file("web/vite-app/package.json", "/root/vite-app/package.json")
    .add_local_file("web/vite-app/tsconfig.json", "/root/vite-app/tsconfig.json")
    .add_local_file(
        "web/vite-app/tsconfig.node.json", "/root/vite-app/tsconfig.node.json"
    )
    .add_local_file(
        "web/vite-app/tsconfig.app.json", "/root/vite-app/tsconfig.app.json"
    )
    .add_local_file("web/vite-app/vite.config.ts", "/root/vite-app/vite.config.ts")
)


def run_sandbox_server_with_tunnel(app: modal.App):
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    sb = modal.Sandbox.create(
        "sh",
        "-c",
        "pnpm install --dir /root/vite-app && pnpm --prefix /root/vite-app dev --host & python /root/server.py",
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
    print(f"\n💡 You can now access these endpoints from anywhere on the internet!")

    print()
    print(f"🌐 Frontend URL: {user_tunnel.url} <-- Open this in your browser!")
    print(f"🔒 TLS Socket: {user_tunnel.tls_socket}")

    print("Sandbox server with tunnel running")
    return main_tunnel.url, user_tunnel.url


if __name__ == "__main__":
    app = modal.App("modal-vibe-sandbox-server")
    with modal.enable_output():
        run_sandbox_server_with_tunnel.remote(app)
