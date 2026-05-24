from __future__ import annotations

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.bff.database import Base


class EnrichmentSnapshot(Base):
    __tablename__ = "enrichment_snapshot"

    upload_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    ref_date: Mapped[str] = mapped_column(String)
    customer_txn_count_30d: Mapped[int] = mapped_column(Integer)
    customer_sum_30d: Mapped[float] = mapped_column(Float)
    customer_avg_30d: Mapped[float] = mapped_column(Float)
    customer_std_amt_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    account_type: Mapped[str | None] = mapped_column(String, nullable=True)
    account_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structuring_24h_count: Mapped[int] = mapped_column(Integer)
    velocity_zscore: Mapped[float | None] = mapped_column(Float, nullable=True)
    dormancy_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
