"""Report jobs: queued on Redis (RQ) when REDIS_URL is set, otherwise run inline."""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.models import User
from app.models.enums import UserRole
from app.schemas.common import DateRange
from app.services.report_service import build_report_csv

logger = logging.getLogger(__name__)
_INLINE_JOBS: dict[str, dict] = {}
RESULT_TTL_SECONDS = 3600


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.redis_url = get_settings().redis_url

    def _redis(self):
        import redis

        return redis.Redis.from_url(self.redis_url, socket_timeout=2, socket_connect_timeout=2)

    def submit_report(self, report_type: str, rng: DateRange, user: User) -> dict:
        if not self.redis_url:
            job_id = uuid.uuid4().hex
            _INLINE_JOBS[job_id] = {
                "user_id": user.id,
                "report_type": report_type,
                "csv": build_report_csv(self.db, report_type, rng),
            }
            return {"job_id": job_id, "report_type": report_type, "status": "finished", "mode": "inline"}
        try:
            from rq import Queue

            from app.jobs.reports import run_report

            queue = Queue("reports", connection=self._redis())
            job = queue.enqueue(
                run_report,
                report_type,
                rng.date_from.isoformat() if rng.date_from else None,
                rng.date_to.isoformat() if rng.date_to else None,
                result_ttl=RESULT_TTL_SECONDS,
                failure_ttl=RESULT_TTL_SECONDS,
                meta={"user_id": user.id, "report_type": report_type},
            )
        except Exception as exc:  # redis down, etc.
            logger.exception("could not enqueue report job")
            raise ExternalServiceError("The job queue is unavailable") from exc
        return {"job_id": job.id, "report_type": report_type, "status": "queued", "mode": "queue"}

    def status(self, job_id: str, user: User) -> dict:
        if not self.redis_url:
            job = self._inline(job_id, user)
            return {"job_id": job_id, "report_type": job["report_type"], "status": "finished", "mode": "inline"}
        job = self._fetch(job_id, user)
        state = job.get_status()
        state = getattr(state, "value", state)
        return {
            "job_id": job_id,
            "report_type": job.meta.get("report_type"),
            "status": str(state),
            "mode": "queue",
        }

    def download(self, job_id: str, user: User) -> str:
        if not self.redis_url:
            return self._inline(job_id, user)["csv"]
        job = self._fetch(job_id, user)
        state = getattr(job.get_status(), "value", job.get_status())
        if str(state) != "finished":
            from app.core.exceptions import ConflictError

            raise ConflictError(f"Report is not ready (status: {state})")
        return job.result

    # ---- helpers -----------------------------------------------------------------------
    def _inline(self, job_id: str, user: User) -> dict:
        job = _INLINE_JOBS.get(job_id)
        if job is None or not self._may_access(job["user_id"], user):
            raise NotFoundError("Report job", job_id)
        return job

    def _fetch(self, job_id: str, user: User):
        from rq.exceptions import NoSuchJobError
        from rq.job import Job

        try:
            job = Job.fetch(job_id, connection=self._redis())
        except NoSuchJobError as exc:
            raise NotFoundError("Report job", job_id) from exc
        except Exception as exc:
            raise ExternalServiceError("The job queue is unavailable") from exc
        if not self._may_access(job.meta.get("user_id"), user):
            raise NotFoundError("Report job", job_id)
        return job

    @staticmethod
    def _may_access(owner_id: int | None, user: User) -> bool:
        return user.role == UserRole.ADMIN or owner_id == user.id
