from telethon import TelegramClient
from config import api_id, api_hash, logger
import os
from typing import Optional
import asyncio

# A global lock to ensure only one Telethon operation uses the session at a time
session_lock = asyncio.Lock()

userbot: Optional[TelegramClient] = None
userbot_authenticated: bool = False

async def initialize_userbot():
    global userbot, userbot_authenticated
    session_path = os.path.join("/app/data", "userbot")
    if os.path.exists(session_path + ".session"):
        try:
            with open(session_path + ".session", "rb") as f:
                pass
        except IOError as e:
            logger.error(f"Session file {session_path}.session is locked or corrupted: {e}")
            session_path = os.path.join("/app/data", f"userbot_{datetime.now().strftime('%Y%m%d%H%M%S')}")
            logger.info(f"Using new session file: {session_path}")
    
    userbot = TelegramClient(session_path, api_id, api_hash)
    
    try:
        await userbot.connect()
        userbot_authenticated = await userbot.is_user_authorized()
        if userbot_authenticated:
            logger.info("Userbot session loaded successfully.")
        else:
            logger.info("No existing userbot session. Use /login to authenticate.")
    except Exception as e:
        logger.error(f"Error initializing userbot: {e}")
        raise

async def shutdown_userbot():
    global userbot
    if userbot and userbot.is_connected():
        try:
            await userbot.disconnect()
            logger.info("Userbot session closed successfully.")
        except Exception as e:
            logger.error(f"Error closing userbot session: {e}")
