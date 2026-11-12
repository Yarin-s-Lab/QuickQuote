"""Product metadata for building the form, derived from the input models (one source of truth)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .apartment import APARTMENT_COVERAGES, ApartmentInputs, price_apartment
from .car import CAR_COVERAGES, CarInputs, price_car
from .common import Coverage, PricingResult


@dataclass(frozen=True)
class Product:
    code: str
    label_he: str
    inputs_model: type[BaseModel]
    coverages: dict[str, Coverage]
    price: Callable[[Any, Iterable[str]], PricingResult]


PRODUCTS: dict[str, Product] = {
    "car": Product("car", "ביטוח רכב", CarInputs, CAR_COVERAGES, price_car),
    "apartment": Product(
        "apartment", "ביטוח דירה", ApartmentInputs, APARTMENT_COVERAGES, price_apartment
    ),
}

_JSON_TYPE_TO_FIELD_TYPE = {"integer": "integer", "boolean": "boolean", "string": "enum"}


def describe_fields(model: type[BaseModel]) -> list[dict[str, Any]]:
    schema = model.model_json_schema()
    required = set(schema.get("required", []))
    fields: list[dict[str, Any]] = []
    for name, prop in schema["properties"].items():
        field_type = _JSON_TYPE_TO_FIELD_TYPE[prop["type"]]
        if field_type == "integer" and prop.get("unit") == "ILS":
            field_type = "money"
        field: dict[str, Any] = {
            "name": name,
            "label_he": prop["title"],
            "type": field_type,
            "required": name in required,
            "min": prop.get("minimum"),
            "max": prop.get("maximum"),
            "options": None,
        }
        if field_type == "enum":
            labels = prop.get("options_he", {})
            field["options"] = [
                {"value": value, "label_he": labels.get(value, value)} for value in prop["enum"]
            ]
        fields.append(field)
    return fields


def field_labels_he() -> dict[str, str]:
    """Field name -> Hebrew label, across all products (used for Hebrew error messages)."""
    labels: dict[str, str] = {}
    for product in PRODUCTS.values():
        for field in describe_fields(product.inputs_model):
            labels[field["name"]] = field["label_he"]
    return labels
