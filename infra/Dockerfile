# syntax=docker/dockerfile:1
# Image de SolarVision v2 : API /v1 et application multi-pages.
#   docker compose -f infra/docker-compose.yml up --build      -> http://localhost:8001
# État au 11 octobre 2026 : fichier écrit mais image non construite (connexion trop lente pour les téléchargements).

# ---------------------------------------------------------------- 1. dépendances
FROM python:3.12-slim AS deps
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /projet
# PyTorch en version processeur : l'index par défaut installerait les bibliothèques CUDA, inutiles ici.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[mlops]"

# ---------------------------------------------------------------- 2. exécution
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1
WORKDIR /projet
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
# Seuls les fichiers lus par le service sont copiés : configuration, pages, panel, rapports, registre.
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY app/pages ./app/pages
COPY data/processed/panel_journalier.parquet data/processed/splits_90_10.yaml data/processed/panel_meta.yaml ./data/processed/
COPY data/manifest.yaml ./data/manifest.yaml
COPY reports ./reports
COPY models/registry ./models/registry
RUN pip install --no-deps -e .
# Exécution sans privilèges ; le service n'écrit que son journal de requêtes.
RUN useradd --create-home --uid 10001 solar && chown -R solar /projet/reports
USER solar
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4).status != 200)"
CMD ["uvicorn", "solarvision.serving.api:app", "--host", "0.0.0.0", "--port", "8001"]
