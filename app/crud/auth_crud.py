from app.models.modal import UserIn, User   #type:ignore
from sqlalchemy.ext.asyncio import AsyncSession 
from fastapi import HTTPException , status
from sqlmodel import select
from app.api.dependencies import hash_password , verify_password  , create_access_token , create_refresh_token #type:ignore
from app.core.app_setting import appsetting  #type:ignore
from app.models.Token_model import TokenPlayload #type:ignore
from datetime import timedelta
class AuthCrud():
    
    async def __check_user_exist(self,username:str , email:str,session:AsyncSession ):
        # print("Hello g ")
        # return  1 , 2 
        user:User|None = (await session.execute(
            select(User).where(User.username == username)
        )).scalar_one_or_none()
        # print('HelloBG Is ',user)
        # return 
        if not user :
            user_e:User|None = (await session.execute(
                select(User).where(User.email == email)
            )).scalar_one_or_none()
            if not user_e:
                return False , "ok"
            else:
                return True , "email_exist"
        else :    
           return True  ,"username_exist"  # True means user exist with username or email
    async def user_reg(self,user:UserIn , session:AsyncSession):
      try:  
        
        exist_bool,exist_str = await self.__check_user_exist(user.username, user.email, session)
        if not exist_bool and exist_str =="ok":
            hsh_pswd=hash_password(user.password)
            
            R_User:User=User.model_validate(
                user , update={'password_hash':hsh_pswd , 'role':'doctor'}
            )
            
            session.add(R_User)
            await session.commit()
            await session.refresh(R_User)
            access_token_expire_time:str = appsetting.ExpireAccessTokenTime
            refresh_token_expire_time:str=appsetting.ExpireRefreshTokenTime
            
            data_dict:dict[str,str] = {
                'id':str(R_User.id),
                'email':R_User.email,
                'username':R_User.username,
                'first_name':R_User.first_name,
                'last_name':R_User.last_name,
                'role':'doctor'
            }
            
            access_token=create_access_token(data_dict , expires_delta=timedelta(hours=int(access_token_expire_time)))
            refresh_token=create_refresh_token(data_dict , expires_delta=timedelta(days=int(refresh_token_expire_time)))
            
            token_Paylaod:TokenPlayload=TokenPlayload(
                access_token=access_token,
                refresh_token=refresh_token,
                user={
                    'id':str(R_User.id),
                    'email':R_User.email,
                    'first_name':R_User.first_name,
                    'last_name':R_User.last_name
                }
            )
            
            # print(token_Paylaod)
            return token_Paylaod
      except HTTPException :
          raise 
      except Exception as e:
          print(f"DEBUG: Real error was: {e}") 
          raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something unexpected happened at sign up "
        )
    
    async def __Authenticate_user(self,username:str,password:str,session:AsyncSession):
       ...
       user:User |None = (await session.execute(
           select(User).where(User.username == username)
       )).scalar_one_or_none()
       if not user:
           raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                               detail="UserName is incorrect. User not found!")
       
       if not verify_password(password , user.password_hash):
           raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                               detail="Invalid username and Password") 
       return user    
    
    async def user_login(self , username:str , password:str , session :AsyncSession):
        try:
             R_User:User = await self.__Authenticate_user(username, password, session)
             if R_User :
                    access_token_expire_time:str = appsetting.ExpireAccessTokenTime
                    refresh_token_expire_time:str=appsetting.ExpireRefreshTokenTime
                    
                    data_dict:dict[str,str] = {
                        'id':str(R_User.id),
                        'email':R_User.email,
                        'first_name':R_User.first_name,
                        'last_name':R_User.last_name,
                        'role':'doctor'
                    }
                    
                    access_token=create_access_token(data_dict , expires_delta=timedelta(hours=int(access_token_expire_time)))
                    refresh_token=create_refresh_token(data_dict , expires_delta=timedelta(days=int(refresh_token_expire_time)))
                    
                    token_Paylaod:TokenPlayload=TokenPlayload(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        user={
                            'id':str(R_User.id),
                            'email':R_User.email,
                            'first_name':R_User.first_name,
                            'last_name':R_User.last_name
                        }
                    )
                    return token_Paylaod
                 
        
        except HTTPException :
            raise
        
        except Exception as e:
            print(f"DEBUG: Real error was: {e}") 
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Something unexpected happened at login"
            )        
        
        
        
authInstace=AuthCrud()        
        
        
        
        
        
        
        
        

        
        
        