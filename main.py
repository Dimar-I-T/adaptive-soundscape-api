import asyncio
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from config.db import connect_db, close_db
from routes import auth_routes, sound_routes
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.s3 import s3_client, BUCKET_NAME
from services.sample_cache import SampleStore, SAMPLE_FILES
from services.sound_service import register_samples

load_dotenv()

raw_client_url = os.getenv("CLIENT_URL", "http://localhost:3000")

origins = [url.strip() for url in raw_client_url.split(",") if url.strip()]

@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SampleStore(s3_client, BUCKET_NAME)
    report = await asyncio.to_thread(store.load_all)    
    register_samples(store)
    app.state.samples = store
    print("Samples:", report)
    await connect_db()
    print("Database connected")
    try:
        yield
    finally:
        await close_db()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/api")
app.include_router(sound_routes.router, prefix="/api")

@app.get("/")
def root():
    return "Halo, ini project adaptive soundscape :)"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=4242, reload=True)