import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import NetworkStatus, ProviderType


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: uuid.UUID
    name: str
    provider_type: ProviderType
    network_status: NetworkStatus
