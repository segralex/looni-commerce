from __future__ import annotations

from fastapi import FastAPI

from app.dependencies import get_marketplace_service
from app.routes import listings_router, users_router, search_router

app = FastAPI(title="Looni Commerce")
marketplace_service = get_marketplace_service()
app.include_router(users_router)
app.include_router(listings_router)
app.include_router(search_router)


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
