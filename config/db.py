import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
pool = None

async def connect_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

async def close_db():
    await pool.close()

async def fetch(query: str, *args):
    async with pool.acquire() as conn:
        records = await conn.fetch(query, *args)
        return [dict(r) for r in records]

async def fetchrow(query: str, *args):
    async with pool.acquire() as conn:
        record = await conn.fetchrow(query, *args)
        return dict(record) if record else None

