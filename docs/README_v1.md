# Mini-projet Séries Temporelles - production photovoltaïque et éclairement (France, Tunisie, Espagne)

Option B (environnement et énergie). Point de départ : le rapport SolarVision-MLOps, qui estimait la
production solaire d'une toiture à Tunis avec une irradiation supposée de 1 800 kWh/m²/an « à remplacer
par la valeur PVGIS ». Le lien PVGIS de ce rapport est interrogé pour 9 villes sur 2005-2023.

**Question de modélisation :** peut-on prévoir à 7 jours la production journalière d'une installation
photovoltaïque à Tunis, et que gagne-t-on à connaître la météo à venir ?

## Contenu

| Fichier ou dossier | Rôle |
|---|---|
| `rapport/Rapport_solarvision_series_temporelles.docx` et `.pdf` | Rapport (environ 22 pages hors annexes) |
| `mini_projet_python.ipynb` | Notebook Python exécuté : sections 1 à 6, extensions, prompts du LLM |
| `mini_projet_R.Rmd` et `mini_projet_R.html` | Notebook R : sections 1, 2, 3 et 6 (socle classique), et sa version compilée |
| `python/collecte_donnees.py` | Lecture des liens du PDF, appels aux API, contrôle qualité, construction des 14 jeux de données |
| `python/partie_A.py`, `partie_B.py`, `partie_C.py` | Sources du notebook Python ; `construire_notebook.py` les assemble |
| `python/entrainer_modeles_app.py` | Entraîne les modèles servis par l'application (LSTM global, ARIMA-Fourier par ville) |
| `python/creer_archive.py` | Crée l'archive .zip à remettre, sans la clé (`.env`) ni les environnements (`.venv`, `node_modules`) |
| `data/datasets/` | Les 14 jeux de données ; fiches dans `data/LISEZMOI_donnees.md`, catalogue dans `data/catalogue_datasets.json` |
| `sources/` | Rapport SolarVision et résultat de la visite de ses 21 liens |
| `llm/` | Interprétation experte (rédigée avant), prompts, réponses intégrales, script d'interrogation |
| `rag/` | Assistant RAG : documents, construction du corpus, moteur BM25 + LLM, évaluation |
| `app/` | Application web (FastAPI + React) : formulaire de prévision et assistant |
| `Dockerfile`, `docker-compose.yml`, `.env.example` | Conteneurs (application, notebook Python) et modèle du fichier de clé |
| `figures/`, `resultats/` | Figures et tableaux produits par les notebooks |

## Les jeux de données

Chacun des 14 jeux compte plus de 1 000 lignes et au moins 20 variables explicatives (contrôle dans
`data/catalogue_datasets.json`, champ `conforme`).

| Jeu | Contenu |
|---|---|
| `fr_`, `tn_`, `es_photovoltaique_journalier.csv` | Production d'1 kWc et plus de 30 variables explicatives, 3 villes par pays, 2005-2023 |
| `fr_`, `tn_`, `es_eclairement_journalier.csv` | Éclairement énergétique, éclairage naturel (lux, heures de lumière) et plus de 30 variables, 3 villes par pays |
| `panel_9_villes_journalier.csv` | Les 9 villes, 58 variables par jour (table de modélisation) |
| `mensuel_9_villes.csv`, `climatologie_9_villes.csv` | Agrégats mensuels et normales journalières |
| `horaire_9_villes_2023.csv.gz`, `tmy_9_villes.csv` | Série horaire 2023 et année météo type PVGIS |
| `pvgis_orientations_9_villes.csv` | Production mensuelle d'1 kWc pour 27 scénarios par ville : 5 inclinaisons x 5 orientations, plan horizontal et pente optimale |
| `fr_solaire_national_rte_journalier.csv`, `es_fotovoltaica_ree_journalier.csv` | Production solaire nationale mesurée (validation externe, cointégration) |

Sources : PVGIS (JRC, lien du rapport), Open-Meteo (ERA5), NASA POWER, RTE éCO2mix (ODRÉ), REE. La table de
référence `data/reference/pvgis_synthese_9_villes.csv` (9 lignes : pente optimale et productible par ville) est lue
par les notebooks et l'application ; elle n'est pas comptée parmi les jeux de données.

## Reproduire l'étude

```
python -m venv .venv
.venv\Scripts\activate                     (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
python python/collecte_donnees.py          (20 minutes ; inutile si data/datasets/ est fourni)
python -m nbconvert --to notebook --execute --inplace mini_projet_python.ipynb     (15 minutes, CPU)
```

Le notebook lance lui-même la collecte si `data/datasets/` est vide (connexion Internet nécessaire).

**R** (5 minutes) :

```
install.packages(c("forecast", "urca", "vars", "tseries", "FinTS", "rugarch", "lmtest", "jsonlite", "rmarkdown"))
rmarkdown::render("mini_projet_R.Rmd")
```

Exécuter le notebook R avant le notebook Python permet à ce dernier d'afficher la comparaison R / Python.

**Notebook Python avec Docker**, sans installer Python (la commande réécrit le notebook, `figures/` et `resultats/`) :

```
docker compose --profile etude run --rm notebook
```

**Section 5 (LLM)** : le notebook écrit les prompts dans `llm/`. `python llm/interroger_llm.py` les envoie à un
modèle local servi par Ollama (`qwen3-vl:8b-instruct`) ; il refuse de s'exécuter tant que
`llm/interpretation_experte.md` (notre lecture, rédigée avant) n'existe pas.

**Rapport** : `python rapport/construire_rapport.py` remplit les tableaux à partir de `resultats/`, puis produit
le Word (pandoc) et le PDF (impression Chromium via Playwright).

## Application et assistant

**Avec Docker** (recommandé) :

```
copy .env.example .env                     (Linux/macOS : cp) puis y coller la clé GROQ_API_KEY
docker compose up --build
```

Ouvrir http://localhost:8000. L'assistant RAG fait rédiger ses réponses par un LLM hébergé par Groq
(`openai/gpt-oss-120b`) ; sans clé ou sans réseau, il répond par extraits des passages retrouvés. Le fichier `.env`
contient un secret : il n'est ni copié dans l'image ni à joindre à l'archive remise.

**Sans Docker** :

```
python python/entrainer_modeles_app.py     (10 minutes, une fois)
python rag/construire_corpus.py
cd app/frontend && npm install && npm run build && cd ../..
cd app/backend && uvicorn main:app --port 8000
```

Ouvrir http://localhost:8000 (documentation de l'API : http://localhost:8000/docs). Détails dans `app/README.md`.

## Correspondance avec l'énoncé

| Exigence | Où |
|---|---|
| 1. Données, objet série temporelle, découpage 90/10, sources | notebook 1, rapport 2, `data/LISEZMOI_donnees.md` |
| 2. Visualisation, ACF/PACF commentées, décomposition, aberrants, ADF + KPSS | notebook 2.1 à 2.6, rapport 3 |
| 3.1 ARIMA/SARIMA manuel et automatique, diagnostic complet | notebook 3.1 et 3.1 bis, R, rapport 4.1 |
| 3.2 VAR, Granger, Johansen et Engle-Granger, VECM | notebook 3.2, R, rapport 4.2 |
| 3.3 ARCH-LM, GARCH(1,1) et ordres supérieurs, diagnostic, volatilité et événements | notebook 3.3, R, rapport 4.3 |
| 4.1 LSTM et GRU, fenêtres, normalisation, courbes de perte, validation croisée temporelle | notebook 4.1, rapport 5.1 |
| 4.2 Hybride ; 4.3 Prophet (et XGBoost, LSTM global) | notebook 4.2 et 4.3, rapport 5.2 et 5.3 |
| 5. LLM : hypothèses, vulgarisation, recommandations, comparaison humain / LLM | `llm/`, rapport 7 et annexe A |
| 6. Prévision h = 7, intervalles, MSE/RMSE/MAE/MAPE, Diebold-Mariano, conclusion | notebook 6, R, rapport 6 |
| 7. Extensions : variables exogènes, corrélation dynamique (la détection d'événements par embeddings de texte n'est pas traitée) | notebook 7, rapport 8 |
| 8. Code R et Python commenté, rapport, notebook exécutable, discussion critique | ce dossier, rapport 9 |

## Reproductibilité

- Graine fixée à 42 dans les deux langages ; PyTorch en mode déterministe, sur CPU.
- Les réponses des API sont mises en cache dans `data/brut/` (non livré, sauf la série horaire de Tunis) ; une
  relance de la collecte ne retélécharge que ce qui manque. Les données PVGIS d'une même version de base sont
  stables ; Open-Meteo, NASA POWER, RTE et REE peuvent être révisés par leurs producteurs.
- Les résultats des réseaux de neurones peuvent différer légèrement d'une machine à l'autre (bibliothèques
  d'algèbre linéaire) ; l'écart-type entre graines est donné dans le notebook.
