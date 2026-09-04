"""Dual Priority Queue manager for Notion Agent SGA.

High Priority: Chat Queue (FIFO, delay 3s between outgoing replies).
Low Priority: Broadcast Queue (delay 5s between broadcasts, yields to chat).
"""
import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self):
        self.chat_queue: asyncio.Queue = asyncio.Queue()
        self.active_chat_items: List[Dict[str, Any]] = []
        self.broadcast_jobs: List[Dict[str, Any]] = []

        self._active_chat_lock = asyncio.Lock()
        self._active_chat_count = 0  # in-flight / processing chat items
        self._chat_worker_task: Optional[asyncio.Task] = None
        self._broadcast_worker_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._chat_worker_task = asyncio.create_task(self._chat_worker(), name="chat_queue_worker")

    async def stop(self):
        self._running = False
        if self._chat_worker_task:
            self._chat_worker_task.cancel()
            try:
                await self._chat_worker_task
            except asyncio.CancelledError:
                pass
            self._chat_worker_task = None

    async def enqueue_chat(
        self,
        handler: Callable[[], Any],
        sender: str,
        platform: str,
        preview: str,
    ) -> str:
        item_id = str(uuid.uuid4())[:8]
        item = {
            "id": item_id,
            "sender": sender,
            "platform": platform,
            "preview": preview[:120] if preview else "",
            "status": "waiting",
            "enqueued_at": time.time(),
        }
        async with self._active_chat_lock:
            self.active_chat_items.append(item)
            self._active_chat_count += 1

        await self.chat_queue.put((item_id, handler))
        return item_id

    async def _update_chat_item_status(self, item_id: str, status: str):
        async with self._active_chat_lock:
            for it in self.active_chat_items:
                if it["id"] == item_id:
                    it["status"] = status
                    break

    async def _remove_chat_item(self, item_id: str):
        async with self._active_chat_lock:
            self.active_chat_items = [it for it in self.active_chat_items if it["id"] != item_id]
            self._active_chat_count = max(0, self._active_chat_count - 1)

    def has_active_chats(self) -> bool:
        return self._active_chat_count > 0 or not self.chat_queue.empty()

    async def _chat_worker(self):
        while self._running:
            try:
                item_id, handler = await self.chat_queue.get()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Chat worker get error: {e}")
                continue

            try:
                await self._update_chat_item_status(item_id, "processing")
                if asyncio.iscoroutinefunction(handler) or hasattr(handler, "__await__"):
                    res = handler()
                    if asyncio.iscoroutine(res):
                        await res
                else:
                    handler()
            except Exception as e:
                logger.error(f"Error processing chat item {item_id}: {e}", exc_info=True)
            finally:
                # Cooldown 3 seconds between outgoing chat replies
                await self._update_chat_item_status(item_id, "cooldown")
                await asyncio.sleep(3.0)
                await self._remove_chat_item(item_id)
                self.chat_queue.task_done()

    async def enqueue_broadcast(
        self,
        message: str,
        division: str = "all",
        platform: str = "all",
        delay_seconds: float = 5.0,
        recipients_override: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from app.services.contacts import get_all_contacts

        job_id = f"job_{uuid.uuid4().hex[:8]}"

        # Resolve target recipients
        all_contacts = await get_all_contacts()
        targets: List[Dict[str, Any]] = []

        if recipients_override and len(recipients_override) > 0:
            for r in recipients_override:
                r_clean = r.strip()
                if not r_clean:
                    continue
                matched = next(
                    (c for c in all_contacts if c.get("phone") == r_clean or (c.get("name") or "").lower() == r_clean.lower() or (c.get("nickname") or "").lower() == r_clean.lower()),
                    None,
                )
                if matched:
                    # check platform
                    plat = platform.lower()
                    if plat == "wa" or plat == "whatsapp":
                        if matched.get("phone"):
                            targets.append({"name": matched.get("name") or r_clean, "platform": "wa", "target": matched.get("phone"), "division": matched.get("division")})
                    elif plat == "telegram":
                        if matched.get("telegram"):
                            targets.append({"name": matched.get("name") or r_clean, "platform": "telegram", "target": matched.get("telegram"), "division": matched.get("division")})
                    else:
                        # both/all
                        if matched.get("phone"):
                            targets.append({"name": matched.get("name") or r_clean, "platform": "wa", "target": matched.get("phone"), "division": matched.get("division")})
                        if matched.get("telegram"):
                            targets.append({"name": matched.get("name") or r_clean, "platform": "telegram", "target": matched.get("telegram"), "division": matched.get("division")})
                else:
                    # Treat raw override as phone for WA
                    targets.append({"name": r_clean, "platform": "wa", "target": r_clean, "division": "Direct"})
        else:
            plat = platform.lower()
            for c in all_contacts:
                div = c.get("division") or ""
                if division != "all" and div.lower() != division.lower():
                    continue

                if plat in ("wa", "whatsapp"):
                    if c.get("phone"):
                        targets.append({"name": c.get("nickname") or c.get("name"), "platform": "wa", "target": c.get("phone"), "division": div})
                elif plat == "telegram":
                    if c.get("telegram"):
                        targets.append({"name": c.get("nickname") or c.get("name"), "platform": "telegram", "target": c.get("telegram"), "division": div})
                else:
                    # all/both
                    if c.get("phone"):
                        targets.append({"name": c.get("nickname") or c.get("name"), "platform": "wa", "target": c.get("phone"), "division": div})
                    if c.get("telegram"):
                        targets.append({"name": c.get("nickname") or c.get("name"), "platform": "telegram", "target": c.get("telegram"), "division": div})

        job = {
            "id": job_id,
            "message": message,
            "division": division,
            "platform": platform,
            "delay_seconds": float(delay_seconds) if delay_seconds > 0 else 5.0,
            "total": len(targets),
            "sent": 0,
            "failed": 0,
            "current_recipient": None,
            "status": "running" if targets else "completed",
            "created_at": time.time(),
            "_cancel_requested": False,
            "_targets": targets,
        }

        self.broadcast_jobs.append(job)

        if targets:
            asyncio.create_task(self._run_broadcast_job(job))

        return self._format_broadcast_job(job)

    def cancel_broadcast(self, job_id: Optional[str] = None) -> bool:
        cancelled = False
        for job in self.broadcast_jobs:
            if job["status"] in ("running", "yielding"):
                if job_id is None or job["id"] == job_id:
                    job["_cancel_requested"] = True
                    job["status"] = "cancelled"
                    cancelled = True
        return cancelled

    async def _run_broadcast_job(self, job: Dict[str, Any]):
        from app.wa.sender import send_direct_message
        from app.telegram.bot import send_telegram_message

        targets = job.get("_targets", [])
        delay = job.get("delay_seconds", 5.0)

        for target_info in targets:
            if job.get("_cancel_requested"):
                job["status"] = "cancelled"
                break

            # Yield to chat queue if any chat is queued or processing
            while self.has_active_chats():
                if job.get("_cancel_requested"):
                    job["status"] = "cancelled"
                    return
                job["status"] = "yielding"
                await asyncio.sleep(0.5)

            job["status"] = "running"
            job["current_recipient"] = f"{target_info['name']} ({target_info['platform']})"

            text_body = (
                f"📢 *Pengumuman SGA ({target_info.get('division') or 'Umum'})*\n\n"
                f"Halo {target_info.get('name')},\n"
                f"{job['message']}\n\n"
                f"— Notion Agent SGA"
            )

            try:
                if target_info["platform"] == "telegram":
                    await send_telegram_message(target_info["target"], text_body)
                else:
                    await send_direct_message(target_info["target"], text_body)
                job["sent"] += 1
            except Exception as e:
                logger.warning(f"Failed sending broadcast to {target_info}: {e}")
                job["failed"] += 1

            # Sleep between broadcasts with chat yield check
            elapsed = 0.0
            step = 0.5
            while elapsed < delay:
                if job.get("_cancel_requested"):
                    job["status"] = "cancelled"
                    return
                if self.has_active_chats():
                    job["status"] = "yielding"
                    while self.has_active_chats():
                        if job.get("_cancel_requested"):
                            job["status"] = "cancelled"
                            return
                        await asyncio.sleep(0.5)
                    job["status"] = "running"
                await asyncio.sleep(min(step, delay - elapsed))
                elapsed += step

        if not job.get("_cancel_requested"):
            job["status"] = "completed"
        job["current_recipient"] = None

    def _format_broadcast_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": job["id"],
            "message": job.get("message", ""),
            "division": job.get("division", "all"),
            "platform": job.get("platform", "all"),
            "delay_seconds": job.get("delay_seconds", 5.0),
            "total": job.get("total", 0),
            "sent": job.get("sent", 0),
            "failed": job.get("failed", 0),
            "current_recipient": job.get("current_recipient"),
            "status": job.get("status", "pending"),
            "created_at": job.get("created_at"),
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "chat_queue": {
                "active_count": len(self.active_chat_items),
                "items": list(self.active_chat_items),
            },
            "broadcast_jobs": [
                self._format_broadcast_job(j)
                for j in reversed(self.broadcast_jobs[-20:])
            ],
        }


queue_manager = QueueManager()
