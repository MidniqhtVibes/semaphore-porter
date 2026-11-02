"""An in-process ASGI sandbox; no second listener, process, volume or service.

Context variables survive sync dependencies and streaming responses. The outer
portal always retains its original settings, database and signing keys.
"""
from threading import RLock
import asyncio
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings, settings_context
from app.database import session_context, demo_gate_context


class DemoApplication:
    def __init__(self, application, parent_settings):
        self.application = application
        self.settings = Settings(
            _env_file=None, demo_mode=True, database_url="sqlite+pysqlite:///:memory:",
            portal_cookie_secure=parent_settings.portal_cookie_secure,
            portal_allowed_hosts=parent_settings.portal_allowed_hosts,
            portal_session_hours=1, demo_enabled=True,
        )
        # A named shared-memory database gives each request its own connection;
        # closing an SSE reader must never roll back another request's session.
        uri = f"sqlite+pysqlite:///file:semaporter-demo-{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true"
        self.engine = create_engine(uri,
            connect_args={"check_same_thread": False}, poolclass=NullPool)
        self.anchor = self.engine.connect()  # Keep memory alive between requests.
        self.sessions = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.initialized = False
        self.lock = RLock()
        self.gate = None
        self.loop = None

    async def __call__(self, scope, receive, send):
        loop = asyncio.get_running_loop()
        if self.loop is not loop:
            self.gate, self.loop = asyncio.Lock(), loop
        gate = self.gate
        await gate.acquire()
        held = True
        async def scoped_send(message):
            nonlocal held
            if message["type"] == "http.response.start" and any(
                key.lower() == b"content-type" and b"text/event-stream" in value
                for key, value in message.get("headers", [])
            ):
                # Streaming polls take individual turns; other demo requests
                # (including task stop/reset) remain usable while a stream lives.
                gate.release()
                held = False
            await send(message)
        settings_token = settings_context.set(self.settings)
        sessions_token = session_context.set(self.sessions)
        gate_token = demo_gate_context.set(gate)
        try:
            with self.lock:
                if not self.initialized:
                    from app.demo.seed import initialize
                    initialize()
                    self.initialized = True
            await self.application(scope, receive, scoped_send)
        finally:
            if held:
                gate.release()
            demo_gate_context.reset(gate_token)
            session_context.reset(sessions_token)
            settings_context.reset(settings_token)
