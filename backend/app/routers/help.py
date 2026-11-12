from fastapi import APIRouter, HTTPException, Query, Response

from app import help_service
from app.dependencies import CurrentUser
from app.security import user_has_role

router = APIRouter(prefix="/help", tags=["Hilfe & Dokumentation"])


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"


@router.get("/catalog")
def help_catalog(response: Response, user: CurrentUser, q: str = Query(default="", max_length=200)) -> dict:
    private_response(response)
    return help_service.catalog(user_has_role(user, "system_admin"), q.strip())


@router.get("/articles/{article_id}")
def help_article(article_id: str, response: Response, user: CurrentUser) -> dict:
    private_response(response)
    item = help_service.article(article_id, user_has_role(user, "system_admin"))
    if item is None:
        raise HTTPException(status_code=404, detail="Dieser Hilfeartikel ist nicht verfügbar.")
    return item


@router.get("/contexts/{context_id}")
def help_context(context_id: str, response: Response, user: CurrentUser) -> dict:
    private_response(response)
    item = help_service.context(context_id, user_has_role(user, "system_admin"))
    if item is None:
        raise HTTPException(status_code=404, detail="Für diesen Bereich ist keine Hilfe verfügbar.")
    return item
