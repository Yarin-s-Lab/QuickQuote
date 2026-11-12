"""HTTP routes only — no business logic here."""

from fastapi import APIRouter

from app.api.schemas import PreviewRequest, PreviewResponse, ProductsResponse
from app.services import quote_service

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/products", response_model=ProductsResponse)
def get_products() -> ProductsResponse:
    return quote_service.list_products()


@router.post("/quotes/preview", response_model=PreviewResponse)
def preview_quote(request: PreviewRequest) -> PreviewResponse:
    return quote_service.preview(request)
