from pydantic_settings import BaseSettings , SettingsConfigDict


from pydantic import Field

class AppSettings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env" ,extra="ignore" , env_ignore_empty=True)
    Database_Url:str
    Algorithm:str
    AccessSecret_Key:str 
    RefreshSecretKey:str
    ExpireAccessTokenTime:int
    ExpireRefreshTokenTime:int
    Development:bool
appsetting=AppSettings() #type:ignore