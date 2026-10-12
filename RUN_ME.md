# Lancer le projet

Commandes exactes, à exécuter depuis la racine du projet. Chaque commande est donnée pour PowerShell (Windows)
et pour bash (Linux, macOS). Durées indicatives, relevées sur un portable à 20 cœurs, sans carte graphique.

## 1. Installer

| | PowerShell | bash |
|---|---|---|
| Créer l'environnement | `python -m venv .venv` | `python3 -m venv .venv` |
| L'activer | `.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Installer le projet | `pip install -e ".[dev,mlops]"` | `pip install -e ".[dev,mlops]"` |

Python 3.12 ou plus récent. Les versions exactes utilisées sont dans `requirements.txt`.
Avec `uv` : `uv venv --python 3.12`, puis `uv pip install -e ".[dev,mlops]"`.

## 2. Parcours rapide (3 villes)

Les commandes sont les mêmes dans les deux interpréteurs.

| Étape | Commande | Durée |
|---|---|---|
| Tout enchaîner | `python -m solarvision.cli pipeline --fast` | environ 15 min la première fois (téléchargements), 6 min ensuite |
| Tests | `python -m pytest -m "not data and not slow"` | 20 s |
| Rapport | `python -m solarvision.cli report --fast` | 30 s |
| Application et API | `python -m solarvision.cli serve --fast` | ouvrir http://127.0.0.1:8001 |
| Notebook | `python -m nbconvert --to notebook --execute --inplace notebooks/solarvision_v2.ipynb` | 1 min si le parcours rapide a déjà tourné |

Le parcours rapide télécharge environ 50 Mo (Paris, Tunis, Madrid). Il attend 3 minutes entre deux requêtes
à Open-Meteo, pour rester sous le quota gratuit.

## 3. Étude complète (30 villes)

| Étape | Commande | Durée |
|---|---|---|
| Collecte | `python -m solarvision.cli ingest` | 1 h 30 (quota d'Open-Meteo : une dizaine de villes par heure) |
| Reprise après un quota | `python -m solarvision.cli ingest --retry-failed` | selon le nombre de villes |
| État du cache | `python -m solarvision.cli status` | immédiat |
| Reconstruire les tables sans réseau | `python -m solarvision.cli ingest --reprocess` | 1 min |
| Panel et découpages | `python -m solarvision.cli features --allow-partial` | 10 s |
| Modèles classiques | `python -m solarvision.cli train --workers 14 --sensitivity` | 15 min |
| Réseaux récurrents | `python -m solarvision.cli deep --walk-forward tunis` | 10 min |
| Évaluation | `python -m solarvision.cli evaluate` | 1 min |
| Technologies | `python -m solarvision.cli recommend` | 1 min |
| Économie | `python -m solarvision.cli economics` | 10 s |
| Registre | `python -m solarvision.cli register` | 30 s |
| Suivi | `python -m solarvision.cli monitor` | 20 s |
| Section IA générative | `python -m solarvision.cli llm-pack` | 1 min |
| Rapport | `python -m solarvision.cli report` | 2 min |
| Application et API | `python -m solarvision.cli serve` | ouvrir http://127.0.0.1:8001 |

`python -m solarvision.cli pipeline` enchaîne tout, de la collecte au suivi.
Chaque étape reprend là où elle s'est arrêtée : une ville déjà traitée n'est pas refaite (ajouter `--force` pour la refaire).

## 4. Dossier R autonome

| | PowerShell | bash |
|---|---|---|
| Exécuter tout le code R | `Rscript .\r_standalone\run_all.R` | `Rscript r_standalone/run_all.R` |

Durée : 2 minutes. Les packages nécessaires sont listés dans le fichier `DESCRIPTION` du dossier.

## 5. Étude historique (9 villes)

| But | Commande |
|---|---|
| Notebook Python | `python -m nbconvert --to notebook --execute --inplace mini_projet_python.ipynb` |
| Rapport historique | `python rapport/construire_rapport.py` |
| Application historique | `docker compose up --build`, puis http://localhost:8000 |

## 6. Avant de rendre

1. Renseigner les noms du groupe : `report.authors` dans `configs/params.yaml`.
2. Rédiger `docs/llm/interpretation_experte.md` **avant** d'envoyer les prompts de `docs/llm/` à un LLM.
3. Coller les réponses dans `docs/llm/reponse_1.md` à `reponse_3.md`, puis remplir `docs/llm/comparaison_humain_llm.md`.
4. Régénérer le rapport : `python -m solarvision.cli report`.
5. Créer l'archive : `python scripts/make_archive.py`. Elle exclut la clé `.env`, les environnements et le cache brut.
   Pour retirer d'autres fichiers : `python scripts/make_archive.py --exclude CLAUDE.md --exclude MASTER_PROMPT.md`.
