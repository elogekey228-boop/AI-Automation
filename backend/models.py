from pydantic import BaseModel, EmailStr
from typing import Optional


class Lead(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    need: str
    budget: Optional[float] = None
    urgency: Optional[str] = "medium" 
