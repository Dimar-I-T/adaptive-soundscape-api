
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

class DB_Pool:
    def __init__(self):
        self.pool = None

    async def connect_db(self, database_url: str | None = None):
        if self.pool is None:
            database_url = database_url or os.getenv("DATABASE_URL")
            self.pool = await asyncpg.create_pool(database_url)

    async def close_db(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, *args)
            return [dict(r) for r in records]

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, *args)
            return dict(record) if record else None
