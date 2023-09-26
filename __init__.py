from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer

db = Database("ext_watchonly")

watchonly_static_files = [
    {
        "path": "/watchonly/static",
        "name": "watchonly_static",
    }
]

watchonly_ext: APIRouter = APIRouter(prefix="/watchonly", tags=["watchonly"])


def watchonly_renderer():
    return template_renderer(["watchonly/templates"])


from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403
