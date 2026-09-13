import uuid

from pydantic import BaseModel, Field


class RequestInfoCreate(BaseModel):
    requested_by: uuid.UUID
    message: str = Field(..., min_length=1, description="What additional information is needed from the member.")
