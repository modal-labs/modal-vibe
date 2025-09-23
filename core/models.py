"""Core models for the sandbox app."""

from enum import Enum
import json
from pydantic import BaseModel
from datetime import datetime


class DateTimeEncoder(json.JSONEncoder):
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"

    def __str__(self):
        return self.value
    
    def __json__(self):
        return self.value

class Message(BaseModel):
    content: str
    type: MessageType
    
    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        data['type'] = self.type.value
        return data

class AppStatus(Enum):
    CREATED = "created" # The sandbox is created but hasn't reported back to the server yet.
    READY = "ready"     # The sandbox is alive but the initial app is not generated yet.
    ACTIVE = "active"   # The sandbox is alive and the initial app is generated.
    TERMINATED = "terminated" # The sandbox is terminated either by the user or from timeout.
    
    def __json__(self):
        return self.value

class AppMetadata(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    status: AppStatus
    sandbox_user_tunnel_url: str
    title: str = ""
    is_featured: bool = False 
    
    def model_dump(self, **kwargs):
        """Override model_dump to handle AppStatus enum serialization"""
        data = super().model_dump(**kwargs)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['sandbox_user_tunnel_url'] = self.sandbox_user_tunnel_url
        data['title'] = self.title
        data['is_featured'] = self.is_featured
        return data

class AppData(BaseModel):
    id: str
    message_history: list[Message]
    current_component: str
    sandbox_tunnel_url: str
    sandbox_user_tunnel_url: str
    sandbox_object_id: str
    
    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        data['message_history'] = [msg.model_dump() for msg in self.message_history]
        return data
