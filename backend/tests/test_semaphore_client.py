import asyncio

import httpx
import pytest
import respx

from app.semaphore_client import SemaphoreClient, SemaphoreConnection, SemaphoreError
from app.schemas import SemaphoreSettingsInput


def test_project_list_normalization_accepts_known_shapes():
    expected = [{"id": 2, "name": "A"}, {"id": 3, "name": "B"}]
    assert SemaphoreClient.normalize_projects(expected) == expected
    assert SemaphoreClient.normalize_projects({"data": expected}) == expected
    assert SemaphoreClient.normalize_projects([[expected[0]], [expected[1]]]) == expected


def test_post_redirect_is_not_followed_or_retried():
    client = SemaphoreClient(SemaphoreConnection("https://semaphore.example", "token"))
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://semaphore.example/api/project/1/tasks").mock(
            return_value=httpx.Response(307, headers={"Location": "/api/project/1/tasks"})
        )
        with pytest.raises(SemaphoreError) as error:
            asyncio.run(client.start_task(1, 2, {"tenant_slug": "kunde-a"}))
        assert error.value.uncertain
        assert route.call_count == 1


def test_task_payload_contains_only_given_validated_environment():
    client = SemaphoreClient(SemaphoreConnection("https://semaphore.example", "token"))
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://semaphore.example/api/project/7/tasks").mock(
            return_value=httpx.Response(201, json={"id": 91, "status": "waiting"})
        )
        result = asyncio.run(client.start_task(7, 12, {"tenant_slug": "kunde-a", "ttl_minutes": 60}))
        assert result["id"] == 91
        body = route.calls[0].request.read().decode()
        assert '"template_id":12' in body.replace(" ", "")
        assert "kunde-a" in body


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_url", "https://user:password@semaphore.example"),
        ("proxy_url", "http://user:password@proxy.example:8080"),
    ],
)
def test_settings_reject_credentials_embedded_in_urls(field, value):
    values = {"base_url": "https://semaphore.example", "token": "service-token", "proxy_url": None}
    values[field] = value
    with pytest.raises(ValueError, match="Zugangsdaten"):
        SemaphoreSettingsInput(**values)
