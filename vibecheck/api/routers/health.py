from fastapi import APIRouter

from api.services.tunnel_manager import tunnel_manager

router = APIRouter(tags=["Health"])


@router.get("/v1/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "active_tunnels": len(tunnel_manager.active_connections),
        "agents_available": True,
    }
