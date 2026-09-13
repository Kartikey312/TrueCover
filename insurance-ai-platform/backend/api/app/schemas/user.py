import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole


class AdjusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    full_name: str
    email: str
    role: UserRole
