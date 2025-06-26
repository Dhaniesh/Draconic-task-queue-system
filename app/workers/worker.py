import time
from sqlalchemy.orm import Session
from app.services.database import SessionLocal
from app.models.job import Job, JobStatus
from app.services.job_service import can_execute_job, execute_job

import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARN)

def get_pending_jobs(db: Session):
    """
    Retrieve pending jobs ordered by priority and creation time.
    """
    return (
        db.query(Job)
        .filter(Job.status == JobStatus.pending)
        .order_by(Job.priority.asc(), Job.created_at.asc())
        .all()
    )

def run_worker(poll_interval_idle: int = 5, poll_interval_active: int = 1):
    """
    Main worker loop to process jobs.
    """
    print("🚀 Starting job worker...")

    while True:
        db = SessionLocal()
        try:
            pending_jobs = get_pending_jobs(db)

            if not pending_jobs:
                print("🟡 No pending jobs. Sleeping...")
                time.sleep(poll_interval_idle)
                continue

            for job in pending_jobs:
                try:
                    if can_execute_job(db, job):
                        print(f"Executing job {job.job_id} (Priority: {job.priority})")
                        success = execute_job(db, job)
                        print(f"Job {job.job_id} {'completed' if success else 'failed'}")
                    else:
                        print(f"⏳ Job {job.job_id} is not ready (dependencies/resources)")
                except Exception as job_error:
                    print(f"Error processing job {job.job_id}: {job_error}")

            time.sleep(poll_interval_active)

        except Exception as loop_error:
            print(f"Worker loop error: {loop_error}")
            time.sleep(10)  # Backoff on failure

        finally:
            db.close()

if __name__ == "__main__":
    run_worker()
