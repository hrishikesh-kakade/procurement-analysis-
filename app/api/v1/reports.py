from fastapi import APIRouter, Response, status

from app.api.deps import JobSvc
from app.api.permissions import CurrentUser
from app.schemas.common import DateRange
from app.schemas.report import ReportJob, ReportRequest

router = APIRouter(prefix="/reports", tags=["Reports (background jobs)"])


@router.post("", response_model=ReportJob, status_code=status.HTTP_202_ACCEPTED)
def request_report(payload: ReportRequest, service: JobSvc, user: CurrentUser):
    """Queue a CSV report. Poll `GET /reports/{job_id}` then download it."""
    return service.submit_report(
        payload.report_type, DateRange(payload.date_from, payload.date_to), user
    )


@router.get("/{job_id}", response_model=ReportJob)
def report_status(job_id: str, service: JobSvc, user: CurrentUser):
    return service.status(job_id, user)


@router.get("/{job_id}/download", summary="Download a finished report (CSV)")
def download_report(job_id: str, service: JobSvc, user: CurrentUser):
    content = service.download(job_id, user)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="report-{job_id[:8]}.csv"'},
    )
