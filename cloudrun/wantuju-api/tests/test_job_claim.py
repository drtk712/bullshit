"""Job leases are claimed atomically."""
from __future__ import annotations

import threading
import time

from app.services.tasks import PROCESSING_RECOVERY_AFTER_MS, TaskService


class _Storage:
    pass


def _service(db) -> TaskService:
    return TaskService(db=db, storage=_Storage())


def _insert_job(db, **overrides) -> str:
    now = int(time.time() * 1000)
    document = {
        "openid": "worker-user",
        "type": "palm",
        "status": "pending",
        "param": {},
        "fileID": "cloud://test/a.jpg",
        "fileIDs": ["cloud://test/a.jpg"],
        "generationPrompt": "prompt",
        "createdAt": now,
        "updatedAt": now,
    }
    document.update(overrides)
    return db.insert_documents("feature_jobs", [document])["ids"][0]


def test_pending_job_can_be_claimed_once(db):
    task_id = _insert_job(db)
    service = _service(db)

    claimed = service.claim_processing_job(task_id)
    again = service.claim_processing_job(task_id)

    assert claimed is not None
    assert claimed["status"] == "processing"
    assert claimed["processingLeaseToken"]
    assert again is None
    stored = db.get_document("feature_jobs", task_id)
    assert stored["processingLeaseToken"] == claimed["processingLeaseToken"]
    assert stored["status"] == "processing"


def test_expired_processing_lease_can_be_reclaimed(db):
    expired = int(time.time() * 1000) - PROCESSING_RECOVERY_AFTER_MS - 1000
    task_id = _insert_job(
        db,
        status="processing",
        processingLeaseToken="old-token",
        processingLeaseAt=expired,
        updatedAt=expired,
    )
    service = _service(db)

    claimed = service.claim_processing_job(task_id)

    assert claimed is not None
    assert claimed["processingLeaseToken"] != "old-token"
    assert claimed["status"] == "processing"


def test_completed_job_is_not_claimed(db):
    task_id = _insert_job(db, status="completed")

    assert _service(db).claim_processing_job(task_id) is None
    assert db.get_document("feature_jobs", task_id)["status"] == "completed"


def test_concurrent_claims_have_one_winner(db):
    task_id = _insert_job(db)
    service = _service(db)
    barrier = threading.Barrier(2)
    winners: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        barrier.wait()
        claimed = service.claim_processing_job(task_id)
        if claimed:
            with lock:
                winners.append(claimed["processingLeaseToken"])

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1
    stored = db.get_document("feature_jobs", task_id)
    assert stored["status"] == "processing"
    assert stored["processingLeaseToken"] == winners[0]
