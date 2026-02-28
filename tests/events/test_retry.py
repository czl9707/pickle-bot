# tests/events/test_retry.py
from picklebot.server.delivery_worker import BACKOFF_MS, MAX_RETRIES, compute_backoff_ms


def test_backoff_first_retry():
    result = compute_backoff_ms(1)
    # First backoff should be around 5000ms with 20% jitter
    assert 4000 <= result <= 6000


def test_backoff_second_retry():
    result = compute_backoff_ms(2)
    # Second backoff should be around 25000ms with 20% jitter
    assert 20000 <= result <= 30000


def test_backoff_max():
    result = compute_backoff_ms(10)
    # Should cap at last backoff value
    assert 480000 <= result <= 720000  # 600000 +/- 20%


def test_backoff_zero():
    result = compute_backoff_ms(0)
    assert result == 0


def test_constants():
    assert BACKOFF_MS == [5000, 25000, 120000, 600000]
    assert MAX_RETRIES == 5
