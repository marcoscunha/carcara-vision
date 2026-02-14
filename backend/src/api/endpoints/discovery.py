from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel

from ...core.security import AuthenticatedUser
from ...services.discovery import DiscoveryService

router = APIRouter()


class DiscoveredCamera(BaseModel):
    ip: str
    name: str | None = None
    rtsp_url: str | None = None
    protocol: str


@router.get("/cameras", response_model=list[DiscoveredCamera])
async def discover_cameras(
    current_user: AuthenticatedUser,
    protocol: str = Query("mdns", pattern="^(mdns|onvif|both)$"),
    timeout: float = Query(3.0, ge=0.5, le=10.0),
    discovery_service: DiscoveryService = Depends(DiscoveryService),
) -> list[DiscoveredCamera]:
    """
    Discover network cameras using mDNS and/or ONVIF WS-Discovery.

    Args:
        protocol: "mdns", "onvif", or "both"
        timeout: discovery timeout in seconds
    """
    try:
        cameras = await discovery_service.scan(protocol=protocol, timeout=timeout)
        return [DiscoveredCamera(**camera) for camera in cameras]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to discover cameras: {exc!s}")
