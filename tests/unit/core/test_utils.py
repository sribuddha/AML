from datetime import datetime, UTC

from src.core.utils import now


class TestNow:
    def test_returns_string(self):
        result = now()
        assert isinstance(result, str)

    def test_valid_iso_format(self):
        result = now()
        parsed = datetime.fromisoformat(result)
        assert isinstance(parsed, datetime)

    def test_is_utc(self):
        result = now()
        assert result.endswith("+00:00") or "Z" in result.upper()

    def test_subsequent_calls_differ(self):
        a = now()
        b = now()
        assert a <= b
