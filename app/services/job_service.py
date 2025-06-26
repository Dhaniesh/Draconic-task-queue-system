import uuid
import time
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.job import Job, JobLog, JobCreate, JobStatus, JobPriority, JobType

# Simulated in-memory resource pool (not thread-safe)
TOTAL_CPU_UNITS = 8
TOTAL_MEMORY_MB = 4096
used_cpu_units = 0
used_memory_mb = 0

def create_job(db: Session, job_data: JobCreate) -> Job:
    """
    Create a new job and add it to the database.
    """
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    # Prevent duplicate job - Using JSONB cast for comparison
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy import cast
    
    existing_job = db.query(Job).filter(
        Job.job_type == job_data.type,
        cast(Job.payload, JSONB) == job_data.payload,
        Job.status.in_([JobStatus.pending, JobStatus.running])
    ).first()
    if existing_job:
        raise ValueError(f"Duplicate job detected (ID: {existing_job.job_id})")

    # Create job
    job = Job(
        job_id=job_id,
        job_type=job_data.type,
        priority=job_data.priority,
        payload=job_data.payload,
        resource_requirements={
            "cpu_units": job_data.resource_requirements.cpu_units,
            "memory_mb": job_data.resource_requirements.memory_mb
        },
        retry_config=job_data.retry_config.dict() if job_data.retry_config else None,
        timeout_seconds=job_data.timeout_seconds,
        status=JobStatus.pending,
        position_in_queue=db.query(Job).filter(Job.status == JobStatus.pending).count() + 1
    )

    # Validate dependencies
    for dep_id in job_data.depends_on:
        if dep_id == job_id:
            raise ValueError("Self-dependency detected")
        dep_job = db.query(Job).filter(Job.job_id == dep_id).first()
        if not dep_job:
            raise ValueError(f"Dependency job {dep_id} not found")
        job.depends_on.append(dep_job)

    db.add(job)
    db.commit()
    db.refresh(job)

    # Log creation
    db.add(JobLog(job_id=job_id, status=JobStatus.pending, message="Job created"))
    db.commit()

    return job

def get_job(db: Session, job_id: str) -> Optional[Job]:
    return db.query(Job).filter(Job.job_id == job_id).first()

def list_jobs(db: Session, status: Optional[JobStatus] = None,
              priority: Optional[str] = None,
              type: Optional[str] = None,
              skip: int = 0, limit: int = 100) -> List[Job]:
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    if priority:
        try:
            query = query.filter(Job.priority == JobPriority(priority))
        except ValueError:
            pass
    if type:
        try:
            query = query.filter(Job.job_type == JobType(type))
        except ValueError:
            pass
    return query.offset(skip).limit(limit).all()

def cancel_job(db: Session, job_id: str) -> Optional[Job]:
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        return None
    if job.status not in [JobStatus.pending, JobStatus.running]:
        raise ValueError(f"Cannot cancel job in '{job.status}' state")

    was_running = job.status == JobStatus.running
    job.status = JobStatus.cancelled
    job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    db.add(JobLog(job_id=job_id, status=JobStatus.cancelled, message="Job cancelled by user"))
    db.commit()

    if was_running:
        _release_resources(job)

    return job

def get_job_logs(db: Session, job_id: str) -> Optional[List[JobLog]]:
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        return None
    return db.query(JobLog).filter(JobLog.job_id == job_id).order_by(JobLog.created_at).all()

def can_execute_job(db: Session, job: Job) -> bool:
    for dep in job.depends_on:
        if dep.status != JobStatus.completed:
            return False

    cpu_needed = job.resource_requirements.get("cpu_units", 0)
    mem_needed = job.resource_requirements.get("memory_mb", 0)
    return (used_cpu_units + cpu_needed <= TOTAL_CPU_UNITS and
            used_memory_mb + mem_needed <= TOTAL_MEMORY_MB)

def execute_job(db: Session, job: Job) -> bool:
    global used_cpu_units, used_memory_mb

    cpu = job.resource_requirements.get("cpu_units", 0)
    mem = job.resource_requirements.get("memory_mb", 0)

    used_cpu_units += cpu
    used_memory_mb += mem

    job.status = JobStatus.running
    job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    db.add(JobLog(job_id=job.job_id, status=JobStatus.running, message="Job execution started"))
    db.commit()

    try:
        time.sleep(0.5)  # Simulate job execution

        db.refresh(job)
        if job.status == JobStatus.cancelled:
            db.add(JobLog(job_id=job.job_id, status=JobStatus.cancelled, message="Job was cancelled during execution"))
            db.commit()
            _release_resources(job)
            return False

        job.status = JobStatus.completed
        job.updated_at = datetime.utcnow()
        job.completed_at = datetime.utcnow()
        db.commit()

        db.add(JobLog(job_id=job.job_id, status=JobStatus.completed, message="Job completed successfully"))
        db.commit()

        _release_resources(job)
        return True

    except Exception as e:
        return _handle_job_failure(db, job, str(e))

def _handle_job_failure(db: Session, job: Job, error: str) -> bool:
    retry_config = job.retry_config or {"max_attempts": 1, "backoff_multiplier": 2}
    attempts = db.query(JobLog).filter(JobLog.job_id == job.job_id, JobLog.status == JobStatus.failed).count()

    if attempts < retry_config["max_attempts"]:
        backoff = retry_config["backoff_multiplier"] ** attempts
        job.status = JobStatus.pending
        job.updated_at = datetime.utcnow()
        db.commit()

        db.add(JobLog(job_id=job.job_id, status=JobStatus.failed,
                      message=f"Job failed (attempt {attempts + 1}): {error}. Retrying after {backoff}s"))
        db.commit()
        time.sleep(backoff)
        _release_resources(job)
        return False
    else:
        job.status = JobStatus.failed
        job.updated_at = datetime.utcnow()
        db.commit()

        db.add(JobLog(job_id=job.job_id, status=JobStatus.failed,
                      message=f"Job permanently failed after {attempts} attempts: {error}"))
        db.commit()
        _release_resources(job)
        return False

def _release_resources(job: Job):
    global used_cpu_units, used_memory_mb
    used_cpu_units -= job.resource_requirements.get("cpu_units", 0)
    used_memory_mb -= job.resource_requirements.get("memory_mb", 0)
