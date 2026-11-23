from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import redis_client
from app.api.v1 import api_router
from app.api.websockets import router as ws_router
from app.core.config import settings
from app.core.errors import CleanDeskException
from app.db.base import Base
from app.db.session import engine
# Import models so Base.metadata knows about all tables and composite indexes
import app.models  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan:
    1. Initializes PostgreSQL tables and composite indexes on startup.
    2. Verifies Redis connectivity with graceful degradation.
    3. Closes engine and Redis connection on shutdown.
    """
    logger.info("Initializing database tables and composite indexes...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schemas ready.")

    # Check Redis connectivity
    try:
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
    except Exception as exc:
        logger.warning(f"Redis is currently unreachable: {exc}. Graceful degradation active.")

    yield

    # Shutdown cleanup
    logger.info("Shutting down resources...")
    await engine.dispose()
    await redis_client.close()
    logger.info("Resources released.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="CleanDesk AI - Multi-Tenant Merchant Inventory & Real-Time Operations Platform",
    lifespan=lifespan
)

# 1. Enable CORS for local and containerized frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Structured CleanDesk Exception Handler
@app.exception_handler(CleanDeskException)
async def cleandesk_exception_handler(request: Request, exc: CleanDeskException):
    """Ensures CleanDesk's exact JSON error structure is returned."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )


# 3. Mount REST API Routes
# Mounts both /api/v1/... and direct /... (e.g., /auth/login and /api/v1/auth/login both work)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router)

# 4. Mount Real-Time WebSocket Endpoint (/ws/merchant)
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}