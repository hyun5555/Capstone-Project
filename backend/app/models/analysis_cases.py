# app/models/analysis_cases.py
from sqlalchemy import JSON, Column, String, ForeignKey, DateTime, func
from app.db.session import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    job_id = Column(String(36), primary_key=True)
    user_id = Column(String(255), ForeignKey("users.user_id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    stage = Column(String(100), nullable=False, default="업로드 완료")
    case_id = Column(String(64), nullable=True, index=True)
    result = Column(JSON, nullable=True)
    error = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VectorDeletion(Base):
    """Chroma 삭제가 일시 실패해도 개인 데이터 삭제를 재시도하기 위한 case 해시 대기열."""
    __tablename__ = "vector_deletions"

    case_id = Column(String(64), primary_key=True)
    requested_at = Column(DateTime, server_default=func.now(), nullable=False)
