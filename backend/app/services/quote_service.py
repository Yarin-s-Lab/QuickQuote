"""Quote use cases. Level 1: preview only (no persistence)."""

from __future__ import annotations

from app.api.schemas import (
    ApartmentPreviewRequest,
    BreakdownLineOut,
    CarPreviewRequest,
    CoverageOut,
    FactorOut,
    PreviewResponse,
    ProductOut,
    ProductsResponse,
)
from app.domain.pricing.catalog import PRODUCTS, describe_fields
from app.domain.pricing.common import MIN_PREMIUM


def preview(request: CarPreviewRequest | ApartmentPreviewRequest) -> PreviewResponse:
    product = PRODUCTS[request.product]
    result = product.price(request.inputs, request.coverages)
    return PreviewResponse(
        product=product.code,
        premium=result.premium,
        premium_before_rounding=result.premium_before_rounding,
        minimum_applied=result.minimum_applied,
        breakdown=[
            BreakdownLineOut(code=line.code, label_he=line.label_he, amount=line.amount)
            for line in result.breakdown
        ],
        factors=[
            FactorOut(code=factor.code, label_he=factor.label_he, value=factor.value)
            for factor in result.factors
        ],
    )


def list_products() -> ProductsResponse:
    return ProductsResponse(
        min_premium=MIN_PREMIUM,
        products=[
            ProductOut(
                code=product.code,
                label_he=product.label_he,
                fields=describe_fields(product.inputs_model),
                coverages=[
                    CoverageOut(code=c.code, label_he=c.label_he, price_rule_he=c.price_rule_he)
                    for c in product.coverages.values()
                ],
            )
            for product in PRODUCTS.values()
        ],
    )
