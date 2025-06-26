from sqlalchemy import (
    Column, Integer, String, Enum, JSON, DateTime,
    ForeignKey, Table
)
from sqlalchemy.orm import declarative_base, relationship
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import enum

# --- SQLAlchemy base ---
Base = declarative_base()


# --- ENUMS ---
class JobType(str, enum.Enum):
    email = "email"
    data_export = "data_export"
    report_generation = "report_generation"


class JobPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


# --- ASSOCIATION TABLE (Many-to-Many for dependencies) ---
job_dependencies = Table(
    "job_dependencies",
    Base.metadata,
    Column("job_id", String, ForeignKey("jobs.job_id"), primary_key=True),
    Column("depends_on_id", String, ForeignKey(
        "jobs.job_id"), primary_key=True),
)


# --- DATABASE MODELS ---
class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True, index=True)
    job_type = Column(Enum(JobType), nullable=False)
    priority = Column(Enum(JobPriority), nullable=False,
                      default=JobPriority.normal, index=True)
    status = Column(Enum(JobStatus), nullable=False,
                    default=JobStatus.pending, index=True)
    payload = Column(JSON, nullable=False)
    resource_requirements = Column(JSON, nullable=False)
    retry_config = Column(JSON, nullable=True)
    timeout_seconds = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False,
                        default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False,
                        default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    position_in_queue = Column(Integer, nullable=True, index=True)

    # Job dependencies (many-to-many self-referential)
    depends_on = relationship(
        "Job",
        secondary=job_dependencies,
        primaryjoin=job_id == job_dependencies.c.job_id,
        secondaryjoin=job_id == job_dependencies.c.depends_on_id,
        backref="dependent_jobs"
    )

    # One-to-many: a job can have many logs
    logs = relationship("JobLog", back_populates="job")


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.job_id"),
                    nullable=False, index=True)
    status = Column(Enum(JobStatus), nullable=False)
    message = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    job = relationship("Job", back_populates="logs")


# --- PYDANTIC MODELS (for API schema validation) ---
class ResourceRequirements(BaseModel):
    cpu_units: int = Field(..., ge=1)
    memory_mb: int = Field(..., ge=128)


class RetryConfig(BaseModel):
    max_attempts: int = Field(..., ge=1, le=10)
    backoff_multiplier: float = Field(..., ge=1.0)


class JobCreate(BaseModel):
    type: JobType
    priority: JobPriority = JobPriority.normal
    payload: Dict
    resource_requirements: ResourceRequirements
    depends_on: List[str] = []
    retry_config: Optional[RetryConfig] = None
    timeout_seconds: Optional[int] = Field(None, ge=30)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    priority: JobPriority
    position_in_queue: Optional[int] = None

    class Config:
        orm_mode = True


class JobDetailResponse(JobResponse):
    type: JobType
    payload: Dict
    resource_requirements: Dict
    depends_on: List[str]
    retry_config: Optional[Dict] = None
    timeout_seconds: Optional[int] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class JobLogResponse(BaseModel):
    id: int
    job_id: str
    status: JobStatus
    message: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True
