from typing import TypeVar, Generic, Optional
from pydantic import BaseModel

T = TypeVar('T')

class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str