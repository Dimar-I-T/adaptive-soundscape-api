from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.db import connect_db, close_db
from routes import auth_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    print("Database connected")
    yield
    await close_db

app = FastAPI(lifespan=lifespan)

app.include_router(auth_routes.router, prefix="/api")

@app.get("/")
def root():
    return "Halo, ini project adaptive soundscape :)"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=4242, reload=True)