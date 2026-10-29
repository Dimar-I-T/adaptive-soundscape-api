from pydantic import BaseModel

class SoundStore(BaseModel):
    title: str
    sound_type: str
    analysis: str
    r2_audio_url: str