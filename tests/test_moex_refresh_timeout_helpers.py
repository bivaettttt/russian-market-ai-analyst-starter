import httpx
import pytest

from app.services import moex_data_bootstrap as bootstrap


class _TimeoutClient:
    def get(self, *_args, **_kwargs):
        raise httpx.ConnectTimeout("ssl handshake timed out")


def test_fetch_json_uses_bounded_retries_and_reports_attempts():
    with pytest.raises(RuntimeError) as exc:
        bootstrap._fetch_json(
            _TimeoutClient(),
            "https://example.test",
            {},
            request_timeout=0.1,
            max_retries=1,
            retry_backoff=0,
        )

    message = str(exc.value)
    assert "MOEX request failed after 2 attempts" in message
    assert "ConnectTimeout" in message


def test_request_timeout_has_connect_and_read_limits():
    timeout = bootstrap._request_timeout(5)

    assert timeout.connect == 5
    assert timeout.read == 5
