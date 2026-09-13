from pydantic import BaseModel, Field


class RequestInfoCreate(BaseModel):
    message: str = Field(..., min_length=1, description="What additional information is needed from the member.")
