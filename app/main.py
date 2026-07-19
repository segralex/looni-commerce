from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dependencies import get_marketplace_service, get_event_dispatcher
from app.middleware.logging import RequestLoggingMiddleware
from app.routes import listings_router, users_router, search_router, reservations_router
from app.routes.auth import router as auth_router
from app.routes.images import router as images_router
from infrastructure.logging.config import configure_logging

configure_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    dispatcher = get_event_dispatcher()
    dispatcher.start()
    try:
        yield
    finally:
        dispatcher.stop()


app = FastAPI(title="Looni Commerce", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
marketplace_service = get_marketplace_service()

# Mount all product routers under /api/v1
app.include_router(users_router, prefix="/api/v1")
app.include_router(listings_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(reservations_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(images_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "product": "Looni Commerce",
        "version": "0.1-alpha",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
