#!/bin/bash
set -e

echo "🚀 Starting sandbox services..."

# Start FastAPI server in background with logs
echo "📦 Starting FastAPI server..."
python /root/server.py > /tmp/fastapi.log 2>&1 &
FASTAPI_PID=$!
echo "FastAPI started with PID: $FASTAPI_PID"

# Start Vite dev server in background with logs
echo "⚡ Starting Vite dev server..."
cd /root/vite-app
# Try pnpm with explicit command
pnpm exec vite --host 0.0.0.0 --port 5173 > /tmp/vite.log 2>&1 &
VITE_PID=$!
echo "Vite started with PID: $VITE_PID"

# Give services a moment to start
sleep 3

# Check if processes are still running
echo "Checking if services are running..."
if ps -p $FASTAPI_PID > /dev/null; then
    echo "✅ FastAPI process is running"
else
    echo "❌ FastAPI process died! Log:"
    cat /tmp/fastapi.log
    exit 1
fi

if ps -p $VITE_PID > /dev/null; then
    echo "✅ Vite process is running"
else
    echo "❌ Vite process died! Log:"
    cat /tmp/vite.log
    exit 1
fi

# Simple health check - just see if ports are open
echo "⏳ Waiting for services to be ready..."
for i in {1..30}; do
    # Check FastAPI
    if curl -s http://localhost:8000/heartbeat > /dev/null 2>&1; then
        echo "✅ FastAPI is ready!"
        FASTAPI_READY=true
    fi
    
    # Check Vite
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo "✅ Vite is ready!"
        VITE_READY=true
    fi
    
    # Both ready?
    if [ "$FASTAPI_READY" = "true" ] && [ "$VITE_READY" = "true" ]; then
        echo "🎉 All services started successfully!"
        break
    fi
    
    if [ $i -eq 30 ]; then
        echo "❌ Services failed to start after 30 attempts"
        echo "FastAPI log:"
        cat /tmp/fastapi.log
        echo "Vite log:"
        cat /tmp/vite.log
        exit 1
    fi
    
    echo "Attempt $i/30: Waiting for services..."
    sleep 2
done

# Keep the script running
echo "Services are running. Keeping container alive..."
wait $FASTAPI_PID $VITE_PID
