import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.db import DB_Pool
from config.s3 import s3_client, BUCKET_NAME
from routes import auth_routes, sound_routes, user_routes
from services.sample_cache import SampleStore
from services.sound_service import register_samples
from utils.exceptions import AppError

load_dotenv()

def create_app(
    database_url: str | None = None,
    load_samples: bool = True
):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if load_samples:
            store = SampleStore(s3_client, BUCKET_NAME)
            report = await asyncio.to_thread(store.load_all)
            register_samples(store)
            app.state.samples = store
            print("Samples:", report)

        pool = DB_Pool()
        await pool.connect_db(database_url)
        app.state.db = pool

        print("Database connected")

        try:
            yield
        finally:
            await pool.close_db()

    app = FastAPI(lifespan=lifespan)

    raw_client_url = os.getenv(
        "CLIENT_URL",
        "http://localhost:3000"
    )
    origins = [
        url.strip()
        for url in raw_client_url.split(",")
        if url.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(sound_routes.router, prefix="/api")
    app.include_router(user_routes.router, prefix="/api")

    @app.exception_handler(AppError)
    async def app_error_handler(req: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message
            }
        )

    @app.get("/")
    def root():
        return "Halo, ini project adaptive soundscape :)"

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=4242,
        reload=True
    )