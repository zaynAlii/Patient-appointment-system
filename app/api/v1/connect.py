from fastapi import APIRouter 
from app.api.v1.Route import auth #type:ignore
from app.api.v1.Route import user
connect:APIRouter=APIRouter()


connect.include_router(auth.router , prefix='/auth' , tags=['Auth'])
connect.include_router(user.router ,  tags=['Doctor'])
