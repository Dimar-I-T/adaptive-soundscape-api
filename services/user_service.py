from config.db import fetch

async def get_user(id: str):
    query = """
        select username, sound_preference_default
        from users
        where id = $1
    """

    return await fetch(query, id)

async def update_sound_preference_default_serv(id: str, sound_preference: str):
    query = """
        update users
        set sound_preference_default = $1
        where id = $2
    """

    return await fetch(query, sound_preference, id)