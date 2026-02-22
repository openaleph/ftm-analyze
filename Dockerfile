# syntax=docker/dockerfile:1.4
#
# Multi-stage Dockerfile for ftm-analyze with NER variant targets
#
# Build targets:
#   docker build --target spacy -t ftm-analyze:spacy .
#   docker build --target spacy-slim -t ftm-analyze:spacy-slim .
#   docker build --target flair -t ftm-analyze:flair .
#   docker build --target gliner -t ftm-analyze:gliner .
#   docker build --target transformers -t ftm-analyze:transformers .
#   docker build --target minimal -t ftm-analyze:minimal .
#
# Default target is 'spacy'

ARG PYTHON_VERSION=3.13

# =============================================================================
# Stage: python-base
# Runtime base with only necessary system libraries (no build tools)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime dependencies only - libicu for pyicu
# Note: git NOT included - only needed at build time
# Use wildcard for libicu version (72 on bookworm, 76 on trixie)
RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends \
        'libicu[0-9][0-9]' \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# =============================================================================
# Stage: builder
# Build stage with compilation tools - produces wheels for native packages
# =============================================================================
FROM python-base AS builder

RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends \
        build-essential \
        pkg-config \
        libicu-dev \
        git \
        binutils \
    && rm -rf /var/lib/apt/lists/*

# Build pyicu wheel (requires compilation)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --no-binary=:pyicu: --wheel-dir=/wheels pyicu

# =============================================================================
# Stage: models-ftm
# Download FTM type prediction model (parallel with other stages)
# =============================================================================
FROM python-base AS models-ftm

RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/models \
    && wget -q -O /app/models/model_type_prediction.ftz \
        https://cdn.investigativedata.org/ftm-analyze/model_type_prediction.ftz

# =============================================================================
# Stage: deps-base
# Install frozen dependencies from requirements.txt
# =============================================================================
FROM builder AS deps-builder

# Install pre-built pyicu wheel
RUN pip install /wheels/*.whl

RUN apt-get update -qq \
    && apt-get install -qq -y --no-install-recommends libleveldb-dev \
    && rm -rf /var/lib/apt/lists/*

# Install frozen dependencies with git available for VCS deps
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements.txt

# Strip debug symbols from compiled extensions (~20-40MB savings)
RUN find /usr/local/lib/python*/site-packages -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

# Remove unnecessary files from site-packages (~30-50MB savings)
# Be careful not to remove data files needed at runtime
RUN find /usr/local/lib/python*/site-packages -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyo" -delete 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "doc" -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Stage: deps-base (clean runtime without build tools)
# =============================================================================
FROM python-base AS deps-base

# Copy cleaned site-packages from builder
COPY --from=deps-builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps-builder /usr/local/bin /usr/local/bin

# =============================================================================
# Stage: app-base
# Application code installation (no NER extras yet)
# =============================================================================
FROM deps-base AS app-base

# Copy FTM model from parallel stage
COPY --from=models-ftm /app/models /app/models

# Copy application code
COPY pyproject.toml setup.py VERSION README.md /app/
COPY ftm_analyze /app/ftm_analyze
COPY models /app/models

# Install app without deps (already installed) and add psycopg binary
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps --no-compile ".[openaleph]" \
    && pip install --no-compile "psycopg[binary]"

# Final cleanup - remove pip/setuptools (not needed at runtime)
RUN pip uninstall -y pip setuptools 2>/dev/null || true \
    && rm -rf /root/.cache /tmp/* \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

ENV PROCRASTINATE_APP="ftm_analyze.tasks.app"

# =============================================================================
# Stage: minimal
# Minimal image without any NER backend (for testing/development)
# =============================================================================
FROM app-base AS minimal

ENV FTM_ANALYZE_NER_ENGINE=""
ENTRYPOINT []

# =============================================================================
# Stage: spacy-models
# Download spaCy models (parallel stage for caching)
# =============================================================================
FROM python-base AS spacy-models

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install spacy

# Download models - grouped by region for granular layer caching
# Western European (most common)
RUN python -m spacy download en_core_web_sm \
    && python -m spacy download de_core_news_sm \
    && python -m spacy download fr_core_news_sm \
    && python -m spacy download es_core_news_sm

# Southern/Western European
RUN python -m spacy download pt_core_news_sm \
    && python -m spacy download it_core_news_sm \
    && python -m spacy download nl_core_news_sm

# Eastern European
RUN python -m spacy download ru_core_news_sm \
    && python -m spacy download pl_core_news_sm \
    && python -m spacy download ro_core_news_sm \
    && python -m spacy download mk_core_news_sm

# Nordic + other
RUN python -m spacy download el_core_news_sm \
    && python -m spacy download lt_core_news_sm \
    && python -m spacy download nb_core_news_sm \
    && python -m spacy download da_core_news_sm

# =============================================================================
# Stage: spacy-models-slim
# Minimal set of spaCy models (EN, DE, FR, ES only) for smaller image
# =============================================================================
FROM python-base AS spacy-models-slim

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install spacy

RUN python -m spacy download en_core_web_sm \
    && python -m spacy download de_core_news_sm \
    && python -m spacy download fr_core_news_sm \
    && python -m spacy download es_core_news_sm

# =============================================================================
# Stage: spacy (DEFAULT)
# Full spaCy NER with all language models
# =============================================================================
FROM app-base AS spacy

# Copy spaCy model packages with dist-info from models stage
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/en_core_web_sm /usr/local/lib/python3.13/site-packages/en_core_web_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/de_core_news_sm /usr/local/lib/python3.13/site-packages/de_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/fr_core_news_sm /usr/local/lib/python3.13/site-packages/fr_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/es_core_news_sm /usr/local/lib/python3.13/site-packages/es_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/pt_core_news_sm /usr/local/lib/python3.13/site-packages/pt_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/it_core_news_sm /usr/local/lib/python3.13/site-packages/it_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/nl_core_news_sm /usr/local/lib/python3.13/site-packages/nl_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/ru_core_news_sm /usr/local/lib/python3.13/site-packages/ru_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/pl_core_news_sm /usr/local/lib/python3.13/site-packages/pl_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/ro_core_news_sm /usr/local/lib/python3.13/site-packages/ro_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/mk_core_news_sm /usr/local/lib/python3.13/site-packages/mk_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/el_core_news_sm /usr/local/lib/python3.13/site-packages/el_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/lt_core_news_sm /usr/local/lib/python3.13/site-packages/lt_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/nb_core_news_sm /usr/local/lib/python3.13/site-packages/nb_core_news_sm
COPY --from=spacy-models /usr/local/lib/python3.13/site-packages/da_core_news_sm /usr/local/lib/python3.13/site-packages/da_core_news_sm

# Copy dist-info directories and additional model dependencies (e.g., pymorphy3 for Russian)
RUN --mount=from=spacy-models,source=/usr/local/lib/python3.13/site-packages,target=/mnt \
    cp -r /mnt/*_core_*_sm*.dist-info /usr/local/lib/python3.13/site-packages/ \
    && cp -r /mnt/pymorphy3* /usr/local/lib/python3.13/site-packages/ 2>/dev/null || true \
    && cp -r /mnt/dawg* /usr/local/lib/python3.13/site-packages/ 2>/dev/null || true

# Copy .so files necessary for plyvel (juditha)
COPY --from=deps-builder /usr/lib/x86_64-linux-gnu/libleveldb.so.1d /usr/lib/x86_64-linux-gnu/libleveldb.so.1d
COPY --from=deps-builder /usr/lib/x86_64-linux-gnu/libsnappy.so.1 /usr/lib/x86_64-linux-gnu/libsnappy.so.1
# COPY --from=deps-builder /usr/lib/aarch64-linux-gnu/libleveldb.so.1d /usr/lib/aarch64-linux-gnu/libleveldb.so.1d
# COPY --from=deps-builder /usr/lib/aarch64-linux-gnu/libsnappy.so.1 /usr/lib/aarch64-linux-gnu/libsnappy.so.1

ENV FTM_ANALYZE_NER_ENGINE=spacy
ENTRYPOINT []

# =============================================================================
# Stage: spacy-slim
# spaCy NER with only common language models (EN, DE, FR, ES)
# ~250MB smaller than full spacy
# =============================================================================
FROM app-base AS spacy-slim

# Copy spaCy model packages with dist-info from slim models stage
COPY --from=spacy-models-slim /usr/local/lib/python3.13/site-packages/en_core_web_sm /usr/local/lib/python3.13/site-packages/en_core_web_sm
COPY --from=spacy-models-slim /usr/local/lib/python3.13/site-packages/de_core_news_sm /usr/local/lib/python3.13/site-packages/de_core_news_sm
COPY --from=spacy-models-slim /usr/local/lib/python3.13/site-packages/fr_core_news_sm /usr/local/lib/python3.13/site-packages/fr_core_news_sm
COPY --from=spacy-models-slim /usr/local/lib/python3.13/site-packages/es_core_news_sm /usr/local/lib/python3.13/site-packages/es_core_news_sm
# Copy dist-info directories for package recognition
RUN --mount=from=spacy-models-slim,source=/usr/local/lib/python3.13/site-packages,target=/mnt \
    cp -r /mnt/*_core_*_sm*.dist-info /usr/local/lib/python3.13/site-packages/

# Copy .so files necessary for plyvel (juditha)
COPY --from=deps-builder /usr/lib/x86_64-linux-gnu/libleveldb.so.1d /usr/lib/x86_64-linux-gnu/libleveldb.so.1d
COPY --from=deps-builder /usr/lib/x86_64-linux-gnu/libsnappy.so.1 /usr/lib/x86_64-linux-gnu/libsnappy.so.1
# COPY --from=deps-builder /usr/lib/aarch64-linux-gnu/libleveldb.so.1d /usr/lib/aarch64-linux-gnu/libleveldb.so.1d
# COPY --from=deps-builder /usr/lib/aarch64-linux-gnu/libsnappy.so.1 /usr/lib/aarch64-linux-gnu/libsnappy.so.1

ENV FTM_ANALYZE_NER_ENGINE=spacy
ENTRYPOINT []

# =============================================================================
# Stage: flair
# Flair NER backend (downloads models at runtime)
# =============================================================================
FROM app-base AS flair

RUN python -m ensurepip 2>/dev/null || true \
    && pip install --no-compile "flair>=0.15.1,<0.16.0" \
    && pip uninstall -y pip setuptools 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true

ENV FTM_ANALYZE_NER_ENGINE=flair
ENTRYPOINT []

# =============================================================================
# Stage: gliner
# GLiNER zero-shot NER backend
# =============================================================================
FROM app-base AS gliner

RUN python -m ensurepip 2>/dev/null || true \
    && pip install --no-compile "gliner>=0.2,<1.0" \
    && pip uninstall -y pip setuptools 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true

ENV FTM_ANALYZE_NER_ENGINE=gliner
ENTRYPOINT []

# =============================================================================
# Stage: transformers
# Hugging Face transformers NER backend (BERT, etc.)
# =============================================================================
FROM app-base AS transformers

RUN python -m ensurepip 2>/dev/null || true \
    && pip install --no-compile "transformers>=4.57.1,<5.0.0" \
    && pip uninstall -y pip setuptools 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python*/site-packages -name "*.pyc" -delete 2>/dev/null || true

ENV FTM_ANALYZE_NER_ENGINE=bert
ENTRYPOINT []
