from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api import (
    archive,
    auth,
    calculate,
    catalog,
    chains,
    compare,
    configurations,
    end_products,
    meta,
    roles,
    settings as settings_api,
    user_datasets,
    users,
)
from app.bootstrap import bootstrap
from app.config import ensure_data_dir, settings
from app.db import Base, SessionLocal, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dir(settings.database_url)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap(db)
    finally:
        db.close()
    yield


app = FastAPI(title="LCA-Tool", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.session_https_only,
    max_age=60 * 60 * 24 * 14,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(meta.router, prefix="/api/meta", tags=["meta"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(archive.router, prefix="/api/archive", tags=["archive"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])
app.include_router(roles.router, prefix="/api/roles", tags=["roles"])
app.include_router(end_products.router, prefix="/api/end-products", tags=["end-products"])
app.include_router(chains.router, prefix="/api/chains", tags=["chains"])
app.include_router(calculate.router, prefix="/api/calculate", tags=["calculate"])
app.include_router(configurations.router, prefix="/api/configurations", tags=["configurations"])
app.include_router(compare.router, prefix="/api/compare", tags=["compare"])
app.include_router(user_datasets.router, prefix="/api/user-datasets", tags=["user-datasets"])
app.include_router(users.router, prefix="/api/users", tags=["users"])


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
