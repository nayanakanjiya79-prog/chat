from pydantic import BaseModel
from typing import Optional


class Message(BaseModel):
    sender: str
    message: str
    timestamp: Optional[str] = None


class User(BaseModel):
    username: str


class JoinRequest(BaseModel):
    username: str


class SystemMessage(BaseModel):
    type: str
    message: str
    timestamp: str
    username: Optional[str] = None


class UserListMessage(BaseModel):
    type: str
    users: list[str]