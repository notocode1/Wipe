"""commands/login.py – Aiogram 3.x compatible
Handles /login multi‑step flow without blocking other handlers.
"""

import re
import logging
from aiogram import Router, F               # <-- Router + filter helpers
from aiogram.types import Message
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
)

import auth_core as auth_core
from config import owner_id
from auth import set_state, get_state, clear_state
from auth_utils import validate_phone

# -----------------------------------------------------------------------------
router = Router()
log = logging.getLogger("VipMan.login")

# -----------------------------------------------------------------------------
# Helper filter – true only when the OWNER is currently in a login_* state
# -----------------------------------------------------------------------------
async def is_login_step(msg: Message) -> bool:
    if msg.from_user.id != owner_id:
        return False
    state = await get_state(owner_id)
    return bool(state and state.get("step", "").startswith("login_"))

# -----------------------------------------------------------------------------
# /login command (starts the flow)
# -----------------------------------------------------------------------------
@router.message(F.text.startswith("/login"), F.from_user.id == owner_id)
async def cmd_login(msg: Message):
    if auth_core.userbot is None or not auth_core.userbot.is_connected():
        await auth_core.initialize_userbot()
    if auth_core.userbot_authenticated:
        return await msg.answer("✅ Already logged in.")

    await set_state(owner_id, "login_phone", {})
    await msg.answer("📱 Send your phone number (e.g. +1234567890), or /cancel.")

# -----------------------------------------------------------------------------
# Catch non‑command messages *only* during login flow
# -----------------------------------------------------------------------------
@router.message(is_login_step)
async def login_steps(msg: Message):
    log.info("Login-step handler: %s", msg.text)

    state = await get_state(owner_id)
    step  = state["step"]
    data  = state.get("data") or {}

    # ---------------- phone ---------------
    if step == "login_phone":
        phone = msg.text.strip()
        if not validate_phone(phone):
            return await msg.answer("❌ Invalid format. Use +<country><number>.")
        try:
            await auth_core.userbot.send_code_request(phone)
        except FloodWaitError as e:
            await msg.answer(f"⚠️ Too many requests, wait {(e.seconds//60)+1}m.")
            await clear_state(owner_id)
            return
        except Exception as e:
            log.error("send_code_request failed", exc_info=e)
            await msg.answer("⚠️ Couldn’t send code. Try /login again.")
            await clear_state(owner_id)
            return

        data["phone"] = phone
        await set_state(owner_id, "login_code", data)
        return await msg.answer("🔑 Code sent! Please enter it.")

    # ---------------- code ----------------
    if step == "login_code":
        match = re.search(r"\d+", msg.text)
        if not match:
            return await msg.answer("❌ Invalid code. Digits only.")
        code  = match.group()
        phone = data.get("phone")
        if not phone:
            await clear_state(owner_id)
            return await msg.answer("⚠️ Session expired. Run /login again.")
        try:
            await auth_core.userbot.sign_in(phone, code)
        except PhoneCodeInvalidError:
            return await msg.answer("❌ Wrong code. Try again.")
        except SessionPasswordNeededError:
            await set_state(owner_id, "login_password", data)
            return await msg.answer("🔒 2FA enabled; send your password:")
        except FloodWaitError as e:
            await msg.answer(f"⚠️ Too many requests, wait {(e.seconds//60)+1}m.")
            await clear_state(owner_id)
            return
        except Exception as e:
            log.error("sign_in code failed", exc_info=e)
            await msg.answer("⚠️ Login failed. Try /login again.")
            await clear_state(owner_id)
            return

        auth_core.userbot_authenticated = True
        await clear_state(owner_id)
        return await msg.answer("✅ Logged in successfully!")

    # ------------- password ---------------
    if step == "login_password":
        pw = msg.text.strip()
        try:
            await auth_core.userbot.sign_in(password=pw)
        except SessionPasswordNeededError:
            return await msg.answer("❌ Wrong password. Try again.")
        except FloodWaitError as e:
            await msg.answer(f"⚠️ Too many requests, wait {(e.seconds//60)+1}m.")
            await clear_state(owner_id)
            return
        except Exception as e:
            log.error("sign_in password failed", exc_info=e)
            await msg.answer("⚠️ Login failed. Try /login again.")
            await clear_state(owner_id)
            return

        auth_core.userbot_authenticated = True
        await clear_state(owner_id)
        return await msg.answer("✅ Logged in with 2FA!")

# -----------------------------------------------------------------------------
# /cancel command to abort login flow
# -----------------------------------------------------------------------------
@router.message(F.text == "/cancel", F.from_user.id == owner_id)
async def cancel_login(msg: Message):
    await clear_state(owner_id)
    await msg.answer("❌ Login cancelled.")


    # ───── catch-all DB/Network errors ─────
    try:
        pass
    except PostgresError as e:
        log.error("DB error during login", exc_info=e)
        await msg.answer("❌ Database error. Contact support.")
        await set_state(owner_id, None)
    except aiohttp.ClientError as e:
        log.error("Network error during login", exc_info=e)
        await msg.answer("🌐 Network error. Please retry /login.")
        await set_state(owner_id, None)
