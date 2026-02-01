from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    email: str
    is_active: bool

    class Config:
        orm_mode = True
