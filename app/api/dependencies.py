from app.core.db_setting  import AsyncSessionLocal #type:ignore
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends , HTTPException
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from datetime import timedelta , datetime , timezone
from app.core.app_setting import appsetting #type:ignore
import jwt
from jwt import ExpiredSignatureError
from app.models.Token_model import TokenDecodePayload #type:ignore
from app.models.modal import User #type:ignore
import uuid
from uuid import UUID

from fastapi import status , HTTPException
schema_oauth2=OAuth2PasswordBearer(tokenUrl="/api/v1/login")

TOKEN_DEPS=Annotated[str, Depends(schema_oauth2)]

async def get_session():
    try:
        async with AsyncSessionLocal() as session:
            yield session
    except HTTPException :
        raise
    except Exception as e:
        raise


Session_Dependency=Annotated[AsyncSession,Depends(get_session)]            
        
password_hash=PasswordHash.recommended()        

def hash_password(password:str):
    return password_hash.hash(password)

def verify_password(passowrd:str , hashed_pswd:str):
    return password_hash.verify(passowrd , hashed_pswd)
        
def create_access_token(data:dict[str ,str|int|datetime] , expires_delta:timedelta|None=None):
    to_encode = data.copy()
    jti:str=str(uuid.uuid4())
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire , 'jti':jti})
    encoded_jwt = jwt.encode(to_encode,appsetting.AccessSecret_Key, algorithm=appsetting.Algorithm)
    return encoded_jwt    

def create_refresh_token(data:dict[str ,str|datetime] , expires_delta:timedelta|None=None):
    to_encode = data.copy()
    jti=str(uuid.uuid4())
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire , 'jti':jti})
    encoded_jwt = jwt.encode(to_encode,appsetting.RefreshSecretKey, algorithm=appsetting.Algorithm)
    return encoded_jwt    

def verify_token_signature(token:TOKEN_DEPS):

    try:
        payload = jwt.decode(
            token,
            appsetting.AccessSecret_Key,
            algorithms=[appsetting.Algorithm],
        )
        if payload.get("role") != "doctor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only doctors can create a doctor profile",
            )
        user_id = UUID(str(payload["id"]))
        return user_id
    except HTTPException:
        raise
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid access token",
		) from error

Get_Doctor_id=Annotated[UUID , Depends(verify_token_signature)]    



async def verify_refresh_Token(token:TOKEN_DEPS , session:Session_Dependency):
    credential_Exception=HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
             detail="Could not validate Credentials ",
            headers={"WWW-Authenticate":"Bearer"}
        )
    
    try:
        
        payload_data=jwt.decode(token , appsetting.RefreshSecretKey ,algorithms=[appsetting.algorithm])
        payload_model :TokenDecodePayload= TokenDecodePayload.model_validate(payload_data)
        
        if not payload_model.id or not payload_model.username:
            raise credential_Exception
        
        try:
            user_id:UUID=UUID(payload_model.id)
        except (ValueError , TypeError):
            raise credential_Exception
        
        R_User:User|None=await session.get(User , user_id)
        if not R_User:
            raise     HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User Not Found"
            )
        
        
        # if payload_model.type == "refresh":
        # jti=payload_model.jti
        
        # if not User_is.haveRefreshToken:
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail=f"No active refresh token found for user"
        #     )
        
        # user_jti_in_db=User_is.haveRefreshToken.jti
        
        # if jti == user_jti_in_db :
            
        access_token_expired_time=appsetting.ExpireAccessTokenTime
        
        user_data_to_encode:dict[str , str|int|datetime] = {
            # "id":payload_model.id,
            # "username":payload_model.username,
            # "email":payload_model.email
            'id':str(R_User.id),
            'email':R_User.email,
            'username':R_User.username,
            'first_name':R_User.first_name,
            'last_name':R_User.last_name,
            'role':'doctor'
        }
        
        user_acceess_token_is=create_access_token(user_data_to_encode , timedelta(hours=access_token_expired_time))
        return user_acceess_token_is         
        
        # else :
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Invalid Refresh token(token mis_matched)"
        #     )
            
            
        # elif payload_model.type =="access":
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST , 
        #         detail=f"you cant get an access token using an access token .  use a refresh token"
        #     )    
    
    
    
    except  ExpiredSignatureError:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been expired, Please LogIn Again"
        )    
         
           
    except (InvalidTokenError , Exception ) :
        raise  credential_Exception 
    
GET_ACCESS_TOKEN_USING_REFRESH_TOKEN=Annotated[str , Depends(verify_refresh_Token)]    