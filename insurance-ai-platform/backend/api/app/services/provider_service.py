from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderHospital


async def list_providers(db: AsyncSession) -> list[ProviderHospital]:
    result = await db.execute(
        select(ProviderHospital).where(ProviderHospital.is_active.is_(True)).order_by(ProviderHospital.name)
    )
    return list(result.scalars().all())
