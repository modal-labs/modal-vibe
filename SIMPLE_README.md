# Simple FastAPI App

A dummy FastAPI application with basic routes including the requested "hello" endpoint.

## Features

- Basic hello routes (`/hello` and `/hello/{name}`)
- User management (CRUD operations)
- Message posting
- Health check endpoint
- Automatic API documentation

## Installation

1. Install dependencies:
```bash
pip install -r simple_requirements.txt
```

## Running the App

### Method 1: Using Python directly
```bash
python simple_app.py
```

### Method 2: Using Uvicorn
```bash
uvicorn simple_app:app --reload
```

The app will start at `http://localhost:8000`

## Available Endpoints

- **GET /** - Root endpoint
- **GET /hello** - Simple hello endpoint
- **GET /hello/{name}** - Hello with name parameter
- **GET /status** - Health check
- **GET /info** - Application information
- **POST /users** - Create a new user
- **GET /users** - Get all users
- **GET /users/{user_id}** - Get specific user
- **DELETE /users/{user_id}** - Delete user
- **POST /messages** - Create a message
- **GET /messages** - Get all messages

## API Documentation

Once running, you can access:
- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc

## Example Usage

### Test the hello endpoint:
```bash
curl http://localhost:8000/hello
```

### Create a user:
```bash
curl -X POST "http://localhost:8000/users" \
     -H "Content-Type: application/json" \
     -d '{"name": "John Doe", "email": "john@example.com"}'
```

### Get all users:
```bash
curl http://localhost:8000/users
```

### Post a message:
```bash
curl -X POST "http://localhost:8000/messages" \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello from the API!"}'
``` 