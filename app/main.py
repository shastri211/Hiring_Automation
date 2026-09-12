import app.models
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs, resumes, health, integration, candidates, emails
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()

from contextlib import asynccontextmanager
from app.services.queue import queue_service
import logging
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger(__name__)
    logger.info("Starting up Resume Screener API...")
    await queue_service.init_stream()
    yield
    logger.info("Shutting down Resume Screener API...")

app = FastAPI(
    title="Resume Screener API",
    description="AI-powered semantic resume screening with Qdrant + Groq/Gemini",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(integration.router, prefix="/integration", tags=["integration"])
app.include_router(candidates.router, prefix="/candidates", tags=["candidates"])
app.include_router(emails.router, prefix="/emails", tags=["emails"])
