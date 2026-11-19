"""SPEC section 7: user input reaches the PDF as literal text, never as markup or code."""

import re
from pathlib import Path

import pytest

from app.services.pdf_renderer import (
    FONTS_DIR,
    TEMPLATES_DIR,
    BlockedResourceError,
    PdfRenderer,
    build_url_fetcher,
    check_resource_url,
    fetch_resource,
)
from tests.conftest import PRODUCT_CODES, make_document, requires_pdf

PAYLOADS = {
    "jinja": "{{7*7}}",
    "jinja_block": "{% for x in range(3) %}X{% endfor %}",
    "script": "<script>alert(1)</script>",
    "img_file": '<img src="file:///etc/passwd">',
    "link_http": '<link rel="stylesheet" href="http://attacker.example/x.css">',
    "style": "<style>body{display:none}</style>",
    "attr_break": '"><b onmouseover=alert(1)>',
}


def render_with_everywhere(payload: str, product: str = "car") -> str:
    return PdfRenderer().render_html(
        make_document(
            product,
            agent_name=payload,
            client_full_name=payload,
            client_phone=payload,
            client_email=payload,
        )
    )


def body_of(html: str) -> str:
    """Everything after the opening <body ...> tag (the head legitimately has <link>s)."""
    return html.split("<body", 1)[1].split(">", 1)[1]


@pytest.mark.parametrize("product", PRODUCT_CODES)
@pytest.mark.parametrize("name", PAYLOADS)
def test_payload_is_escaped_in_html(name, product):
    payload = PAYLOADS[name]
    body = body_of(render_with_everywhere(payload, product))

    # No raw markup from the payload survives.
    for raw in ("<script", "<img", "<link", "<style", "<b "):
        assert raw not in body, f"{raw} leaked"
    # Template syntax is not evaluated.
    assert "XXX" not in body


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_jinja_expression_stays_literal(product):
    html = render_with_everywhere("{{7*7}}", product)
    assert html.count("{{7*7}}") == 4
    assert ">49<" not in html


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_escaped_forms_present(product):
    html = render_with_everywhere("<script>alert(1)</script>", product)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_only_expected_head_resources(product):
    """The only external references are our own two stylesheets; no user data in <head>."""
    html = render_with_everywhere('"><link href="http://x">', product)
    head = html.split("<body", 1)[0]
    assert sorted(re.findall(r'href="([^"]*)"', head)) == sorted(
        ["quote.css", f"quote_{product}.css"]
    )
    assert "src=" not in html


def test_renderer_has_no_from_string_and_autoescape_on():
    env = PdfRenderer()._env
    assert env.autoescape is True
    source = (
        Path(__file__)
        .parents[2]
        .joinpath("app", "services", "pdf_renderer.py")
        .read_text(encoding="utf-8")
    )
    assert ".from_string(" not in source


def test_templates_do_not_use_safe_filter():
    templates = sorted(TEMPLATES_DIR.glob("*.html"))
    assert {t.name for t in templates} >= {"base.html", "quote_car.html", "quote_apartment.html"}
    for template in templates:
        text = template.read_text(encoding="utf-8").replace(" ", "")
        assert "|safe" not in text, template.name
        assert "autoescapefalse" not in text, template.name


def test_css_only_references_local_fonts():
    """Every url() in our CSS is a bundled font; no remote or @import resources."""
    for css in sorted(TEMPLATES_DIR.glob("*.css")):
        text = css.read_text(encoding="utf-8")
        assert "@import" not in text, css.name
        for url in re.findall(r"url\(([^)]*)\)", text):
            target = (TEMPLATES_DIR / url.strip("\"' ")).resolve()
            assert target.is_relative_to(FONTS_DIR), (css.name, url)
            assert target.is_file(), (css.name, url)


# ---------- url_fetcher ----------


@pytest.mark.parametrize(
    "url",
    [
        "http://attacker.example/x.css",
        "https://fonts.googleapis.com/css2?family=Noto+Sans+Hebrew",
        "ftp://example.com/x",
        "data:text/css,body{}",
        "file:///etc/passwd",
        "file:///C:/Windows/win.ini",
        "file://evil-host/share/x.css",
        (TEMPLATES_DIR / ".." / ".." / "pyproject.toml").as_uri(),
        TEMPLATES_DIR.as_uri() + "/../../../etc/passwd",
        TEMPLATES_DIR.as_uri() + "/..%2F..%2F..%2Fetc%2Fpasswd",
        TEMPLATES_DIR.as_uri() + "/quote.css%00.png",
        (TEMPLATES_DIR / "missing.css").as_uri(),
    ],
)
def test_fetcher_blocks(url):
    with pytest.raises(BlockedResourceError):
        fetch_resource(url)


@pytest.mark.parametrize(
    "path",
    [
        TEMPLATES_DIR / "quote.css",
        FONTS_DIR / "NotoSansHebrew-Regular.ttf",
        FONTS_DIR / "NotoSans-Bold.ttf",
    ],
)
def test_fetcher_allows_template_and_font_files(path):
    assert check_resource_url(path.as_uri()) == path.resolve()
    assert fetch_resource(path.as_uri()).body == path.read_bytes()


def test_font_mime_type():
    assert fetch_resource((FONTS_DIR / "NotoSans-Regular.ttf").as_uri()).mime_type == "font/ttf"


# ---------- in the real PDF (Docker) ----------


@requires_pdf
@pytest.mark.pdf
def test_payloads_appear_literally_in_pdf():
    from io import BytesIO

    from pypdf import PdfReader

    pdf = PdfRenderer().render(
        make_document(agent_name="{{7*7}}", client_full_name='<img src="file:///etc/passwd">')
    )
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    # Not evaluated. (A neutral-only run inside RTL is extracted in visual order,
    # so the braces may come out as "}}7*7{{"; on the page it reads {{7*7}}.)
    assert "7*7" in text
    assert "49" not in text
    assert "file:///etc/passwd" in text


@requires_pdf
@pytest.mark.pdf
@pytest.mark.parametrize(
    "url", ["http://attacker.example/x.css", "file:///etc/passwd", "data:text/css,body{}"]
)
def test_weasyprint_fetcher_blocks(url):
    with pytest.raises(BlockedResourceError):
        build_url_fetcher().fetch(url)


@requires_pdf
@pytest.mark.pdf
@pytest.mark.parametrize(
    "markup",
    [
        '<link rel="stylesheet" href="http://attacker.example/x.css">',
        '<img src="file:///etc/passwd">',
        '<style>@font-face{font-family:x;src:url("http://attacker.example/f.ttf")}</style>',
    ],
)
def test_render_aborts_on_external_resource(markup):
    """Even if markup ever reached the HTML unescaped, nothing outside is fetched."""
    html = f'<html lang="he" dir="rtl"><head>{markup}</head><body>x</body></html>'
    with pytest.raises(BlockedResourceError):
        PdfRenderer().render_pdf(html)
