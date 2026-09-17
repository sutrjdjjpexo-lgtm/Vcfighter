import asyncio
import logging
import os

from pytgcalls import PyTgCalls

from relay import state

log = logging.getLogger(__name__)


class VCBridge:
    """Manage multiple Telegram voice chats with one PyTgCalls client."""

    def __init__(self, app):
        # Keep the original Pyrogram client separately. PyTgCalls does not
        # expose it as `.app` in the installed API version.
        self.app = app
        self.calls = PyTgCalls(app)
        self._started = False
        self._fight_task = None
        self._lock = asyncio.Lock()

    async def _ensure_started(self):
        if not self._started:
            await self.calls.start()
            self._started = True

    @staticmethod
    async def _duration(path: str) -> float:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await proc.communicate()
            value = float(out.decode().strip())
            if value > 0:
                return value
        except Exception:
            log.exception("Unable to detect audio duration")
        return 30.0

    async def join(self, chat_id: int):
        """Join a VC with no audible media. PyTgCalls accepts stream=None."""
        async with self._lock:
            await self._ensure_started()
            await self.calls.play(chat_id, None)
            state.joined_chat_ids.add(chat_id)
            state.current_chat_id = chat_id
            state.target_chat_id = chat_id
            return chat_id

    async def join_all(self):
        return await self.join_all_from_dialogs()

    async def join_all_from_dialogs(self):
        """Scan the session account's joined group dialogs and try each active VC."""
        async with self._lock:
            await self._ensure_started()
            ok, failed = [], []
            async for dialog in self.app.get_dialogs():
                chat = dialog.chat
                if not chat or chat.type not in ("group", "supergroup"):
                    continue
                chat_id = chat.id
                try:
                    await self.calls.play(chat_id, None)
                    state.joined_chat_ids.add(chat_id)
                    ok.append(chat_id)
                except Exception as exc:
                    failed.append((chat_id, exc))
                    log.warning("Skipping VC %s: %s", chat_id, exc)
            if ok:
                state.current_chat_id = ok[-1]
                state.target_chat_id = ok[-1]
            return ok, failed

    async def remove_and_leave(self, chat_id: int):
        async with self._lock:
            await self._stop_fight_for_chat_unlocked(chat_id)
            state.joined_chat_ids.discard(chat_id)
            try:
                await self.calls.leave_call(chat_id)
            except Exception:
                log.exception("Failed to leave VC %s", chat_id)
            if state.current_chat_id == chat_id:
                state.current_chat_id = next(iter(state.joined_chat_ids), None)
                state.target_chat_id = state.current_chat_id

    async def leave_all(self):
        async with self._lock:
            await self._cancel_fight_unlocked()
            ids = list(state.joined_chat_ids)
            left, failed = [], []
            for chat_id in ids:
                try:
                    await self.calls.leave_call(chat_id)
                    left.append(chat_id)
                except Exception as exc:
                    failed.append((chat_id, exc))
                    log.exception("Failed to leave VC %s", chat_id)
            state.joined_chat_ids.clear()
            state.current_chat_id = None
            state.target_chat_id = None
            state.fight_file = None
            state.fight_running = False
            return left, failed

    async def fight(self, path: str, chat_id: int | None = None):
        async with self._lock:
            target = chat_id or state.current_chat_id
            if not target:
                raise RuntimeError("No VC selected. Use /join <group_id> first.")
            if target not in state.joined_chat_ids:
                raise RuntimeError("That group is not currently joined. Use /join or /allvc join first.")
            if not os.path.exists(path):
                raise FileNotFoundError(path)

            await self._ensure_started()
            await self._cancel_fight_unlocked()
            state.current_chat_id = target
            state.target_chat_id = target
            state.fight_file = path
            state.fight_running = True
            self._fight_task = asyncio.create_task(self._fight_loop(target, path))

    async def _fight_loop(self, target: int, path: str):
        try:
            while state.fight_running and state.current_chat_id == target:
                if not os.path.exists(path):
                    raise FileNotFoundError(path)
                duration = await self._duration(path)
                await self.calls.play(target, path)
                await asyncio.sleep(max(1.0, duration - 0.25))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Fight playback failed")
            state.fight_running = False
        finally:
            if not state.fight_running:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass

    async def _stop_fight_for_chat_unlocked(self, chat_id: int):
        if state.current_chat_id == chat_id:
            await self._cancel_fight_unlocked()
            state.fight_file = None

    async def _cancel_fight_unlocked(self):
        state.fight_running = False
        task = self._fight_task
        self._fight_task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def stop_fight(self):
        async with self._lock:
            await self._cancel_fight_unlocked()
            state.fight_file = None

    async def leave(self, chat_id: int | None = None):
        target = chat_id or state.current_chat_id
        if target is None:
            return
        await self.remove_and_leave(target)

    async def status(self):
        return {
            "target": state.current_chat_id,
            "joined": sorted(state.joined_chat_ids),
            "fight": bool(state.fight_running),
            "file": state.fight_file,
        }
