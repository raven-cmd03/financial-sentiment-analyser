from sqlalchemy import Column, Integer, String, DateTime, JSON, func
from app.database import Base


class FinetuningJob(Base):
    __tablename__ = "finetuning_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_name = Column(String(255), nullable=False)
    hyperparams = Column(JSON, nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    metrics = Column(JSON, default=dict)
    model_path = Column(String(500))
    is_active = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
