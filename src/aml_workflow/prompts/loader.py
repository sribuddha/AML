from __future__ import annotations

import pathlib

_PROMPT_DIR = pathlib.Path(__file__).parent

_TRIAGE_SYSTEM = (_PROMPT_DIR / "triage_system.txt").read_text()
_TRIAGE_USER = (_PROMPT_DIR / "triage_user.txt").read_text()
_TRIAGE_STAGE2_SYSTEM = (_PROMPT_DIR / "triage_stage2_system.txt").read_text()
_TRIAGE_STAGE3_SYSTEM = (_PROMPT_DIR / "triage_stage3_system.txt").read_text()


def get_triage_system() -> str:
    return _TRIAGE_SYSTEM


def get_triage_stage2_system() -> str:
    return _TRIAGE_STAGE2_SYSTEM


def get_triage_stage3_system() -> str:
    return _TRIAGE_STAGE3_SYSTEM


def render_triage_user(
    source_txn_id: str,
    account_id: str,
    customer_id: str,
    amount: float,
    counterparty: str,
    location: str,
    date: str,
    rules_flagged: int,
    rule_evidence: str,
) -> str:
    return _TRIAGE_USER.format(
        source_txn_id=source_txn_id,
        account_id=account_id,
        customer_id=customer_id,
        amount=amount,
        counterparty=counterparty,
        location=location,
        date=date,
        rules_flagged=rules_flagged,
        rule_evidence=rule_evidence,
    )
