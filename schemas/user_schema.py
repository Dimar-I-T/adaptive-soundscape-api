from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserPublic(BaseModel):
    sub: str
    username: str
    sound_preference_default: str

class SoundPreference(BaseModel):
    sound_preference_default: str