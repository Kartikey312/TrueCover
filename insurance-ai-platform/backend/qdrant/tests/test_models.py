from datetime import date, datetime, timezone

from qdrant.models import effective_date_to_ts


def test_effective_date_to_ts_matches_utc_midnight():
    d = date(2026, 1, 1)
    expected = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    assert effective_date_to_ts(d) == expected


def test_effective_date_to_ts_orders_correctly():
    assert effective_date_to_ts(date(2025, 1, 1)) < effective_date_to_ts(date(2026, 1, 1))
