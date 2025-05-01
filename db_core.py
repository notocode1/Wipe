import logging
import asyncpg
from asyncpg.exceptions import PostgresConnectionError
from config import DATABASE_URL

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        logger.info("Database pool initialized")

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

db = Database()

async def with_retry(func, max_attempts=3, delay=1):
    for attempt in range(max_attempts):
        try:
            return await func()
        except PostgresConnectionError as e:
            if attempt == max_attempts - 1:
                raise
            logger.warning(f"DB connection error, retrying: {e}")
            await asyncio.sleep(delay * (2 ** attempt))
    raise RuntimeError("Max retries exceeded")

async def initialize_db():
    async with db.pool.acquire() as conn:
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    subscription_start TIMESTAMP,
                    subscription_end TIMESTAMP,
                    payment_method VARCHAR(50),
                    subscription_status VARCHAR(20) CHECK (subscription_status IN ('active', 'expired', 'canceled')),
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS premium_channels (
                    channel_id BIGINT PRIMARY KEY,
                    channel_name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    amount DECIMAL(10,2),
                    method VARCHAR(50),
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transaction_id VARCHAR(255)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS subscription_history (
                    history_id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    action VARCHAR(50),
                    amount DECIMAL(10,2),
                    method VARCHAR(50),
                    new_expiry TIMESTAMP,
                    change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    user_id BIGINT PRIMARY KEY,
                    step VARCHAR(255),
                    data JSONB,
                    expires TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Add indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_subscription ON users(subscription_end);
                CREATE INDEX IF NOT EXISTS idx_payment_date ON payments(payment_date);
                CREATE INDEX IF NOT EXISTS idx_history_user ON subscription_history(user_id);
            """)
            # Ensure is_admin column exists
            await conn.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
            """)
            logger.info("Database initialized")
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
