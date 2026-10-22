from pydantic import BaseModel, EmailStr
from typing import Optional, List

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    full_name: str
    role: str
    department: Optional[str] = None
    permissions: List[str] = []

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: EmailStr
    role: str
    department: Optional[str] = None
    consultation_fee: int = 500

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    department: Optional[str] = None
    consultation_fee: int
    permissions: List[str] = []

    class Config:
        from_attributes = True

