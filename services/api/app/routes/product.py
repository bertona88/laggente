from __future__ import annotations

from fastapi import APIRouter, Depends

from ..config import Settings
from ..dependencies import runtime_settings
from ..positioning import (
    PublicProductPositioning,
    load_product_positioning,
    public_product_positioning,
)

router = APIRouter(prefix="/product", tags=["product"])


@router.get("/positioning", response_model=PublicProductPositioning)
def get_product_positioning(
    settings: Settings = Depends(runtime_settings),
) -> PublicProductPositioning:
    """Return backend-owned audience and weighted vertical priorities for public clients."""
    return public_product_positioning(load_product_positioning(settings.product_positioning_json))
