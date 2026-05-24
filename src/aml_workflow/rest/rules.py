import json
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.models.rule import Rule
from src.bff.database import get_db
from src.bff.schemas import PaginatedResponse, RuleCreate, RuleResponse, RuleUpdate

router = APIRouter()


def _rule_to_response(r: Rule) -> RuleResponse:
    rules_json = r.rules_json
    if isinstance(rules_json, str):
        rules_json = json.loads(rules_json)
    return RuleResponse(
        id=r.id,
        name=r.name,
        description=r.description,
        type=r.type,
        status=r.status,
        rules_json=rules_json,
    )


@router.get("/api/rules")
async def list_rules(
    type: str | None = Query(None),
    status: str | None = Query(None),
    name: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    where_clauses = []
    if status is None:
        where_clauses.append(Rule.status == "active")
    elif status != "all":
        where_clauses.append(Rule.status == status)
    if type is not None:
        where_clauses.append(Rule.type == type)
    if name is not None:
        where_clauses.append(Rule.name == name)

    stmt = select(Rule).order_by(Rule.created_at.desc())
    if where_clauses:
        stmt = stmt.where(*where_clauses)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    offset = (page - 1) * per_page
    rows = (await db.execute(stmt.offset(offset).limit(per_page))).scalars().all()

    items = [_rule_to_response(r) for r in rows]
    return PaginatedResponse(page=page, per_page=per_page, total=total, items=items)


@router.get("/api/rules/{rule_id}")
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    r = await db.get(Rule, rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_to_response(r)


@router.post("/api/rules", status_code=201)
async def create_rule(body: RuleCreate, db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC).isoformat()
    r = Rule(
        name=body.name,
        description=body.description,
        type=body.type,
        status=body.status,
        rules_json=json.dumps(body.rules_json),
        created_at=now,
        updated_at=now,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _rule_to_response(r)


@router.put("/api/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate, db: AsyncSession = Depends(get_db)):
    existing = await db.get(Rule, rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    now = datetime.now(UTC).isoformat()
    existing.status = "inactive"
    existing.updated_at = now

    new_rule = Rule(
        name=body.name,
        description=body.description,
        type=body.type,
        status=body.status,
        rules_json=json.dumps(body.rules_json),
        created_at=now,
        updated_at=now,
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    return _rule_to_response(new_rule)


@router.delete("/api/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    existing = await db.get(Rule, rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    now = datetime.now(UTC).isoformat()
    existing.status = "inactive"
    existing.updated_at = now
    await db.commit()
