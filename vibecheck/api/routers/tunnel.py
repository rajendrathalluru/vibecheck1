from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.tunnel_session import TunnelSession
from api.schemas.tunnel import TunnelSessionResponse, TunnelSessionListResponse
from api.services.tunnel_manager import tunnel_manager
from api.utils.errors import VibeCheckError

router = APIRouter(tags=["Tunnel"])


@router.websocket("/v1/tunnel")
async def tunnel_websocket(
    ws: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    await ws.accept()
    session_id = None
    try:
        data = await ws.receive_json()
        if data.get("type") != "connect" or "target_port" not in data:
            await ws.close(code=1008, reason="Expected connect message with target_port")
            return

        session_id = await tunnel_manager.register(ws, data["target_port"], db)
        await ws.send_json({"type": "session_created", "session_id": session_id})

        while True:
            msg = await ws.receive_json()
            await tunnel_manager.handle_message(session_id, msg, db)

    except WebSocketDisconnect:
        pass
    finally:
        if session_id:
            await tunnel_manager.unregister(session_id, db)


@router.get(
    "/v1/tunnel/sessions",
    response_model=TunnelSessionListResponse,
)
async def list_tunnel_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TunnelSession))
    sessions = result.scalars().all()
    return TunnelSessionListResponse(
        data=[TunnelSessionResponse.model_validate(s) for s in sessions]
    )


@router.get(
    "/v1/tunnel/sessions/{session_id}",
    response_model=TunnelSessionResponse,
)
async def get_tunnel_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TunnelSession, session_id)
    if not session:
        raise VibeCheckError.not_found("TunnelSession", session_id)
    return TunnelSessionResponse.model_validate(session)
