"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator

from fastapi import Query, Request
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings
from ..utils import clamp_page_size


def get_db(request: Request) -> Iterator[Session]:
    """Yield a database session bound to the application's engine."""
    with sessionmaker(request.app.state.engine, expire_on_commit=False)() as session:
        yield session


class PageParams:
    """Pagination query parameters (?page=1&page_size=25)."""

    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int | None = Query(None, ge=1, description="Defaults to api.default_page_size"),
    ):
        self.page = page
        self.page_size = clamp_page_size(
            page_size, settings.api.default_page_size, settings.api.max_page_size
        )
