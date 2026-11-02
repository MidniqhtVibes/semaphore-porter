"""All integration HTTP leaves the app through this fail-closed boundary."""
import httpx

from app.config import get_settings


def integration_client(service: str, **options) -> httpx.AsyncClient:
    if get_settings().demo_mode:
        from app.demo.simulator import handle_request
        # Explicit proxies and environment mounts must never override the mock.
        options.pop("proxy", None)
        options["trust_env"] = False
        options["transport"] = httpx.MockTransport(lambda request: handle_request(service, request))
    return httpx.AsyncClient(**options)
