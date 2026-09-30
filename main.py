from fastapi import FastAPI 
from app.api.v1 import connect
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse
from app.core.db_setting import create_tables
@asynccontextmanager
async def lifespan(app:FastAPI):
    
    await create_tables()
    yield    

app:FastAPI = FastAPI(lifespan=lifespan)


app.include_router(connect.connect , prefix='/api/v1')

@app.get("/")
def ToDocs()->RedirectResponse:
    return RedirectResponse(url="/docs")
