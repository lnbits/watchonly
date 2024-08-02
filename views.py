from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.helpers import template_renderer

watchonly_generic_router = APIRouter()


def watchonly_renderer():
    return template_renderer(["watchonly/templates"])


templates = Jinja2Templates(directory="templates")


@watchonly_generic_router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return watchonly_renderer().TemplateResponse(
        "watchonly/index.html", {"request": request, "user": user.dict()}
    )
