"""HTTP routes only — no business logic here."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from app.api.schemas import (
    CompareRequest,
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


@router.post("/quotes/compare", response_class=Response)
def compare_quotes(request: CompareRequest, service: Service) -> Response:
    comparison = service.compare(request.tokens)
    return Response(
        content=comparison.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{comparison.filename}"',
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/quotes/download/{token}", response_class=FileResponse)
def download_quote(token: str, service: Service) -> FileResponse:
    download = service.get_download(token)
    if download is None:
        raise HTTPException(status_code=404)
    return FileResponse(
        download.path,
        media_type="application/pdf",
        filename=f"{download.quote_number}.pdf",
        content_disposition_type="attachment",
        headers={
            # The token is in the URL: never cache it or leak it via Referer.
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/quotes/{quote_number}", response_model=QuoteMetadata)
def get_quote(quote_number: str, service: Service) -> QuoteMetadata:
    metadata = service.get_metadata(quote_number)
    if metadata is None:
        raise HTTPException(status_code=404)
    return metadata
