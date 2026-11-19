"""HTTP routes only — no business logic here."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas import (
    CreateQuoteRequest,
    CreateQuoteResponse,
    PreviewRequest,
    PreviewResponse,
    ProductsResponse,
    QuoteMetadata,
)
from app.services import quote_service
from app.services.quote_service import QuoteService

router = APIRouter(prefix="/api")


def get_quote_service(request: Request) -> QuoteService:
    return request.app.state.quote_service


Service = Annotated[QuoteService, Depends(get_quote_service)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/products", response_model=ProductsResponse)
def get_products() -> ProductsResponse:
    return quote_service.list_products()


@router.post("/quotes/preview", response_model=PreviewResponse)
def preview_quote(request: PreviewRequest) -> PreviewResponse:
    return quote_service.preview(request)


@router.post("/quotes", response_model=CreateQuoteResponse, status_code=201)
def create_quote(request: CreateQuoteRequest, service: Service) -> CreateQuoteResponse:
    return service.create(request)


@router.get("/quotes/{quote_number}", response_model=QuoteMetadata)
def get_quote(quote_number: str, service: Service) -> QuoteMetadata:
    metadata = service.get_metadata(quote_number)
    if metadata is None:
        raise HTTPException(status_code=404)
    return metadata
