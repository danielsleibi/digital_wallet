import datetime
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., max_length=150)
    last_name: str = Field(..., max_length=150)

class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    
class RefreshIn(BaseModel):
    refresh_token: str
    
class AccessTokenOut(BaseModel):
    access_token: str

from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    email: str
    first_name: str
    last_name: str
    date_joined: datetime.datetime

class ErrorOut(BaseModel):
    detail: str
