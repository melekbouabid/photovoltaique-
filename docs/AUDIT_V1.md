# Audit V1 — état du dépôt d'origine

Date : 11 octobre 2026. Phase 0 en version allégée : aucun téléchargement, aucune installation, aucune logique de modélisation modifiée. Toutes les vérifications ont été faites avec l'environnement existant (Python 3.14).

## 1. Résumé

- Le dépôt d'origine est **complet et fonctionnel pour 9 villes** : données, notebooks R et Python, rapport, application, assistant RAG.
- **Rien de la v2 n'existe ici** : ni les 30 villes, ni les technologies CIS et CdTe, ni le dossier `_import_pc1/`.
- Les trois acquis vérifiables sur ce dossier sont confirmés : découpage 6 245 / 694, 13 dates imputées à Tunis, métriques de référence.
- Deux éléments du rapport restent à compléter à la main avant le rendu (noms du groupe, outils d'IA utilisés).

## 2. Fichiers demandés par le plan

| Élément | Résultat |
|---|---|
| `Mini_Projet_Series_Temporelles_2026.pdf` (cahier des charges) | Introuvable |
| `rapport_detaille_SolarVision.md` | Introuvable |
| `_import_pc1/` | Introuvable |

Recherche faite dans tout `Desktop/s1/`. Conséquence : les données des 30 villes sont à collecter depuis zéro (Phase 2), et l'audit de conformité (Phase 10) ne peut pas relire le cahier des charges tant que le PDF n'est pas fourni.

## 3. Sauvegarde

- Pas de dépôt Git dans le projet (Git est installé). La sauvegarde est donc un zip hors du projet.
- Fichier : `../SAUVEGARDE_backup-original_2026-10-11.zip` (95,2 Mo, 457 fichiers, intégrité vérifiée).
- SHA256 : `dc6450250ca9e3ab3c91471e54fa4029bfa13dd8c6f17a72dc242d97c045d98d`
- Exclus : `.venv/`, `node_modules/`, caches, et `.env` (clé Groq). Ce zip n'est pas l'archive à remettre.

## 4. Ce qui existe

| Dossier ou fichier | Contenu | Taille |
|---|---|---|
| `python/` | Collecte (1 145 lignes), sources du notebook (`partie_A`, `B`, `C`), entraînement des modèles de l'application | 0,3 Mo |
| `mini_projet_python.ipynb` | Notebook Python exécuté | 3,3 Mo |
| `mini_projet_R.Rmd`, `.html` | Notebook R (540 lignes) et sa version compilée | 1 Mo |
| `data/datasets/` | 14 jeux de données (9 villes) | 92,6 Mo |
| `data/brut/` | Cache des réponses des API (313 fichiers) | 108,9 Mo |
| `resultats/` | 39 tableaux (métriques, tests, diagnostics) et le LSTM global | 0,1 Mo |
| `figures/` | 18 figures | 3,4 Mo |
| `rapport/` | Texte source, script de construction, Word et PDF (30 pages avec annexes) | 6,9 Mo |
| `app/` | API FastAPI, interface React, 4 modèles servis | 77,3 Mo, surtout `node_modules/` |
| `rag/`, `llm/` | Assistant RAG, prompts et réponses du LLM | 0,3 Mo |
| `Dockerfile`, `docker-compose.yml` | Conteneurs de l'application et du notebook | - |

Le code représente environ 5 500 lignes (15 fichiers Python et le notebook R).

## 5. Vérifications effectuées

| Vérification | Résultat |
|---|---|
| Tests existants (`app/backend/test_api.py`) | 19 réussis en 4,6 s |
| Découpage de Tunis (`int(n * 0.9)`) | 6 245 jours d'apprentissage, 694 de test |
| Dates imputées à Tunis (`tn_photovoltaique_journalier.csv`) | 13 dates, identiques à la liste du plan |
| Jours imputés par ville | 11 à 13 |
| Panel journalier | 9 villes × 6 939 jours = 62 451 lignes, 65 colonnes |
| Métriques de référence (`resultats/py_metriques.csv`) | Identiques aux valeurs citées dans le plan |
| Chemins absolus dans le code | Aucun |
| Archive de rendu existante (`../solarvision_series_temporelles.zip`) | Sans `.env`, sans `.venv` ni `node_modules` |

C'est le seul fichier de tests du dépôt : il n'y a aucun test sur les données, les fuites temporelles ou les modèles.

## 6. Environnement et versions

| Outil | État |
|---|---|
| Python | 3.14.2 seulement ; **Python 3.12 absent** |
| `uv` | Absent |
| Git | Installé, mais pas de dépôt |
| R | 4.6.0 |
| Docker, Node | 29.4.0 et 22.18.0 |

**Bibliothèques Python demandées par le plan**

| État | Bibliothèques |
|---|---|
| Présentes | pandas 2.3.3, statsmodels 0.15.0, arch 8.0.0, pmdarima 2.1.1, prophet 1.5.0, xgboost 3.1.3, torch 2.12.1 (CPU), fastapi 0.115.5, pyarrow 22.0.0, pyyaml 6.0.3, mlflow 3.9.0, typer 0.25.1, pydantic 2.12.5 |
| Absentes | pandera, evidently |
| Absentes (outils) | dvc, ruff |

**Packages R**

| État | Packages |
|---|---|
| Présents | forecast 9.0.2, urca 1.3.4, vars 1.6.1, tseries 0.10.63, FinTS 0.4.9, rugarch 1.5.6, lmtest 0.9.40, jsonlite 2.0.0, rmarkdown 2.31 |
| Absents | renv, here (nécessaires au dossier R isolé de la Phase 1) |

## 7. Ce qui est incohérent ou à corriger

| Problème | Où |
|---|---|
| Auteurs non renseignés : « [Noms des membres du groupe] » | `rapport/rapport_corps.md`, ligne 4 |
| Paragraphe « [À compléter par le groupe …] » sur les outils d'IA utilisés | `rapport/rapport_corps.md`, ligne 260 |
| La section 7.1 dit que le même LLM sert l'assistant RAG, alors que l'assistant utilise l'API Groq | `rapport/rapport_corps.md`, ligne 258 ; `rag/moteur.py` |
| Le rapport annonce 64 colonnes dans le panel, le fichier en contient 65 | `rapport/rapport_corps.md`, section 2.2 |
| L'en-tête du script annonce un PDF par xelatex, le code utilise Chromium (Playwright) | `rapport/construire_rapport.py`, ligne 7 |
| L'archive de rendu date du 10/10 à 20h27, le rapport a été régénéré à 20h50 : elle contient un rapport périmé | `../solarvision_series_temporelles.zip` |

## 8. Ce qui n'est pas portable

- **`.venv/`** : créé avec `--system-site-packages` sur le Python 3.14 de cette machine. torch, pandas et fastapi viennent de l'installation système. Il ne peut pas être reproduit ailleurs tel quel.
- **Pas de fichier de verrouillage** : `requirements.txt` fixe les versions pour Python 3.14, sans empreintes. Ces versions sont à revalider sous Python 3.12.
- **`rapport/construire_rapport.py`** : chemin de secours vers pandoc propre à Windows (`AppData/Local/Pandoc`), contournable en passant le chemin en argument.
- **`mini_projet_python.ipynb`** : une sortie de cellule affiche un chemin absolu de cette machine (ligne 142). Le code lui-même n'en contient pas.
- **`../report/.venv`** : environnement orphelin et cassé, hors du projet. À ne pas utiliser.
- **`data/brut/`** : exclu de Git et de l'archive de rendu. Le reconstruire demande le réseau (environ 20 minutes pour 9 villes).

## 9. Écarts entre le plan et ce dossier

| Le plan suppose | Ce dossier contient |
|---|---|
| 30 villes, panel de 208 170 lignes | 9 villes, panel de 62 451 lignes |
| 3 technologies (`pv_crystSi`, `pv_CIS`, `pv_CdTe`) | Une seule série, `pv_kwh_kwc` (silicium cristallin) |
| `config/cities.yaml` | Villes écrites dans le code (`python/collecte_donnees.py`, ligne 53) |
| Options `--fast`, `--retry-failed`, `--reprocess`, `--quality-only`, `--allow-partial` | Une seule option, `--forcer` |
| Dossier historique `mlops/` et son registre | Absent |
| `data/processed/`, `data/manifest.yaml`, `data/failures.json` | Absents |
| Python 3.12 via uv | Python 3.14, sans uv |

Deux points du plan lui-même sont à trancher en Phase 1 :

- `CLAUDE.md` écrit `config/params.yaml`, `MASTER_PROMPT.md` écrit `configs/`.
- `CLAUDE.md` liste parmi les « acquis validés » les 30 villes et Python 3.12, qui ne sont pas présents sur cette machine.

## 10. Non fait dans cette phase

Version allégée choisie par l'étudiant. Restent donc à faire :

- installer `uv` et Python 3.12 ;
- créer `pyproject.toml` et le fichier de verrouillage ;
- installer pandera, evidently, dvc et ruff, puis revérifier tous les imports sous Python 3.12.
