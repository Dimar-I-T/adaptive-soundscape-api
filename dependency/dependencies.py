from fastapi import Request
from config.db import DB_Pool

def get_db(request: Request) -> DB_Pool:
    return request.app.state.db