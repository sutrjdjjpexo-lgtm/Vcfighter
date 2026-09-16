import asyncio
import logging
import os
import random
import uuid

from pyrogram import filters
from pyrogram.types import Message

from relay import state
from relay.vc_bridge import VCBridge

log = logging.getLogger(__name__)
bridge = None
DOWNLOAD_DIR = "downloads"

# Automatic reactions: one reaction for the latest message from each active user
# after one hour. The interval can be changed with REACTION_INTERVAL (seconds).
REACTION_INTERVAL = max(60, int(os.getenv("REACTION_INTERVAL", "3600")))
REACTION_EMOJIS = ["🌚", "😂", "😅", "😭", "😘", "♥️"]
_reaction_tasks = {}
_reaction_lock = asyncio.Lock()
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _allowed():
    # This project uses a Pyrogram user session. Accept commands sent to the
    # account from other chats AND commands typed by the session account itself.
    return (filters.private | filters.group) & (filters.incoming | filters.outgoing)


def _help_text():
    return (
        "🎙️ **VC Fighter**\n\n"
        "`/join -1001234567890` — group ko saved list me add karke uske VC me join\n"
        "`/allvc join` — saved **sabhi groups** ke VC ek saath join (no audio)\n"
        "`/allvc leave` — sabhi joined VCs se ek saath leave\n"
        "`/leave -1001234567890` — ek specific VC leave\n"
        "`/fight` — replied audio ko selected VC me repeat play\n"
        "`/fightstop` — fight audio stop\n"
        "`/status` — joined VCs/status\n"
        "`/ping` — online check\n"
        "`/reaction on` / `/reaction off` — automatic reactions\n\n"
        "**Flow:** `/join <group_id>` → `/allvc join` → audio reply + `/fight`"
    )


def _is_audio(msg: Message) -> bool:
    return bool(msg and (msg.audio or msg.voice))



async def _reaction_worker(message):
    key = (message.chat.id, message.from_user.id if message.from_user else 0)
    try:
        await asyncio.sleep(REACTION_INTERVAL)

        # React only in groups registered through /join and while the feature is ON.
        if not getattr(state, "reactions_enabled", True):
            return
        if message.chat.id not in state.joined_chat_ids:
            return

        emoji = random.choice(REACTION_EMOJIS)
        await message.react(emoji=emoji)
        log.info(
            "Automatic reaction sent: chat=%s message=%s emoji=%s",
            message.chat.id, message.id, emoji
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning(
            "Automatic reaction failed for chat=%s message=%s: %s",
            getattr(message.chat, "id", None),
            getattr(message, "id", None),
            exc,
        )
    finally:
        async with _reaction_lock:
            if _reaction_tasks.get(key) is asyncio.current_task():
                _reaction_tasks.pop(key, None)


async def _schedule_reaction(message):
    if not getattr(state, "reactions_enabled", True):
        return
    if not message.chat or message.chat.id not in state.joined_chat_ids:
        return
    if not message.from_user or message.from_user.is_bot:
        return
    if getattr(message, "outgoing", False):
        return
    if message.text and message.text.startswith("/"):
        return

    key = (message.chat.id, message.from_user.id)
    async with _reaction_lock:
        old = _reaction_tasks.get(key)
        if old and not old.done():
            old.cancel()
        _reaction_tasks[key] = asyncio.create_task(_reaction_worker(message))


def _cancel_all_reactions():
    for task in list(_reaction_tasks.values()):
        if task and not task.done():
            task.cancel()
    _reaction_tasks.clear()


def register(app):
    global bridge
    bridge = VCBridge(app)
    allowed = _allowed()

    @app.on_message(
        (filters.command(["help", "commands", "menu", "h"]) |
         filters.regex(r"^/(?:help|commands|menu|h)(?:@[A-Za-z0-9_]+)?(?:\s|$)")) & allowed
    )
    async def help_cmd(_, message):
        await message.reply_text(_help_text())

    @app.on_message(filters.command("ping") & allowed)
    async def ping(_, message):
        await message.reply_text("🏓 Pong — VC Fighter is online.")

    @app.on_message(filters.command("join") & allowed)
    async def join_cmd(_, message):
        if len(message.command) < 2:
            return await message.reply_text("Usage: `/join <group_id>`")
        try:
            target = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Group ID must be a number.")

        status = await message.reply_text("⏳ VC join kar raha hoon…")
        try:
            await bridge.join(target)
            await status.edit_text(
                f"✅ **VC joined**\nGroup: `{target}`\n"
                f"Saved VCs: `{len(state.joined_chat_ids)}`\n\n"
                "No audio started. `/allvc join` se sab saved VCs join kar sakte ho."
            )
        except Exception as exc:
            log.exception("VC join failed")
            await status.edit_text(
                f"❌ **VC join failed**\n`{type(exc).__name__}: {exc}`"
            )

    @app.on_message(filters.command("allvc") & allowed)
    async def allvc_cmd(_, message):
        if len(message.command) < 2 or message.command[1].lower() not in {"join", "leave"}:
            return await message.reply_text(
                "Usage:\n`/allvc join` — sab saved groups ke VC join\n"
                "`/allvc leave` — sabhi VC leave"
            )

        action = message.command[1].lower()
        status = await message.reply_text(
            "⏳ Sabhi saved VCs join kar raha hoon…" if action == "join"
            else "⏳ Sabhi VCs se leave kar raha hoon…"
        )
        try:
            if action == "join":
                ok, failed = await bridge.join_all()
                text = f"✅ **ALL VC JOIN DONE**\nJoined: `{len(ok)}`\nFailed: `{len(failed)}`\n\nNo audio started."
                if failed:
                    text += "\n\nFailed IDs: " + ", ".join(f"`{x[0]}`" for x in failed[:10])
            else:
                left, failed = await bridge.leave_all()
                text = f"🚪 **ALL VC LEAVE DONE**\nLeft: `{len(left)}`\nFailed: `{len(failed)}`"
                if failed:
                    text += "\n\nFailed IDs: " + ", ".join(f"`{x[0]}`" for x in failed[:10])
            await status.edit_text(text)
        except Exception as exc:
            log.exception("allvc failed")
            await status.edit_text(f"❌ **ALL VC failed**\n`{type(exc).__name__}: {exc}`")

    @app.on_message(filters.command("fight") & allowed)
    async def fight_cmd(_, message):
        if not state.current_chat_id:
            return await message.reply_text("❌ Pehle `/join <group_id>` karo.")
        replied = message.reply_to_message
        if not _is_audio(replied):
            return await message.reply_text("❌ `/fight` ko audio/voice message ke reply me bhejo.")

        status = await message.reply_text("⬇️ Audio download ho raha hai…")
        path = None
        try:
            ext = ".ogg" if replied.voice else ".mp3"
            path = os.path.join(DOWNLOAD_DIR, f"fight_{uuid.uuid4().hex}{ext}")
            await replied.download(file_name=path)
            target = state.current_chat_id
            await bridge.fight(path, target)
            await status.edit_text(
                f"🔥 **FIGHT started**\nVC: `{target}`\n\n"
                "Audio repeat me play hoga. `/fightstop` se stop karo."
            )
        except Exception as exc:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            log.exception("Fight playback failed")
            await status.edit_text(f"❌ **Fight failed**\n`{type(exc).__name__}: {exc}`")

    @app.on_message(filters.command("fightstop") & allowed)
    async def fightstop_cmd(_, message):
        try:
            await bridge.stop_fight()
            await message.reply_text("🛑 Fight audio stopped. VC me bot bana hua hai.")
        except Exception as exc:
            await message.reply_text(f"❌ Stop failed: `{type(exc).__name__}: {exc}`")

    @app.on_message(filters.command("leave") & allowed)
    async def leave_cmd(_, message):
        target = None
        if len(message.command) >= 2:
            try:
                target = int(message.command[1])
            except ValueError:
                return await message.reply_text("❌ Group ID must be a number.")
        try:
            await bridge.leave(target)
            if target is None:
                await message.reply_text("🚪 Current VC left.")
            else:
                await message.reply_text(f"🚪 VC left: `{target}`")
        except Exception as exc:
            await message.reply_text(f"❌ Leave failed: `{type(exc).__name__}: {exc}`")


    @app.on_message(filters.command("reaction") & allowed)
    async def reaction_cmd(_, message):
        if len(message.command) < 2 or message.command[1].lower() not in {"on", "off"}:
            return await message.reply_text(
                "Usage:\n"
                "`/reaction on` — automatic reactions ON\n"
                "`/reaction off` — automatic reactions OFF"
            )

        action = message.command[1].lower()
        state.reactions_enabled = action == "on"

        if state.reactions_enabled:
            await message.reply_text(
                f"🔔 Automatic reactions ON.\n"
                f"Latest messages from active group users can receive a reaction "
                f"after {REACTION_INTERVAL // 60} minutes."
            )
        else:
            _cancel_all_reactions()
            await message.reply_text("🔕 Automatic reactions OFF.")

    # Dynamic handler: reacts only in groups that were registered with /join.
    @app.on_message(filters.incoming)
    async def automatic_reaction_handler(_, message):
        await _schedule_reaction(message)

    @app.on_message(filters.command("status") & allowed)
    async def status_cmd(_, message):
        s = await bridge.status()
        joined = s["joined"]
        joined_text = "\n".join(f"• `{x}`" for x in joined[:50]) if joined else "• None"
        more = f"\n…and {len(joined)-50} more" if len(joined) > 50 else ""
        await message.reply_text(
            "📊 **VC Fighter Status**\n\n"
            f"Current VC: `{s['target']}`\n"
            f"Saved/Joined groups: `{len(joined)}`\n"
            f"Fight: {'🟢 Playing' if s['fight'] else '🔴 Stopped'}\n\n"
            f"{joined_text}{more}"
        )
