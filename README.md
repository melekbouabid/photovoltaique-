# SolarVision — prévoir la production photovoltaïque journalière

Mini-projet « Séries Temporelles pour Data Science & IA » (TEK-UP, option B : environnement et énergie).

**Objectif.** Prévoir de J+1 à J+7 la production d'une installation photovoltaïque de 1 kWc dans des villes de France,
de Tunisie et d'Espagne ; comparer trois technologies de modules ; chiffrer les bénéfices, avec leur incertitude.

Le dépôt contient deux générations de travail :

- **l'étude historique (v1)** sur 9 villes, avec l'analyse statistique détaillée de Tunis en R et en Python. Elle est
  complète : notebook, rapport, application. Sa description est dans [docs/README_v1.md](docs/README_v1.md) ;
- **la v2**, qui étend l'étude à 30 villes et à trois technologies, ajoute l'économie et une architecture reproductible.

## Démarrage rapide

```
python -m venv .venv
.venv\Scripts\Activate.ps1                    (Linux, macOS : source .venv/bin/activate)
pip install -e ".[dev,mlops]"
python -m solarvision.cli pipeline --fast     (3 villes, de la collecte au suivi)
python -m pytest -m "not data and not slow"
python -m solarvision.cli serve --fast        (application : http://127.0.0.1:8001)
```

Toutes les commandes, avec leurs durées, sont dans [RUN_ME.md](RUN_ME.md).

## Carte du dépôt

| Je cherche | Emplacement |
|---|---|
| Les villes, les paramètres, les hypothèses économiques | `configs/` |
| Le code de la v2 | `src/solarvision/` (une commande par étape : `python -m solarvision.cli --help`) |
| Les réponses brutes des API | `data/raw/<source>/<ville>/` |
| Les tables traitées, le panel, les découpages | `data/processed/` |
| L'origine, la licence et l'empreinte de chaque fichier | `data/manifest.yaml` |
| Les métriques, tests et recommandations | `reports/` |
| Le rapport de la v2 | `reports/rapport/` |
| Les modèles et la version en production | `models/registry/` |
| L'application multi-pages | `app/pages/` (servie par `python -m solarvision.cli serve`) |
| Le notebook de la v2 | `notebooks/solarvision_v2.ipynb` |
| Les tests | `tests/` |
| L'architecture, l'avancement, le guide de soutenance | `docs/` |
| Le code R, autonome | `r_standalone/` |
| L'étude historique | `mini_projet_python.ipynb`, `mini_projet_R.Rmd`, `python/`, `resultats/`, `rapport/`, `app/backend/`, `app/frontend/` |

## Documents

| Document | Contenu |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Schéma du pipeline, où trouver quoi, limites |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Ce qui est fait, ce qui reste, les bloquants |
| [docs/DEFENSE_GUIDE.md](docs/DEFENSE_GUIDE.md) | Chaque choix expliqué, avec les questions probables de soutenance |
| [docs/MIGRATION.md](docs/MIGRATION.md) | Correspondance entre les fichiers de la v1 et ceux de la v2 |
| [reports/conformite_v2.md](reports/conformite_v2.md) | Exigences de l'énoncé, fichier qui y répond, statut |

## Règles suivies

- Découpage chronologique 90/10, jamais aléatoire.
- Scénarios **ex ante** (rien du futur) et **ex post** (météo observée) toujours séparés ; seul le premier est opérationnel.
- Aucun chiffre du rapport n'est saisi à la main : tout vient de fichiers produits par le code.
- Une ville dont les données manquent est listée comme manquante ; elle n'est jamais simulée.
- Les hypothèses économiques sont marquées `TODO_VERIFY` : elles restent à vérifier.

## Données et licences

PVGIS 5.3 © Union européenne (JRC) ; Open-Meteo (réanalyse ERA5, CC BY 4.0) ; NASA POWER (LaRC) ; RTE éCO2mix via ODRÉ
(Licence Ouverte v2.0) ; Red Eléctrica (REData). Les productions PVGIS sont simulées, non mesurées.
Le fichier `.env` (clé de l'assistant de la v1) ne doit jamais être joint à une archive.
