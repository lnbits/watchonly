from fastapi import APIRouter

from .crud import db
from .views import watchonly_generic_router
from .views_api import watchonly_api_router

watchonly_static_files = [
    {
        "path": "/watchonly/static",
        "name": "watchonly_static",
    }
]

watchonly_ext: APIRouter = APIRouter(prefix="/watchonly", tags=["watchonly"])
watchonly_ext.include_router(watchonly_generic_router)
watchonly_ext.include_router(watchonly_api_router)

__all__ = ["watchonly_ext", "watchonly_static_files", "db"]
