import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.queue import QueueManager


@pytest.mark.asyncio
async def test_db_persistence_broadcast_job():
    qm = QueueManager()
    
    mock_contacts = [
        {"id": 1, "name": "Budi", "phone": "62899991", "division": "Tech"},
        {"id": 2, "name": "Andi", "phone": "62899992", "division": "Tech"},
    ]

    mock_db_jobs = {}
    mock_db_recipients = {}

    async def mock_create(job):
        mock_db_jobs[job["id"]] = dict(job)
        mock_db_recipients[job["id"]] = [dict(r) for r in job.get("recipients", [])]

    async def mock_update_recipient(job_id, target, platform, status, error=None, sent_at=None):
        for r in mock_db_recipients.get(job_id, []):
            if r["target"] == target and r["platform"] == platform:
                r["status"] = status
                r["error"] = error
                r["sent_at"] = sent_at

    async def mock_update_job(job):
        if job["id"] in mock_db_jobs:
            mock_db_jobs[job["id"]].update({
                "status": job["status"],
                "sent": job["sent"],
                "failed": job["failed"],
                "completed_at": job.get("completed_at"),
            })

    async def dummy_wa_send(phone, text):
        if phone == "62899992":
            raise RuntimeError("Network timeout")

    with patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=mock_contacts)), \
         patch.object(qm, "_db_create_broadcast_job", side_effect=mock_create), \
         patch.object(qm, "_db_update_recipient", side_effect=mock_update_recipient), \
         patch.object(qm, "_db_update_job_status", side_effect=mock_update_job), \
         patch("app.wa.sender.send_direct_message", side_effect=dummy_wa_send):

        job = await qm.enqueue_broadcast(
            message="Test Persist Message",
            division="Tech",
            platform="wa",
            delay_seconds=0.01,
        )

        assert job["id"] in mock_db_jobs
        assert len(mock_db_recipients[job["id"]]) == 2

        # Allow worker to finish
        await asyncio.sleep(0.2)

        persisted_job = mock_db_jobs[job["id"]]
        assert persisted_job["status"] == "completed"
        assert persisted_job["sent"] == 1
        assert persisted_job["failed"] == 1

        persisted_recs = mock_db_recipients[job["id"]]
        r1 = next(r for r in persisted_recs if r["target"] == "62899991")
        r2 = next(r for r in persisted_recs if r["target"] == "62899992")
        assert r1["status"] == "sent"
        assert r2["status"] == "failed"
        assert "Network timeout" in r2["error"]
