import asyncio
from datetime import datetime, timezone

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.tunnel_session import TunnelSession
from api.utils.errors import VibeCheckError
from api.utils.id_generator import generate_id


class TunnelManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.pending_requests: dict[str, asyncio.Future] = {}

    async def register(
        self, ws: WebSocket, target_port: int, db: AsyncSession
    ) -> str:
        session = TunnelSession(target_port=target_port)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        self.active_connections[session.id] = ws
        return session.id

    async def unregister(self, session_id: str, db: AsyncSession):
        self.active_connections.pop(session_id, None)
        session = await db.get(TunnelSession, session_id)
        if session:
            session.status = "disconnected"
            await db.commit()

    def is_connected(self, session_id: str) -> bool:
        return session_id in self.active_connections

    async def proxy_request(
        self,
        session_id: str,
        method: str,
        path: str,
        headers: dict = None,
        body: str = None,
    ) -> dict:
        ws = self.active_connections.get(session_id)
        if not ws:
            raise VibeCheckError.tunnel_not_connected()

        request_id = generate_id("req")
        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future

        await ws.send_json(
            {
                "type": "http_request",
                "request_id": request_id,
                "method": method,
                "path": path,
                "headers": headers or {},
                "body": body,
            }
        )

        try:
            response = await asyncio.wait_for(future, timeout=15.0)
            return response
        except asyncio.TimeoutError:
            raise VibeCheckError.target_unreachable()
        finally:
            self.pending_requests.pop(request_id, None)

    async def handle_message(
        self, session_id: str, data: dict, db: AsyncSession
    ):
        if data.get("type") == "http_response":
            request_id = data.get("request_id")
            future = self.pending_requests.get(request_id)
            if future and not future.done():
                future.set_result(data)
        elif data.get("type") == "pong":
            session = await db.get(TunnelSession, session_id)
            if session:
                session.last_heartbeat = datetime.now(timezone.utc)
                await db.commit()


tunnel_manager = TunnelManager()
