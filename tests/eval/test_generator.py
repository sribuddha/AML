"""Tests for the fraud pattern generator's individual pattern functions."""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.test_generate_fraud_data import (
    generate_structuring_set,
    generate_velocity_set,
    generate_impossible_travel_pair,
    generate_round_trip_pair,
    generate_watchlist_row,
)


ACCT = "ACC001"
CUST = "CUST001"


class TestStructuringSet:
    def test_returns_multiple_transactions(self):
        rows = generate_structuring_set(ACCT, CUST, 30)
        assert 3 <= len(rows) <= 5
        for row in rows:
            assert row["ground_truth"] == "structuring"
            assert 9500 <= float(row["amount"]) <= 9990
            assert row["account_id"] == ACCT

    def test_all_same_account(self):
        rows = generate_structuring_set(ACCT, CUST, 30)
        accts = {r["account_id"] for r in rows}
        assert accts == {ACCT}


class TestVelocitySet:
    def test_returns_multiple_transactions(self):
        rows = generate_velocity_set(ACCT, CUST, 120)
        assert 5 <= len(rows) <= 8
        for row in rows:
            assert row["ground_truth"] == "velocity"
            assert row["account_id"] == ACCT


class TestImpossibleTravelPair:
    def test_returns_two_transactions(self):
        rows = generate_impossible_travel_pair(ACCT, CUST, 10)
        assert len(rows) == 2
        for row in rows:
            assert row["ground_truth"] == "impossible_travel"
        # Different locations
        assert rows[0]["location"] != rows[1]["location"]


class TestRoundTripPair:
    def test_returns_two_transactions(self):
        rows = generate_round_trip_pair(ACCT, CUST, 15)
        assert len(rows) == 2
        for row in rows:
            assert row["ground_truth"] == "round_trip"
        assert rows[0]["counterparty"] == rows[1]["counterparty"]
        # Return amount is slightly less
        outbound = float(rows[0]["amount"])
        inbound = float(rows[1]["amount"])
        assert 0.99 * outbound <= inbound <= outbound


class TestWatchlistRow:
    def test_returns_single_transaction(self):
        row = generate_watchlist_row(ACCT, CUST, 5)
        assert isinstance(row, dict)
        assert row["ground_truth"] == "watchlist"
        assert row["account_id"] == ACCT
