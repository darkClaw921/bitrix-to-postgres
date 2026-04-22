"""In-memory job store for long-running background tasks."""

import time
import uuid
from typing import Any, Literal, TypedDict

JobStatus = Literal["pending", "running", "done", "error"]

_JOB_TTL_SECONDS = 1800  # 30 min


class JobRecord(TypedDict):
    job_id: str
    status: JobStatus
    result: list[dict[str, Any]] | None
    error: str | None
    created_at: float


_jobs: dict[str, JobRecord] = {}


def _evict_old_jobs() -> None:
    now = time.time()
    stale = [jid for jid, j in _jobs.items() if now - j["created_at"] > _JOB_TTL_SECONDS]
    for jid in stale:
        del _jobs[jid]


def create_job() -> str:
    _evict_old_jobs()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": time.time(),
    }
    return job_id


def get_job(job_id: str) -> JobRecord | None:
    return _jobs.get(job_id)


def update_job(job_id: str, status: JobStatus, result: list[dict] | None = None, error: str | None = None) -> None:
    if job_id in _jobs:
        _jobs[job_id]["status"] = status
        _jobs[job_id]["result"] = result
        _jobs[job_id]["error"] = error
