from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.job import (
    JobCreate, JobResponse, JobDetailResponse, JobLogResponse, JobStatus
)
from app.services import job_service
from app.services.database import get_db

router = APIRouter()


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job: JobCreate, db: Session = Depends(get_db)):
    """
    Submit a new job to the queue.
    """
    try:
        return job_service.create_job(db, job)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific job.
    """
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[JobStatus] = None,
    priority: Optional[str] = None,
    type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List jobs with optional filtering by status, priority, and type.
    """
    return job_service.list_jobs(
        db,
        status=status,
        priority=priority,
        type=type,
        skip=skip,
        limit=limit
    )


@router.patch("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """
    Cancel a job if it is in a pending or running state.
    """
    try:
        job = job_service.cancel_job(db, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error canceling job")


@router.get("/jobs/{job_id}/logs", response_model=List[JobLogResponse])
async def get_job_logs(job_id: str, db: Session = Depends(get_db)):
    """
    Get execution logs for a specific job.
    """
    logs = job_service.get_job_logs(db, job_id)
    if logs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return logs
