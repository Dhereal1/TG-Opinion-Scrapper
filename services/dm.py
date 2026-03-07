"""
services/dm.py
==============
Admin DM delivery helper.
"""

import logging

from telegram.error import Forbidden, BadRequest
from telegram.ext import ContextTypes

from core.config import ADMIN_CHAT_IDS

logger = logging.getLogger(__name__)


async def dm_admins(context: ContextTypes.DEFAULT_TYPE, text: str) -> tuple[int, list[str]]:
    """
    Send a private DM to all configured admins and return (success_count, failures).
    """
    ok = 0
    failures: list[str] = []
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                disable_web_page_preview=True,
            )
            ok += 1
        except Forbidden as e:
            reason = "bot cannot DM this user yet (admin must open bot and press Start)"
            logger.error("Failed to DM admin %s: %s (%s)", admin_id, e, reason)
            failures.append(f"{admin_id}: {reason}")
        except BadRequest as e:
            logger.error("Failed to DM admin %s: %s", admin_id, e)
            failures.append(f"{admin_id}: bad request ({e})")
        except Exception as e:
            logger.error("Failed to DM admin %s: %s", admin_id, e)
            failures.append(f"{admin_id}: {e}")
    return ok, failures
