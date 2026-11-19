FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# WeasyPrint native deps (Pango/HarfBuzz/fontconfig) + pdftoppm for visual checks/snapshots.
# No system fonts are installed on purpose: the PDF must use the embedded fonts in app/fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fontconfig \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 quickquote \
    && mkdir -p /data /storage \
    && chown quickquote:quickquote /data /storage

WORKDIR /app

# Dependencies first, for layer caching.
COPY --chown=quickquote:quickquote pyproject.toml ./
COPY --chown=quickquote:quickquote app/__init__.py app/__init__.py
RUN pip install -e ".[dev]"

COPY --chown=quickquote:quickquote app ./app
COPY --chown=quickquote:quickquote tests ./tests
RUN chown quickquote:quickquote /app

USER quickquote

ENV DATABASE_URL=sqlite:////data/quickquote.db \
    STORAGE_DIR=/storage

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
