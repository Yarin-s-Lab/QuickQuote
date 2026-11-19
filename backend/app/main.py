from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.routes import router
from app.config import Settings, load_settings
from app.db.session import Database
from app.services.pdf_renderer import PdfRenderer
from app.services.quote_service import QuoteService
from app.services.storage import Storage


def create_app(
    settings: Settings | None = None,
    *,
    renderer: PdfRenderer | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own settings, renderer and clock."""
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings.database_url)
        db.create_all()
        service = QuoteService(
            sessions=db.sessionmaker,
            storage=Storage(settings.storage_dir),
            renderer=renderer or PdfRenderer(),
        )
        if clock is not None:
            service.clock = clock
        app.state.quote_service = service
        try:
            yield
        finally:
            db.dispose()

    app = FastAPI(title="QuickQuote API", version="0.3.0", lifespan=lifespan)
    # No 307 "/x/" -> "/x" redirects: odd paths (e.g. download tokens ending in "/")
    # get a plain 404 instead of being bounced to another route.
    app.router.redirect_slashes = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        # setdefault: routes that set their own value (the download) keep it, no duplicates.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
