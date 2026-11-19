"""HTML -> PDF rendering (SPEC sections 6 and 7).

Security rules (do not relax):
- Jinja2 with autoescape=True; user input only ever enters as template *variables*.
  No Environment.from_string, no |safe on user data.
- WeasyPrint only fetches through build_url_fetcher(): file:// under templates/ or fonts/.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.config import LOCAL_TZ

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"
FONTS_DIR = APP_DIR / "fonts"
ALLOWED_RESOURCE_DIRS = (TEMPLATES_DIR, FONTS_DIR)
TEMPLATE_NAME = "quote.html"


class PdfUnavailableError(RuntimeError):
    """WeasyPrint or its native libraries (Pango) are not installed here."""


class BlockedResourceError(ValueError):
    pass


# ---------- display filters ----------

_CENT = Decimal("0.01")


def format_ils(amount: Decimal) -> str:
    """Decimal('1234') -> '1,234 ₪'; fractions shown to 2 places only when present."""
    if not isinstance(amount, Decimal):
        raise TypeError("format_ils accepts Decimal only")
    cents = amount.quantize(_CENT, rounding=ROUND_HALF_UP)
    whole = cents == cents.to_integral_value()
    text = f"{int(cents):,}" if whole else f"{cents:,.2f}"
    return f"{text} ₪"


def format_date_he(moment: datetime) -> str:
    """Aware datetime -> 'DD/MM/YYYY' in Israel time."""
    if moment.tzinfo is None:
        raise ValueError("naive datetime")
    return moment.astimezone(LOCAL_TZ).strftime("%d/%m/%Y")


def format_factor(value: Decimal) -> str:
    return f"×{value.normalize():f}"


# ---------- resource access ----------


def check_resource_url(url: str) -> Path:
    """Return the local path for an allowed resource URL, or raise BlockedResourceError."""
    parsed = urlparse(url)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        raise BlockedResourceError(f"blocked non-local resource: {url!r}")
    raw_path = unquote(parsed.path)
    if "\x00" in raw_path:
        raise BlockedResourceError("blocked resource with NUL byte")
    path = Path(url2pathname(raw_path)).resolve()
    if not any(path.is_relative_to(allowed) for allowed in ALLOWED_RESOURCE_DIRS):
        raise BlockedResourceError(f"blocked file outside templates/fonts: {url!r}")
    if not path.is_file():
        raise BlockedResourceError(f"missing resource: {url!r}")
    return path


@dataclass(frozen=True)
class FetchedResource:
    url: str
    body: bytes
    mime_type: str


def fetch_resource(url: str) -> FetchedResource:
    """All resource-access policy lives here (plain Python, testable without WeasyPrint)."""
    path = check_resource_url(url)
    mime_type, _ = mimetypes.guess_type(path.name)
    if path.suffix == ".ttf":
        mime_type = "font/ttf"
    return FetchedResource(
        url=path.as_uri(),
        body=path.read_bytes(),
        mime_type=mime_type or "application/octet-stream",
    )


def build_url_fetcher() -> Any:
    """WeasyPrint (>=70) adapter around fetch_resource.

    fail_on_errors=True: a blocked or missing resource aborts the render instead of
    being silently skipped, so a bad template or injected markup cannot go unnoticed.
    """
    from weasyprint.urls import URLFetcher, URLFetcherResponse

    class SafeURLFetcher(URLFetcher):
        def fetch(self, url: str, headers: Any = None) -> URLFetcherResponse:
            resource = fetch_resource(url)
            return URLFetcherResponse(
                resource.url, body=resource.body, headers={"Content-Type": resource.mime_type}
            )

    return SafeURLFetcher(allowed_protocols=["file"], allow_redirects=False, fail_on_errors=True)


# ---------- rendering ----------


@dataclass(frozen=True)
class DocumentLine:
    label_he: str
    amount: Decimal


@dataclass(frozen=True)
class DocumentFactor:
    label_he: str
    value: Decimal


@dataclass(frozen=True)
class DocumentField:
    label_he: str
    value: str
    ltr: bool = False  # numbers/amounts: force LTR so signs and separators never flip


@dataclass(frozen=True)
class QuoteDocument:
    """Everything the template shows. All strings are treated as untrusted."""

    quote_number: str
    product_label_he: str
    issued_at: datetime
    valid_until: datetime
    agent_name: str
    client_full_name: str
    client_phone: str | None
    client_email: str | None
    fields: tuple[DocumentField, ...]
    coverages: tuple[str, ...]
    breakdown: tuple[DocumentLine, ...]
    factors: tuple[DocumentFactor, ...]
    premium_before_rounding: Decimal
    premium: Decimal
    minimum_applied: bool


def _build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["ils"] = format_ils
    env.filters["date_he"] = format_date_he
    env.filters["factor"] = format_factor
    return env


class PdfRenderer:
    def __init__(self) -> None:
        self._env = _build_environment()

    def render_html(self, document: QuoteDocument) -> str:
        return self._env.get_template(TEMPLATE_NAME).render(q=document)

    def render_pdf(self, html: str) -> bytes:
        try:
            from weasyprint import HTML
            from weasyprint.urls import FatalURLFetchingError
        except (ImportError, OSError) as exc:
            raise PdfUnavailableError(str(exc)) from exc
        base_url = TEMPLATES_DIR.as_uri() + "/"
        try:
            return HTML(string=html, base_url=base_url, url_fetcher=build_url_fetcher()).write_pdf()
        except FatalURLFetchingError as exc:
            # WeasyPrint's fatal fetch error derives from BaseException; turn it into a
            # normal error so it is handled (500) instead of killing the request.
            raise BlockedResourceError(str(exc)) from exc

    def render(self, document: QuoteDocument) -> bytes:
        return self.render_pdf(self.render_html(document))
