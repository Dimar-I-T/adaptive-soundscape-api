from config.db import fetch

async def get_user(id: str):
    query = """
        select username
        from users
        where id = $1
    """

    return await fetch(query, id)