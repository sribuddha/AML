"""Tests for confidence calibration computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.aml_workflow.eval.calibration import compute_calibration


@dataclass
class FakeSAR:
    transaction_id: str
    llm_confidence: float | None = None


@dataclass
class FakeTxn:
    id: str
    source_txn_id: str


@dataclass
class FakeVR:
    transaction_id: str
    status: str = "flagged"
    risk_level: str = "high"


def test_calibration_returns_10_bins():
    sars = [FakeSAR(transaction_id="t1", llm_confidence=0.85)]
    txn_by_id = {"t1": FakeTxn(id="t1", source_txn_id="TXN001")}
    vr_map = {"t1": FakeVR(transaction_id="t1", risk_level="high")}
    expected = {"TXN001": {"expected_escalate": True}}
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    assert len(result) == 10


def test_calibration_skips_none_confidence():
    sars = [FakeSAR(transaction_id="t1", llm_confidence=None)]
    txn_by_id = {"t1": FakeTxn(id="t1", source_txn_id="TXN001")}
    vr_map = {"t1": FakeVR(transaction_id="t1", risk_level="high")}
    expected = {"TXN001": {"expected_escalate": True}}
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    assert sum(b["count"] for b in result) == 0


def test_calibration_skips_missing_txn():
    sars = [FakeSAR(transaction_id="orphan", llm_confidence=0.5)]
    txn_by_id: dict[str, Any] = {}
    vr_map: dict[str, Any] = {}
    expected: dict[str, Any] = {}
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    assert sum(b["count"] for b in result) == 0


def test_calibration_correct_prediction():
    sars = [FakeSAR(transaction_id="t1", llm_confidence=0.9)]
    txn_by_id = {"t1": FakeTxn(id="t1", source_txn_id="TXN001")}
    vr_map = {"t1": FakeVR(transaction_id="t1", risk_level="high")}
    expected = {"TXN001": {"expected_escalate": True}}
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    bin_9 = result[9]
    assert bin_9["count"] == 1
    assert bin_9["accuracy"] == 1.0
    assert bin_9["avg_confidence"] == 0.9


def test_calibration_incorrect_prediction():
    sars = [FakeSAR(transaction_id="t1", llm_confidence=0.9)]
    txn_by_id = {"t1": FakeTxn(id="t1", source_txn_id="TXN001")}
    vr_map = {"t1": FakeVR(transaction_id="t1", risk_level="high")}
    expected = {"TXN001": {"expected_escalate": False}}
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    bin_9 = result[9]
    assert bin_9["count"] == 1
    assert bin_9["accuracy"] == 0.0


def test_calibration_auto_reviewed_not_escalated():
    sars = [FakeSAR(transaction_id="t1", llm_confidence=0.3)]
    txn_by_id = {"t1": FakeTxn(id="t1", source_txn_id="TXN001")}
    vr_map = {"t1": FakeVR(transaction_id="t1", risk_level="auto_reviewed")}
    expected = {"TXN001": {"expected_escalate": False}}
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    bin_3 = result[3]
    assert bin_3["count"] == 1
    assert bin_3["accuracy"] == 1.0


def test_calibration_multiple_sars_correct_binning():
    sars = [
        FakeSAR(transaction_id="t1", llm_confidence=0.05),
        FakeSAR(transaction_id="t2", llm_confidence=0.55),
        FakeSAR(transaction_id="t3", llm_confidence=0.95),
    ]
    txn_by_id = {
        "t1": FakeTxn(id="t1", source_txn_id="TXN001"),
        "t2": FakeTxn(id="t2", source_txn_id="TXN002"),
        "t3": FakeTxn(id="t3", source_txn_id="TXN003"),
    }
    vr_map = {
        "t1": FakeVR(transaction_id="t1", risk_level="auto_reviewed"),
        "t2": FakeVR(transaction_id="t2", risk_level="high"),
        "t3": FakeVR(transaction_id="t3", risk_level="high"),
    }
    expected = {
        "TXN001": {"expected_escalate": False},
        "TXN002": {"expected_escalate": True},
        "TXN003": {"expected_escalate": True},
    }
    result = compute_calibration(sars, txn_by_id, vr_map, expected)
    assert result[0]["count"] == 1  # bin 0: 0.05
    assert result[5]["count"] == 1  # bin 5: 0.55
    assert result[9]["count"] == 1  # bin 9: 0.95
    assert result[0]["accuracy"] == 1.0  # correct: not escalated
    assert result[5]["accuracy"] == 1.0  # correct: escalated
    assert result[9]["accuracy"] == 1.0  # correct: escalated
