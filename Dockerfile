# syntax=docker/dockerfile:1
# SolarVision - Séries temporelles
#   docker compose up --build                          application web      -> http://localhost:8000
#   docker compose --profile etude run --rm notebook   ré-exécute le notebook Python (sections 1 à 7)

# ---------------------------------------------------------------- 1. site React (fichiers statiques)
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/frontend/index.html app/frontend/tsconfig.json app/frontend/vite.config.ts ./
COPY app/frontend/src ./src
RUN npm run build

# ---------------------------------------------------------------- 2. base Python commune
FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
WORKDIR /projet
# PyTorch en version CPU : l'index par défaut installerait les bibliothèques CUDA (plusieurs Go), inutiles ici.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.12.1

# ---------------------------------------------------------------- 3. étude : environnement du notebook Python
# Le projet est monté en volume par docker-compose : l'image ne contient que les paquets de requirements.txt.
FROM base AS etude
COPY requirements.txt .
# xgboost-cpu : même bibliothèque sans les dépendances GPU (plusieurs centaines de Mo) ; Playwright ne sert qu'au PDF du rapport.
RUN sed -e 's/^xgboost==/xgboost-cpu==/' -e '/^playwright==/d' requirements.txt > /tmp/requirements-docker.txt \
    && pip install -r /tmp/requirements-docker.txt
CMD ["python", "-m", "nbconvert", "--to", "notebook", "--execute", "--inplace", \
     "--ExecutePreprocessor.timeout=5400", "mini_projet_python.ipynb"]

# ---------------------------------------------------------------- 4. application : API + modèles + données + site
FROM base AS app
COPY app/backend/requirements.txt app/backend/requirements.txt
RUN pip install -r app/backend/requirements.txt
# Seuls les fichiers lus par l'API sont copiés (jeux de données, modèles entraînés, corpus du RAG, métriques).
COPY data/catalogue_datasets.json data/catalogue_datasets.json
COPY data/reference data/reference
COPY data/datasets data/datasets
COPY sources/liens_rapport_solarvision.json sources/liens_rapport_solarvision.json
COPY resultats/py_metriques.csv resultats/py_rmse_par_horizon.csv resultats/
COPY rag rag
COPY app/backend app/backend
COPY --from=frontend /frontend/dist app/frontend/dist
# Exécution sans privilèges : l'API ne fait que lire ses fichiers.
RUN useradd --create-home --uid 10001 solar
USER solar
WORKDIR /projet/app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status != 200)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
