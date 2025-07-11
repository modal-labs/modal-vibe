from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import uuid

# Create FastAPI instance
app = FastAPI(
    title="Dummy FastAPI App",
    description="A simple FastAPI application with basic routes",
    version="1.0.0"
)

# Pydantic models for request/response
class User(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime

class UserCreate(BaseModel):
    name: str
    email: str

class Message(BaseModel):
    text: str
    timestamp: datetime = datetime.now()

# In-memory storage (for demo purposes)
users_db = {}
messages_db = []

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to the Dummy FastAPI App!", "version": "1.0.0"}

@app.get("/hello")
async def hello():
    """Simple hello endpoint"""
    return {"message": "Hello, World!"}

@app.get("/hello/{name}")
async def hello_name(name: str):
    """Hello endpoint with name parameter"""
    return {"message": f"Hello, {name}!"}

@app.get("/status")
async def get_status():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "users_count": len(users_db),
        "messages_count": len(messages_db)
    }

@app.post("/users", response_model=User)
async def create_user(user: UserCreate):
    """Create a new user"""
    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        name=user.name,
        email=user.email,
        created_at=datetime.now()
    )
    users_db[user_id] = new_user
    return new_user

@app.get("/users", response_model=List[User])
async def get_users():
    """Get all users"""
    return list(users_db.values())

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Get a specific user"""
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    """Delete a user"""
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[user_id]
    return {"message": f"User {user_id} deleted successfully"}

@app.post("/messages")
async def create_message(message: Message):
    """Create a new message"""
    messages_db.append(message)
    return {"message": "Message created successfully", "id": len(messages_db) - 1}

@app.get("/messages")
async def get_messages():
    """Get all messages"""
    return messages_db

@app.get("/info")
async def get_app_info():
    """Get application information"""
    return {
        "app_name": "Dummy FastAPI App",
        "version": "1.0.0",
        "description": "A simple FastAPI application with basic CRUD operations",
        "endpoints": {
            "GET /": "Root endpoint",
            "GET /hello": "Simple hello endpoint",
            "GET /hello/{name}": "Hello with name parameter",
            "GET /status": "Health check",
            "POST /users": "Create user",
            "GET /users": "Get all users",
            "GET /users/{user_id}": "Get specific user",
            "DELETE /users/{user_id}": "Delete user",
            "POST /messages": "Create message",
            "GET /messages": "Get all messages",
            "GET /info": "App information"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 