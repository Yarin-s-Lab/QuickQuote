from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api.errors import install_error_handlers
from app.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="QuickQuote API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.FRONTEND_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
