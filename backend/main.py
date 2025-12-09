from __future__ import annotations

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .app_logging import configure_logging
from .api.v1.routers import history, jobs, uploads

load_dotenv()
configure_logging()

app = FastAPI(title="Recon AI 2.0 Backend", version="0.1.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(history.router)

app.include_router(api_router)
