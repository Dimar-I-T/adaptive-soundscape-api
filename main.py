import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.db import connect_db, close_db
from routes import auth_routes
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

raw_client_url = os.getenv("CLIENT_URL", "http://localhost:3000")

origins = [url.strip() for url in raw_client_url.split(",") if url.strip()]

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    print("Database connected")
    yield
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

@app.get("/")
def root():
    return "Halo, ini project adaptive soundscape :)"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=4242, reload=True)