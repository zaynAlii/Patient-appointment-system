from fastapi import  APIRouter, Depends, HTTPException, status
from app.models.modal import UserIn  #type:ignore
from app.crud.auth_crud import authInstace  #type:ignore
from app.api.dependencies import Session_Dependency #type:ignore
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from app.api.dependencies import GET_ACCESS_TOKEN_USING_REFRESH_TOKEN


router:APIRouter= APIRouter()


@router.post("/user/sign-up")
async def User_registration(user_data:UserIn ,session:Session_Dependency ):
    
    response=await authInstace.user_reg(user_data , session)
    return response
@router.post("/user/login")
async def User_Login(user_data:Annotated[OAuth2PasswordRequestForm,Depends()] ,session:Session_Dependency ):
    
    response=await authInstace.user_login(user_data.username , user_data.password , session)
    return response


@router.post("/get-access-token/refresh-token")
def get_access_token_by_refreshToken(access_token :GET_ACCESS_TOKEN_USING_REFRESH_TOKEN ,session:Session_Dependency):
    
    if access_token:
        return {"status":status.HTTP_200_OK,"access_token":access_token}   







