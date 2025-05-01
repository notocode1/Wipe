# db/auth.py

import json
from config import logger
from db_core import db
from asyncpg.exceptions import PostgresError

async def set_state(user_id: int, step: str, data: dict = None):
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO state (user_id, step, data, updated_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET step = $2, data = $3, updated_at = CURRENT_TIMESTAMP
                """,
                user_id, step, json.dumps(data) if data else None
            )
    except PostgresError as e:
        logger.error(f"Failed to set state for user {user_id}: {e}")
        raise

async def get_state(user_id: int):
    try:
        async with db.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT step, data FROM state WHERE user_id = $1",
                user_id
            )
            if result:
                return {
                    "step": result["step"],
                    "data": json.loads(result["data"]) if result["data"] else None
                }
            return None
    except PostgresError as e:
        logger.error(f"Failed to get state for user {user_id}: {e}")
        raise

async def clear_state(user_id: int):
    """
    Delete any FSM/login state row for this user so future messages
    aren’t caught by the login_steps handler.
    """
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM state WHERE user_id = $1",
                user_id
            )
    except PostgresError as e:
        logger.error(f"Failed to clear state for user {user_id}: {e}")
        raise
