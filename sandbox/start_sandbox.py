import modal

SANDBOX_TIMEOUT = 86400  # 24 hours

async def run_sandbox_server_with_tunnel(app: modal.App, image: modal.Image):
    """Create and run a sandbox with an HTTP server exposed via tunnel"""
    print("🚀 Creating sandbox...")
    sb = await modal.Sandbox.create.aio(
        "/bin/bash",
        "/root/startup.sh",
        image=image,
        app=app,
        timeout=SANDBOX_TIMEOUT,
        encrypted_ports=[8000, 5173],
    )
    print(f"📋 Created sandbox with ID: {sb.object_id}")

    print("⏳ Waiting for tunnels to establish...")    
    tunnels = await sb.tunnels.aio()
    main_tunnel = tunnels[8000]
    user_tunnel = tunnels[5173]
    print("\n🚀 Creating HTTP Server with tunnel!")
    print(f"🌐 Public URL: {main_tunnel.url}")
    print(f"🔒 TLS Socket: {main_tunnel.tls_socket}")
    print("\n📡 Available endpoints:")
    print(f"  POST {main_tunnel.url}/edit - Update display text")
    print(f"  GET  {main_tunnel.url}/heartbeat - Health check")
    print("\n💡 You can now access these endpoints from anywhere on the internet!")

    print()
    print(f"🌐 Frontend URL: {user_tunnel.url} <-- Open this in your browser!")
    print(f"🔒 TLS Socket: {user_tunnel.tls_socket}")

    print("Sandbox server with tunnel running")
    return main_tunnel.url, user_tunnel.url, sb.object_id
