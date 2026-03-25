from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.database import init_db
from app.routers import pages, api_study, api_quiz, api_analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="FL 2-15 Study Tool", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.include_router(pages.router)
app.include_router(api_study.router)
app.include_router(api_quiz.router)
app.include_router(api_analytics.router)
