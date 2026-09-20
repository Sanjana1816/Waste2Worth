import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import accounts, ai, donations, listings, meta, pools
from app.services.validation import ValidationFailed


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Keep serving even if the database is briefly unreachable; it is retried on the next request,
    # so a blip in the managed database never takes the whole deployment down.
    if not init_db():
        logging.getLogger("app").error("Starting without a database connection; will retry on requests.")
    yield


app = FastAPI(
    title="Waste2Worth API",
    description="Reuse · Recycle · Resell · Donate. Snap your waste, and we'll route it to someone who can use it.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_origin_regex=settings.cors_origin_regex,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ValidationFailed)
async def validation_failed(_: Request, exc: ValidationFailed):
    return JSONResponse(status_code=422, content={"detail": exc.errors})


for r in (listings.router, pools.router, donations.router, ai.router, meta.router, accounts.router):
    app.include_router(r)

if settings.storage_backend == "local":
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}
