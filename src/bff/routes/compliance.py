from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot
from src.aml_workflow.models.rule import Rule
from src.aml_workflow.models.sar import SAR
from src.aml_workflow.models.validation_result import ValidationResult
from src.bff.database import get_db
from src.bff.models.customer import Customer
from src.bff.schemas import PendingSARResponse, PaginatedResponse
from src.file_processor.models import Transaction

router = APIRouter()


@router.get("/api/sar/pending")
async def list_pending_sars(
    upload_id: str | None = Query(None),
    customer_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PendingSARResponse]:
    base = (
        select(SAR, Transaction, ValidationResult, EnrichmentSnapshot, Rule, Customer)
        .join(Transaction, SAR.transaction_id == Transaction.id)
        .outerjoin(ValidationResult, SAR.transaction_id == ValidationResult.transaction_id)
        .outerjoin(
            EnrichmentSnapshot,
            (SAR.upload_id == EnrichmentSnapshot.upload_id)
            & (Transaction.customer_id == EnrichmentSnapshot.customer_id),
        )
        .outerjoin(Rule, SAR.rule_id == Rule.id)
        .outerjoin(Customer, Transaction.customer_id == Customer.customer_id)
        .where(SAR.status == "pending_review")
    )

    if upload_id is not None:
        base = base.where(SAR.upload_id == upload_id)
    if customer_id is not None:
        base = base.where(Transaction.customer_id == customer_id)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar()

    rows = (
        (await db.execute(
            base.order_by(SAR.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        ))
        .all()
    )

    items = []
    for sar, txn, vr, enr, rule, customer in rows:
        enrichment = None
        if enr is not None:
            enrichment = {
                "customer_txn_count_30d": enr.customer_txn_count_30d,
                "customer_sum_30d": enr.customer_sum_30d,
                "customer_avg_30d": enr.customer_avg_30d,
                "customer_std_amt_30d": enr.customer_std_amt_30d,
                "account_type": enr.account_type,
                "account_age_days": enr.account_age_days,
                "structuring_24h_count": enr.structuring_24h_count,
                "velocity_zscore": enr.velocity_zscore,
                "dormancy_days": enr.dormancy_days,
            }

        items.append(
            PendingSARResponse(
                sar_id=sar.id,
                transaction_id=sar.transaction_id,
                upload_id=sar.upload_id,
                source_txn_id=txn.source_txn_id,
                account_id=txn.account_id,
                customer_id=txn.customer_id,
                amount=txn.amount,
                counterparty=txn.counterparty,
                city=txn.city,
                state=txn.state,
                country=txn.country,
                date=txn.date,
                flag_details=vr.flag_details if vr is not None else None,
                risk_level=vr.risk_level if vr is not None else None,
                triage_reasoning=vr.triage_reasoning if vr is not None else None,
                enrichment=enrichment,
                rule_name=rule.name if rule is not None else None,
                rule_description=rule.description if rule is not None else None,
                customer_first_name=customer.first_name if customer is not None else None,
                customer_last_name=customer.last_name if customer is not None else None,
                sar_content=sar.content,
                sar_status=sar.status,
                llm_confidence=sar.llm_confidence,
                triage_stage=sar.triage_stage,
                created_at=sar.created_at,
            )
        )

    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)
