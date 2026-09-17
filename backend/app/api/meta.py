from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.constants import INDICATORS
from app.deps import CurrentUser
from app.services.characterize import method_available

router = APIRouter()


@router.get("/indicators")
def indicators(_user: CurrentUser) -> list[dict[str, str]]:
    return INDICATORS


@router.get("/public")
def public_info() -> dict:
    return {
        "public_signup": settings.public_signup,
        "language": "de",
        "lcia_available": method_available(),
    }
