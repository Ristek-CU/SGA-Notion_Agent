"""Dual Priority Queue manager for Notion Agent SGA.

High Priority: Chat Queue (FIFO, delay 3s between outgoing replies).
Low Priority: Broadcast Queue (delay 5s between broadcasts, yields to chat).
Persisted to PostgreSQL with in-memory fallback.
"""
import asyncio
import logging
import random
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def resolve_file_url_for_waha(file_url: str) -> str:
    """WAHA berjalan di dokploy-network atau host.
    Jika file_url menggunakan localhost atau roro-api.mannn.app, kita bisa pastikan
    WAHA yang satu network dokploy-network bisa reach via internal container name atau public URL.
    Biasanya public URL https://roro-api.mannn.app/uploads/... bisa dijangkau oleh WAHA (karena internet aktif).
    Jika URL adalah internal container URL atau localhost, kita ubah sesuai kebutuhan.
    """
    if not file_url:
        return file_url
    # Jika URL relatif (misal /uploads/abc.pdf), tambahkan backend_public_url
    if file_url.startswith("/"):
        from app.config import settings
        return f"{settings.backend_public_url.rstrip('/')}{file_url}"
    return file_url


class QueueManager:
    def __init__(self):
        self.chat_queue: asyncio.Queue = asyncio.Queue()
        self.active_chat_items: List[Dict[str, Any]] = []
        self.broadcast_jobs: List[Dict[str, Any]] = []

        self._active_chat_lock = asyncio.Lock()
        self._active_chat_count = 0  # in-flight / processing chat items
        self._chat_worker_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._chat_worker_task = asyncio.create_task(self._chat_worker(), name="chat_queue_worker")
        asyncio.create_task(self._mark_interrupted_jobs(), name="broadcast_interrupted_cleanup")

    async def _mark_interrupted_jobs(self):
        """Mark uncompleted running/yielding/waiting jobs as cancelled across restarts."""
        try:
            from app.services.database import get_db_pool
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE broadcast_jobs
                        SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                        WHERE status IN ('running', 'yielding', 'waiting')
                        """
                    )
        except Exception as e:
            logger.warning(f"Error checking interrupted broadcast jobs on startup: {e}")

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
                res = handler()
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    await res
            except Exception as e:
                logger.error(f"Error processing chat item {item_id}: {e}", exc_info=True)
            finally:
                # Cooldown 3 seconds between outgoing chat replies
                await self._update_chat_item_status(item_id, "cooldown")
                await asyncio.sleep(3.0)
                await self._remove_chat_item(item_id)
                self.chat_queue.task_done()

    # -------------------------------------------------------------------------
    # DB Sync Helpers for Broadcast
    # -------------------------------------------------------------------------
    async def _db_create_broadcast_job(self, job: Dict[str, Any]):
        try:
            from app.services.database import get_db_pool
            pool = await get_db_pool()
            if not pool:
                return
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO broadcast_jobs (
                            id, message, division, platform, status,
                            total, sent, failed, pending, delay_seconds,
                            file_url, file_name, file_mimetype, file_size,
                            created_at, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, TO_TIMESTAMP($15), CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        job["id"],
                        job.get("message", ""),
                        job.get("division", "all"),
                        job.get("platform", "all"),
                        job.get("status", "running"),
                        job.get("total", 0),
                        job.get("sent", 0),
                        job.get("failed", 0),
                        job.get("total", 0),
                        float(job.get("delay_seconds", 5.0)),
                        job.get("file_url"),
                        job.get("file_name"),
                        job.get("file_mimetype"),
                        job.get("file_size"),
                        float(job.get("created_at", time.time())),
                    )

                    recipients = job.get("recipients", [])
                    if recipients:
                        rows = [
                            (
                                job["id"],
                                str(r.get("contact_id") or "") if r.get("contact_id") is not None else None,
                                r.get("name") or "",
                                r.get("platform") or "",
                                r.get("target") or "",
                                r.get("division") or "",
                                r.get("status") or "pending",
                                r.get("error"),
                            )
                            for r in recipients
                        ]
                        await conn.executemany(
                            """
                            INSERT INTO broadcast_recipients (
                                job_id, contact_id, name, platform, target, division, status, error
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            rows,
                        )
        except Exception as e:
            logger.warning(f"Error inserting broadcast job into DB: {e}")

    async def _db_update_recipient(
        self,
        job_id: str,
        target: str,
        platform: str,
        status: str,
        error: Optional[str] = None,
        sent_at: Optional[float] = None,
    ):
        try:
            from app.services.database import get_db_pool
            pool = await get_db_pool()
            if not pool:
                return
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE broadcast_recipients
                    SET status = $1,
                        error = $2,
                        sent_at = CASE WHEN $3::float IS NOT NULL THEN TO_TIMESTAMP($3::float) ELSE CURRENT_TIMESTAMP END
                    WHERE job_id = $4 AND target = $5 AND platform = $6
                    """,
                    status,
                    error,
                    sent_at,
                    job_id,
                    target,
                    platform,
                )
        except Exception as e:
            logger.warning(f"Error updating broadcast recipient in DB: {e}")

    async def _db_update_job_status(self, job: Dict[str, Any]):
        try:
            from app.services.database import get_db_pool
            pool = await get_db_pool()
            if not pool:
                return
            async with pool.acquire() as conn:
                comp_ts = job.get("completed_at")
                await conn.execute(
                    """
                    UPDATE broadcast_jobs
                    SET status = $1,
                        sent = $2,
                        failed = $3,
                        pending = $4,
                        updated_at = CURRENT_TIMESTAMP,
                        completed_at = CASE WHEN $5::float IS NOT NULL THEN TO_TIMESTAMP($5::float) ELSE completed_at END
                    WHERE id = $6
                    """,
                    job.get("status", "running"),
                    job.get("sent", 0),
                    job.get("failed", 0),
                    max(0, job.get("total", 0) - job.get("sent", 0) - job.get("failed", 0)),
                    float(comp_ts) if comp_ts else None,
                    job["id"],
                )
        except Exception as e:
            logger.warning(f"Error updating broadcast job status in DB: {e}")

    # -------------------------------------------------------------------------
    # Broadcast Queue Methods
    # -------------------------------------------------------------------------
    async def enqueue_broadcast(
        self,
        message: str,
        division: str = "all",
        platform: str = "all",
        delay_seconds: float = 5.0,
        recipients_override: Optional[List[str]] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_mimetype: Optional[str] = None,
        file_size: Optional[int] = None,
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
                    (
                        c
                        for c in all_contacts
                        if c.get("phone") == r_clean
                        or (c.get("name") or "").lower() == r_clean.lower()
                        or (c.get("nickname") or "").lower() == r_clean.lower()
                    ),
                    None,
                )
                if matched:
                    plat = platform.lower()
                    if plat in ("wa", "whatsapp"):
                        if matched.get("phone"):
                            targets.append({
                                "contact_id": str(matched.get("id") or ""),
                                "name": matched.get("name") or r_clean,
                                "platform": "wa",
                                "target": matched.get("phone"),
                                "division": matched.get("division") or "Direct",
                                "status": "pending",
                                "error": None,
                                "sent_at": None,
                            })
                    elif plat == "telegram":
                        if matched.get("telegram"):
                            targets.append({
                                "contact_id": str(matched.get("id") or ""),
                                "name": matched.get("name") or r_clean,
                                "platform": "telegram",
                                "target": matched.get("telegram"),
                                "telegram_chat_id": matched.get("telegram_chat_id"),
                                "division": matched.get("division") or "Direct",
                                "status": "pending",
                                "error": None,
                                "sent_at": None,
                            })
                    else:
                        if matched.get("phone"):
                            targets.append({
                                "contact_id": str(matched.get("id") or ""),
                                "name": matched.get("name") or r_clean,
                                "platform": "wa",
                                "target": matched.get("phone"),
                                "division": matched.get("division") or "Direct",
                                "status": "pending",
                                "error": None,
                                "sent_at": None,
                            })
                        if matched.get("telegram"):
                            targets.append({
                                "contact_id": str(matched.get("id") or ""),
                                "name": matched.get("name") or r_clean,
                                "platform": "telegram",
                                "target": matched.get("telegram"),
                                "telegram_chat_id": matched.get("telegram_chat_id"),
                                "division": matched.get("division") or "Direct",
                                "status": "pending",
                                "error": None,
                                "sent_at": None,
                            })
                else:
                    targets.append({
                        "contact_id": "",
                        "name": r_clean,
                        "platform": "wa",
                        "target": r_clean,
                        "division": "Direct",
                        "status": "pending",
                        "error": None,
                        "sent_at": None,
                    })
        else:
            plat = platform.lower()
            for c in all_contacts:
                div = c.get("division") or ""
                if division != "all" and div.lower() != division.lower():
                    continue

                if plat in ("wa", "whatsapp"):
                    if c.get("phone"):
                        targets.append({
                            "contact_id": str(c.get("id") or ""),
                            "name": c.get("nickname") or c.get("name"),
                            "platform": "wa",
                            "target": c.get("phone"),
                            "division": div,
                            "status": "pending",
                            "error": None,
                            "sent_at": None,
                        })
                elif plat == "telegram":
                    if c.get("telegram"):
                        targets.append({
                            "contact_id": str(c.get("id") or ""),
                            "name": c.get("nickname") or c.get("name"),
                            "platform": "telegram",
                            "target": c.get("telegram"),
                            "telegram_chat_id": c.get("telegram_chat_id"),
                            "division": div,
                            "status": "pending",
                            "error": None,
                            "sent_at": None,
                        })
                else:
                    if c.get("phone"):
                        targets.append({
                            "contact_id": str(c.get("id") or ""),
                            "name": c.get("nickname") or c.get("name"),
                            "platform": "wa",
                            "target": c.get("phone"),
                            "division": div,
                            "status": "pending",
                            "error": None,
                            "sent_at": None,
                        })
                    if c.get("telegram"):
                        targets.append({
                            "contact_id": str(c.get("id") or ""),
                            "name": c.get("nickname") or c.get("name"),
                            "platform": "telegram",
                            "target": c.get("telegram"),
                            "telegram_chat_id": c.get("telegram_chat_id"),
                            "division": div,
                            "status": "pending",
                            "error": None,
                            "sent_at": None,
                        })

        job = {
            "id": job_id,
            "message": message,
            "division": division,
            "platform": platform,
            "delay_seconds": float(delay_seconds) if delay_seconds > 0 else 5.0,
            "file_url": file_url,
            "file_name": file_name,
            "file_mimetype": file_mimetype,
            "file_size": file_size,
            "total": len(targets),
            "sent": 0,
            "failed": 0,
            "current_recipient": None,
            "status": "running" if targets else "completed",
            "created_at": time.time(),
            "completed_at": None if targets else time.time(),
            "_cancel_requested": False,
            "recipients": targets,
        }

        self.broadcast_jobs.append(job)

        # Save to database
        await self._db_create_broadcast_job(job)

        if targets:
            asyncio.create_task(self._run_broadcast_job(job))

        return self._format_broadcast_job(job)

    async def cancel_broadcast(self, job_id: Optional[str] = None) -> bool:
        cancelled = False
        target_jobs = []
        for job in self.broadcast_jobs:
            if job["status"] in ("running", "yielding"):
                if job_id is None or job["id"] == job_id:
                    job["_cancel_requested"] = True
                    job["status"] = "cancelled"
                    job["completed_at"] = time.time()
                    cancelled = True
                    target_jobs.append(job)

        for j in target_jobs:
            await self._db_update_job_status(j)

        if job_id and not cancelled:
            # Fallback DB update if not in memory
            try:
                from app.services.database import get_db_pool
                pool = await get_db_pool()
                if pool:
                    async with pool.acquire() as conn:
                        res = await conn.execute(
                            """
                            UPDATE broadcast_jobs
                            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                            WHERE id = $1 AND status IN ('running', 'yielding', 'waiting')
                            """,
                            job_id,
                        )
                        if "UPDATE 1" in res:
                            cancelled = True
            except Exception as e:
                logger.warning(f"Error cancelling broadcast job {job_id} in DB: {e}")

        return cancelled

    async def _run_broadcast_job(self, job: Dict[str, Any]):
        from app.wa.sender import send_direct_message, send_whatsapp_file
        from app.telegram.bot import send_telegram_message, send_telegram_document

        targets = job.get("recipients", [])
        base_delay = job.get("delay_seconds", 5.0)
        file_url = job.get("file_url")
        file_name = job.get("file_name")
        file_mimetype = job.get("file_mimetype")

        consecutive_sent = 0
        batch_threshold = random.randint(10, 12)

        for target_info in targets:
            if job.get("_cancel_requested"):
                job["status"] = "cancelled"
                job["completed_at"] = time.time()
                await self._db_update_job_status(job)
                break

            # Yield to chat queue if any chat is queued or processing
            while self.has_active_chats():
                if job.get("_cancel_requested"):
                    job["status"] = "cancelled"
                    job["completed_at"] = time.time()
                    await self._db_update_job_status(job)
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
                    from app.services.contacts import get_telegram_chat_id
                    dest_chat_id = await get_telegram_chat_id(target_info["target"])
                    if not dest_chat_id and target_info.get("telegram_chat_id"):
                        dest_chat_id = str(target_info["telegram_chat_id"])
                    if not dest_chat_id:
                        raise RuntimeError("telegram_chat_id tidak ditemukan (Pengguna belum pernah klik /start atau mengirim pesan ke bot Telegram)")

                    if file_url:
                        # Kirim dokumen via Telegram sendDocument dengan caption
                        resolved_tg_url = resolve_file_url_for_waha(file_url)
                        await send_telegram_document(
                            dest_chat_id,
                            document_url=resolved_tg_url,
                            caption=text_body,
                            filename=file_name,
                        )
                    else:
                        await send_telegram_message(dest_chat_id, text_body)
                else:
                    if file_url:
                        # Kirim file via WAHA sendFile dengan caption
                        resolved_wa_url = resolve_file_url_for_waha(file_url)
                        await send_whatsapp_file(
                            number_or_jid=target_info["target"],
                            file_url=resolved_wa_url,
                            filename=file_name,
                            caption=text_body,
                            mimetype=file_mimetype,
                        )
                    else:
                        await send_direct_message(target_info["target"], text_body)
                target_info["status"] = "sent"
                target_info["sent_at"] = time.time()
                job["sent"] += 1
                await self._db_update_recipient(
                    job_id=job["id"],
                    target=target_info["target"],
                    platform=target_info["platform"],
                    status="sent",
                    sent_at=target_info["sent_at"],
                )
            except Exception as e:
                err_msg = str(e)
                if "chat not found" in err_msg.lower() and target_info.get("platform") == "telegram":
                    err_msg = f"{err_msg} (Pengguna belum pernah klik /start atau mengirim pesan ke bot Telegram)"
                logger.warning(f"Failed sending broadcast to {target_info['target']}: {err_msg}")
                target_info["status"] = "failed"
                target_info["error"] = err_msg
                target_info["sent_at"] = time.time()
                job["failed"] += 1
                await self._db_update_recipient(
                    job_id=job["id"],
                    target=target_info["target"],
                    platform=target_info["platform"],
                    status="failed",
                    error=err_msg,
                    sent_at=target_info["sent_at"],
                )

            # Track consecutive sent messages for Human Cooling Pause
            if target_info.get("status") == "sent":
                consecutive_sent += 1
            else:
                consecutive_sent = 0

            # Update job progress in DB after each recipient
            await self._db_update_job_status(job)

            # Check if cooling pause is triggered (after 10-12 consecutive sent messages)
            if consecutive_sent >= batch_threshold:
                cooling_pause = random.uniform(12.0, 20.0)
                logger.info(
                    f"[BROADCAST_QUEUE] Taking human cooling break for {cooling_pause:.1f}s after batch ({consecutive_sent} sent)..."
                )
                consecutive_sent = 0
                batch_threshold = random.randint(10, 12)

                # Execute cooling pause with cancel & chat yield checks
                c_elapsed = 0.0
                c_step = 0.5
                while c_elapsed < cooling_pause:
                    if job.get("_cancel_requested"):
                        job["status"] = "cancelled"
                        job["completed_at"] = time.time()
                        await self._db_update_job_status(job)
                        return
                    if self.has_active_chats():
                        job["status"] = "yielding"
                        while self.has_active_chats():
                            if job.get("_cancel_requested"):
                                job["status"] = "cancelled"
                                job["completed_at"] = time.time()
                                await self._db_update_job_status(job)
                                return
                            await asyncio.sleep(0.5)
                        job["status"] = "running"
                    await asyncio.sleep(min(c_step, cooling_pause - c_elapsed))
                    c_elapsed += c_step

            # Anti-Spam Random Jitter: base_delay + uniform(1.5, 4.5)
            # If base_delay is very small (e.g. tests with < 0.1s), skip or scale down jitter
            if base_delay > 0.1:
                jitter = random.uniform(1.5, 4.5)
                delay = base_delay + jitter
            else:
                delay = base_delay

            # Sleep between broadcasts with chat yield check
            elapsed = 0.0
            step = 0.5
            while elapsed < delay:
                if job.get("_cancel_requested"):
                    job["status"] = "cancelled"
                    job["completed_at"] = time.time()
                    await self._db_update_job_status(job)
                    return
                if self.has_active_chats():
                    job["status"] = "yielding"
                    while self.has_active_chats():
                        if job.get("_cancel_requested"):
                            job["status"] = "cancelled"
                            job["completed_at"] = time.time()
                            await self._db_update_job_status(job)
                            return
                        await asyncio.sleep(0.5)
                    job["status"] = "running"
                await asyncio.sleep(min(step, delay - elapsed))
                elapsed += step

        if not job.get("_cancel_requested"):
            job["status"] = "completed"
            job["completed_at"] = time.time()
        job["current_recipient"] = None
        await self._db_update_job_status(job)

    def _format_broadcast_job(self, job: Dict[str, Any], include_recipients: bool = False) -> Dict[str, Any]:
        res = {
            "id": job["id"],
            "message": job.get("message", ""),
            "division": job.get("division", "all"),
            "platform": job.get("platform", "all"),
            "delay_seconds": job.get("delay_seconds", 5.0),
            "file_url": job.get("file_url"),
            "file_name": job.get("file_name"),
            "file_mimetype": job.get("file_mimetype"),
            "file_size": job.get("file_size"),
            "total": job.get("total", 0),
            "sent": job.get("sent", 0),
            "failed": job.get("failed", 0),
            "current_recipient": job.get("current_recipient"),
            "status": job.get("status", "pending"),
            "created_at": job.get("created_at"),
            "completed_at": job.get("completed_at"),
        }
        if include_recipients:
            res["recipients"] = job.get("recipients", [])
        return res

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        # Check active in-memory list first for live current_recipient / progress
        for j in self.broadcast_jobs:
            if j["id"] == job_id:
                return self._format_broadcast_job(j, include_recipients=True)

        # Query PostgreSQL
        try:
            from app.services.database import get_db_pool
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT 
                            id, message, division, platform, delay_seconds,
                            file_url, file_name, file_mimetype, file_size,
                            total, sent, failed, status,
                            EXTRACT(EPOCH FROM created_at) as created_at,
                            EXTRACT(EPOCH FROM completed_at) as completed_at
                        FROM broadcast_jobs
                        WHERE id = $1
                        """,
                        job_id,
                    )
                    if row:
                        recipients_rows = await conn.fetch(
                            """
                            SELECT 
                                contact_id, name, platform, target, division, status, error,
                                EXTRACT(EPOCH FROM sent_at) as sent_at
                            FROM broadcast_recipients
                            WHERE job_id = $1
                            ORDER BY id ASC
                            """,
                            job_id,
                        )
                        job_dict = dict(row)
                        job_dict["recipients"] = [dict(r) for r in recipients_rows]
                        return self._format_broadcast_job(job_dict, include_recipients=True)
        except Exception as e:
            logger.warning(f"Error fetching job {job_id} from DB: {e}")

        return None

    async def get_broadcast_jobs(self, status_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        # Attempt to load from PostgreSQL first
        try:
            from app.services.database import get_db_pool
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    where_clause = ""
                    params = []
                    if status_filter == "active":
                        where_clause = "WHERE status IN ('running', 'yielding', 'pending', 'waiting')"
                    elif status_filter == "history":
                        where_clause = "WHERE status IN ('completed', 'cancelled')"
                    elif status_filter:
                        where_clause = "WHERE status = $1"
                        params.append(status_filter)

                    limit_param = f"${len(params) + 1}"
                    params.append(limit)

                    query = f"""
                        SELECT 
                            id, message, division, platform, delay_seconds,
                            file_url, file_name, file_mimetype, file_size,
                            total, sent, failed, status,
                            EXTRACT(EPOCH FROM created_at) as created_at,
                            EXTRACT(EPOCH FROM completed_at) as completed_at
                        FROM broadcast_jobs
                        {where_clause}
                        ORDER BY created_at DESC
                        LIMIT {limit_param}
                    """
                    rows = await conn.fetch(query, *params)
                    if rows:
                        job_ids = [r["id"] for r in rows]
                        rec_rows = await conn.fetch(
                            """
                            SELECT 
                                job_id, contact_id, name, platform, target, division, status, error,
                                EXTRACT(EPOCH FROM sent_at) as sent_at
                            FROM broadcast_recipients
                            WHERE job_id = ANY($1::varchar[])
                            ORDER BY id ASC
                            """,
                            job_ids,
                        )
                        recs_by_job: Dict[str, List[Dict[str, Any]]] = {}
                        for rr in rec_rows:
                            recs_by_job.setdefault(rr["job_id"], []).append(dict(rr))

                        # Build job list, overlaying in-memory running stats if active
                        in_mem_map = {j["id"]: j for j in self.broadcast_jobs}
                        res_list = []
                        for r in rows:
                            j_dict = dict(r)
                            jid = j_dict["id"]
                            if jid in in_mem_map and in_mem_map[jid]["status"] in ("running", "yielding", "pending"):
                                mem_job = in_mem_map[jid]
                                j_dict["current_recipient"] = mem_job.get("current_recipient")
                                j_dict["sent"] = mem_job.get("sent", j_dict["sent"])
                                j_dict["failed"] = mem_job.get("failed", j_dict["failed"])
                                j_dict["status"] = mem_job.get("status", j_dict["status"])
                                j_dict["recipients"] = mem_job.get("recipients", recs_by_job.get(jid, []))
                            else:
                                j_dict["recipients"] = recs_by_job.get(jid, [])
                            res_list.append(self._format_broadcast_job(j_dict, include_recipients=True))
                        return res_list
        except Exception as e:
            logger.warning(f"Error fetching broadcast jobs from DB: {e}")

        # Fallback to in-memory list
        jobs = []
        for j in reversed(self.broadcast_jobs):
            st = j.get("status", "")
            if status_filter == "active":
                if st not in ("running", "yielding", "pending"):
                    continue
            elif status_filter == "history":
                if st not in ("completed", "cancelled"):
                    continue
            elif status_filter and st != status_filter:
                continue
            jobs.append(self._format_broadcast_job(j, include_recipients=True))
            if len(jobs) >= limit:
                break
        return jobs

    async def get_status(self) -> Dict[str, Any]:
        # Get latest 20 broadcast jobs from get_broadcast_jobs
        b_jobs = await self.get_broadcast_jobs(limit=20)
        return {
            "chat_queue": {
                "active_count": len(self.active_chat_items),
                "items": list(self.active_chat_items),
            },
            "broadcast_jobs": b_jobs,
        }


queue_manager = QueueManager()
