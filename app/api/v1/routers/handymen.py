"""Handymen personnel discovery and lookup router."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.handyman import HandymanOut
from app.core.security.deps import RequireAuth
from app.core.services.handyman_service import HandymanService
from app.persistence.repositories.handyman_repo import HandymanRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/handymen", tags=["Handymen"])


def get_handyman_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HandymanService:
    return HandymanService(HandymanRepository(db))


@router.get(
    "/{handyman_id}",
    response_model=HandymanOut,
    summary="Get handyman details by ID",
)
async def get_handyman_by_id(
    handyman_id: UUID,
    ctx: RequireAuth,
    service: Annotated[HandymanService, Depends(get_handyman_service)],
) -> HandymanOut:
    handyman = await service.get_handyman(handyman_id)
    return HandymanOut.model_validate(handyman)

