from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.job import Base
import logging

DATABASE_URL = "postgresql://user:password@db:5432/taskqueue"


engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARN)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import job  # Import all models here
    Base.metadata.create_all(bind=engine)
