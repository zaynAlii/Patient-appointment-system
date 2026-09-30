from app.core.app_setting import appsetting  #type:ignore
from   sqlmodel import SQLModel
from app.models import modal #type:ignore
from sqlalchemy.ext.asyncio import AsyncEngine
DATABASE_URL:str=appsetting.Database_Url


from sqlalchemy.ext.asyncio import AsyncEngine , create_async_engine , async_sessionmaker , AsyncSession

engine :AsyncEngine= create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=3600
)


AsyncSessionLocal=async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def create_tables()->None:
   async with engine.begin() as con:
       await con.run_sync(
           lambda sync_conn:SQLModel.metadata.create_all(sync_conn)
       )
              



    


