import re
import asyncio
from datetime import datetime
from pytz import UTC

from config import logger
from db.auth import set_state, get_state

# ───────────────────────── helpers ─────────────────────────
PHONE_RE = re.compile(r"^\+\d{10,15}$")

def validate_phone(phone: str) -> bool:
    """
    Return True if `phone` matches +<countrycode><number>,
    with 10–15 digits after the '+'.
    """
    return bool(PHONE_RE.match(phone))


async def code_callback(user_id: int, msg):
    """
    Called by Telethon when it needs your login code.
    Preserves the existing `data` (your phone),
    switches `state` to 'login_code', and waits up to 2 minutes.
    Returns the code string, or raises TimeoutError if you never reply.
    """
    # ── Preserve any existing data (so phone stays in state["data"]) ──
    current = await get_state(user_id)
    preserved = current["data"] if current and current.get("data") else {}

    # Move to the code‐entry step
    await set_state(user_id, "login_code", preserved)

    # Prompt the user
    await msg.answer(
        "🔑 Telegram sent you a verification code.\n"
        "Please send the code (e.g., 'code123456' or just '123456') within 2 minutes:"
    )

    timeout = 120  # seconds
    start_time = datetime.now(UTC)

    while (datetime.now(UTC) - start_time).total_seconds() < timeout:
        current_state = await get_state(user_id)

        # If they /cancel or timeout elsewhere, abort
        if current_state is None:
            raise TimeoutError("State vanished")

        data = current_state.get("data") or {}
        if current_state["step"] == "login_code" and data.get("code"):
            return data["code"]

        await asyncio.sleep(1)

    # Timed-out: clear state and inform
    await set_state(user_id, None)
    await msg.answer("⏳ Login timed out. Please start again with /login.")
    raise TimeoutError("Code input timed out")
