from pyrogram import Client, errors, idle
import pyrogram.raw.types as pyrogram_raw_types

if not hasattr(pyrogram_raw_types, "InputGroupCallSlug"):
    class InputGroupCallSlug:
        def __init__(self, slug: str):
            self.slug = slug
        def __repr__(self):
            return f"InputGroupCallSlug(slug={self.slug!r})"
    pyrogram_raw_types.InputGroupCallSlug = InputGroupCallSlug

import pyrogram.errors as pyrogram_errors

if not hasattr(pyrogram_errors, "GroupcallForbidden"):
    if hasattr(pyrogram_errors, "GroupCallForbidden"):
        pyrogram_errors.GroupcallForbidden = pyrogram_errors.GroupCallForbidden
    else:
        class GroupcallForbidden(pyrogram_errors.BadRequest):
            pass
        pyrogram_errors.GroupcallForbidden = GroupcallForbidden

if not hasattr(pyrogram_errors, "GroupcallInvalid"):
    if hasattr(pyrogram_errors, "GroupCallInvalid"):
        pyrogram_errors.GroupcallInvalid = pyrogram_errors.GroupCallInvalid
    else:
        class GroupcallInvalid(pyrogram_errors.BadRequest):
            pass
        pyrogram_errors.GroupcallInvalid = GroupcallInvalid

from config import API_HASH, API_ID, CONTROL_GROUP_ID, SESSION_NAME, SESSION_STRING
from relay.commands import register

if SESSION_STRING:
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

register(app)

async def startup():
    await app.start()
    print("🔊 VC Fighter started", flush=True)
    try:
        await app.send_message(
            CONTROL_GROUP_ID,
            "🟢 **VC Fighter started**\nUse `/help` for commands.\n\nFlow: `/join <group_id>` → reply to audio → `/fight`",
        )
    except Exception as exc:
        print(f"Startup notification failed: {type(exc).__name__}: {exc}", flush=True)
    await idle()
    await app.stop()

try:
    app.run(startup())
except errors.BadRequest as exc:
    print(f"Telegram startup error: {exc}", flush=True)
    raise
