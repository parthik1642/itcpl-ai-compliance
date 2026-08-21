from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text
)

from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    po_no = Column(
        String,
        nullable=True
    )

    collection_no = Column(
        String,
        nullable=True
    )

    customer = Column(
        String,
        nullable=True
    )

    overall_status = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    labs = relationship(
        "LabResult",
        back_populates="job",
        cascade="all, delete-orphan"
    )


class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=False
    )

    lab_no = Column(
        String,
        nullable=False
    )

    heat_no = Column(
        String,
        nullable=True
    )

    final_status = Column(
        String,
        nullable=True
    )

    reason = Column(
        Text,
        nullable=True
    )

    required_tests = Column(
        Text,
        nullable=True
    )

    uploaded_tests = Column(
        Text,
        nullable=True
    )

    missing_tests = Column(
        Text,
        nullable=True
    )

    issues = Column(
        Text,
        nullable=True
    )

    review_status = Column(
        String,
        nullable=True
    )

    review_note = Column(
        Text,
        nullable=True
    )

    reviewed_by = Column(
        String,
        nullable=True
    )

    reviewed_at = Column(
        DateTime,
        nullable=True
    )

    job = relationship(
        "Job",
        back_populates="labs"
    )