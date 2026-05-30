from datetime import datetime, timedelta, UTC

from src.core.metrics import compute_velocity_zscore


class TestComputeVelocityZscore:
    def test_empty_list_returns_none(self):
        ref = datetime.now(UTC)
        assert compute_velocity_zscore([], ref) is None

    def test_no_historical_data_returns_none(self):
        ref = datetime(2026, 6, 1, tzinfo=UTC)
        dates = [ref.isoformat()]
        assert compute_velocity_zscore(dates, ref) is None

    def test_avg_weekly_zero_returns_none(self):
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        dates = [datetime(2026, 6, 10, tzinfo=UTC).isoformat()]
        result = compute_velocity_zscore(dates, ref)
        assert result is None

    def test_higher_than_average_positive_zscore(self):
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        dates = [
            (ref - timedelta(days=d)).isoformat()
            for d in [1, 2, 3, 4, 5, 6, 7]
        ]
        dates += [
            (ref - timedelta(days=d)).isoformat()
            for d in [14, 21, 28]
        ]
        result = compute_velocity_zscore(dates, ref)
        assert result is not None
        assert result > 0

    def test_lower_than_average_negative_zscore(self):
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        dates = [
            (ref - timedelta(days=3)).isoformat(),
        ] + [
            (ref - timedelta(days=d)).isoformat()
            for d in [10, 11, 12, 13, 17, 18, 19, 20, 24, 25, 26, 27]
        ]
        result = compute_velocity_zscore(dates, ref)
        assert result is not None
        assert result < 0

    def test_bad_date_string_skipped(self):
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        dates = ["not-a-date", datetime(2026, 6, 10, tzinfo=UTC).isoformat()]
        result = compute_velocity_zscore(dates, ref)
        assert result is None

    def test_all_bad_date_strings_return_none(self):
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        assert compute_velocity_zscore(["garbage", None, ""], ref) is None

    def test_boundary_7_days_ago(self):
        ref = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
        dates = [
            (ref - timedelta(hours=1)).isoformat(),
            (ref - timedelta(days=7)).isoformat(),
            (ref - timedelta(days=8)).isoformat(),
            (ref - timedelta(days=14)).isoformat(),
        ]
        result = compute_velocity_zscore(dates, ref)
        assert result is not None

    def test_activity_in_prior_weeks_only(self):
        ref = datetime(2026, 6, 15, tzinfo=UTC)
        dates = [
            (ref - timedelta(days=10)).isoformat(),
            (ref - timedelta(days=11)).isoformat(),
        ]
        result = compute_velocity_zscore(dates, ref)
        assert result is None
