from fastapi import UploadFile, File, Form
from pydantic import BaseModel

class SoundStore(BaseModel):
    title: str
    sound_type: str
    analysis: str
    r2_key: str

class SoundAnalyze(BaseModel):
    file: UploadFile = File(...)
    sound: str = Form("default")        
    texture_mix: float = Form(0.8)      
    whiten: float = Form(1.0)