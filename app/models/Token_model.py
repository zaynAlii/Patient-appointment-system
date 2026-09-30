from sqlmodel import SQLModel

from datetime import datetime
class TokenPlayload(SQLModel):
    access_token:str
    refresh_token:str
    user:dict[str,str]
    
class TokenDecodePayload(SQLModel):
    id:str
    email:str
    username:str
    first_name:str
    last_name:str
    role:str    
    jti:str
    exp:datetime