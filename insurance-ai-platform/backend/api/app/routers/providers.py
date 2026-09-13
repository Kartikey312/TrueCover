from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.provider import ProviderRead
from app.services import provider_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderRead])
async def list_providers(db: AsyncSession = Depends(get_db)):
    return await provider_service.list_providers(db)
