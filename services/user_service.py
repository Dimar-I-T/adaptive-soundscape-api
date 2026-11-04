from config.db import DB_Pool

async def get_user(db: DB_Pool, id: str):
    query = """
        select username, sound_preference_default
        from users
        where id = $1
    """

    return await db.fetch(query, id)

async def update_sound_preference_default_serv(db: DB_Pool, id: str, sound_preference: str):
    query = """
        update users
        set sound_preference_default = $1
        where id = $2
    """

    return await db.fetch(query, sound_preference, id)