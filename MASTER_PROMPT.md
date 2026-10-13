## 0. Contexte et objectifs

Tu es un ingénieur senior Data Science / MLOps. Tu fais évoluer le dépôt SolarVision (copie originale, sans les dernières mises à jour) pour produire une version v2 professionnelle, reproductible et conforme au cahier des charges.

Objectifs de la v2 :
1. Étude sur **30 villes** (10 par pays : France, Tunisie, Espagne) au lieu de 9.
2. **Recommander la technologie PV la plus fiable par ville** (crystSi, CIS, CdTe) avec incertitude.
3. **Chiffrer les bénéfices** (économies, payback, VAN, CO₂ évité) avec intervalles.
4. **Architecture data science / MLOps professionnelle et lisible** (où sont les données, les modèles, les rapports).
5. **Application multi-pages** (une URL par page) et rapport avec un chapitre par page.
6. **Dossier R isolé** (`r_standalone/`) contenant tout le code R existant, sans aucun lien avec le reste du projet.
7. Livrables du cahier des charges intacts : code R ET Python (socle classique), notebook exécutable, rapport 15–25 pages, section LLM, discussion critique.

Date limite : 12/10/2026 23h55. Priorités : **P0** = obligatoire pour la note ; **P1** = forte valeur ; **P2** = bonus si le temps le permet.

| Phase | Contenu | Priorité |
|---|---|---|
| 0 | Prise en main, sauvegarde, audit, environnement | P0 |
| 1 | Architecture professionnelle (squelette) + dossier R isolé | P0 |
| 2 | Données 30 villes (ingestion, imputation, qualité, manifeste) | P0 |
| 3 | Panel, splits, tests anti-fuite | P0 |
| 4a | Modèles classiques/ML sur 30 villes + tests DM corrects | P0 |
| 4b | LSTM/GRU/LSTM global (walk-forward) | P0 (barème bloc B) |
| 5 | Technologies PV : score de fiabilité + recommandeur | P1 |
| 6 | Économie et bénéfices (Monte-Carlo) | P1 |
| 7 | MLOps : pipeline, registre, promotion/rollback, API, monitoring, CI, Docker | P1 |
| 8 | Application multi-pages | P2 (version minimale P1) |
| 9 | Notebook, rapport, section LLM (gabarit), guide de soutenance | P0 |
| 10 | Audit final de conformité | P0 |

Règle d'or : à la fin de chaque phase, **arrête-toi**, résume (≤ 10 lignes), mets à jour `docs/PROGRESS.md`, attends mon « continue ».

---

## 1. Acquis d'une session précédente (à reproduire ou à réutiliser)

Cette section décrit ce qui a déjà été fait sur un autre PC. Si `_import_pc1/` existe, **audite-le** (ne lui fais pas confiance aveuglément : relance les tests) puis réutilise-le. Sinon, recrée-le.

**Villes (`config/cities.yaml`)** : champs `id, nom, pays, code_pays, lat, lon, altitude, fuseau, zone_climatique`.
- France : paris, lyon, marseille, toulouse, bordeaux, nantes, lille, strasbourg, nice, montpellier.
- Tunisie : tunis, sfax, tozeur, sousse, bizerte, gabès, kairouan, gafsa, médenine, tataouine.
- Espagne : madrid, séville, barcelone, valence, malaga, saragosse, bilbao, murcie, grenade, palma.
- Vérifie lat/lon/altitude de chaque ville contre une source fiable (une erreur fausse toute la ville). Ajouter une ville = ajouter une entrée YAML, sans changer le code.

**Collecte (`collecte_donnees.py`, options CLI)** : `--fast` (3 villes, une par pays, dans `data/fast/`, sans toucher aux données historiques), `--retry-failed` (ne traite que `data/failures.json`), `--reprocess` (reconstruit les tables traitées depuis le cache, sans réseau), `--quality-only` (régénère les rapports qualité), `--allow-partial` (panel partiel avec métadonnées `villes_manquantes`).
- PVGIS (5.3) : par ville, 17 appels (1 PVcalc + 4 horizontaux + 12 technologiques sur sous-périodes), technologies `crystSi`, `CIS`, `CdTe`, 1 kWc, pertes 14 %, inclinaison optimale, plein sud, 2005–2023. Sortie : `pv_crystSi_kwh_kwc`, `pv_CIS_kwh_kwc`, `pv_CdTe_kwh_kwc`.
- Open-Meteo/ERA5 : **une seule requête par ville** pour 2005–2023, 10 variables (cloud_cover_mean, sunshine_duration, daylight_duration, precipitation_sum, relative_humidity_2m_mean, dew_point_2m_mean, pressure_msl_mean, wind_gusts_10m_max, et0_fao_evapotranspiration, shortwave_radiation_sum). Pause de 180 s entre villes. L'offre gratuite a des quotas (d'après mes informations : environ 600/min, 5 000/h, 10 000/jour ; à vérifier). Un HTTP 429 doit lire `Retry-After`, attendre, puis écrire l'heure de reprise dans `data/failures.json` si le quota est horaire/journalier. Le quota heure UTC se réinitialise à l'heure pile.
- NASA POWER : 1 requête par ville (GHI `ghi_nasa_kwh_m2`).
- Cache par ville et par source dans `data/raw/<source>/<ville>/`, écriture atomique (`.part` puis remplacement), reprise sans retélécharger, manifeste YAML (source, paramètres, date, SHA256, période, unités, fuseau, licence), journal des échecs.
- **Imputation PVGIS par NASA POWER** (règle réglée sur Tunis) : un jour est imputé si (1) `hauteur_soleil_midi_deg - hauteur_soleil_max_deg > 5°` OU (2) `ghi_pvgis < 0,25 × ghi_nasa` ET `ghi_nasa > 1,5 kWh/m²`. Valeur imputée = ratio PVGIS/NASA médian roulant sur 31 jours × NASA, appliqué de façon cohérente aux 3 technologies. Colonne `jour_impute_pvgis` conservée.
  - **Vérification non circulaire obligatoire** : à Tunis, les 13 dates imputées doivent être exactement : 2005-04-18, 2008-01-23, 2008-03-01, 2008-03-06, 2008-05-17, 2008-05-18, 2009-04-18, 2009-04-19, 2009-08-15, 2009-08-16, 2014-12-02, 2016-10-16, 2016-10-17 (celles de `data/datasets/tn_photovoltaique_journalier.csv`).
  - Les mêmes dates apparaissent dans toutes les villes (trous PVGIS systématiques) ; attendu : 11 à 15 jours imputés par ville. Ne jamais traiter une table avant que l'imputation soit active (piège rencontré : 18 villes traitées sans imputation ; la commande `--reprocess` existe pour ça).
- Résultat attendu : 30 tables dans `data/processed/<ville>.csv` (colonnes : date, 3 séries PV, jour_impute_pvgis), 6939 lignes chacune.

**Panel** : `panel_journalier_30_villes.parquet` (208170 lignes, ~51 colonnes), colonnes ville/pays/lat/lon/altitude, calendrier, Fourier annuel (2 harmoniques), retards 1 et 7 jours, moyenne glissante passée 7 jours, météo, NASA POWER ; features **ex_ante** et **ex_post** clairement séparées ; `splits_90_10.yaml` (coupures par ville) ; colonne/métadonnée `villes_manquantes`.

**Protocole de modélisation 4a** : persistance, climatologie, ARIMA+Fourier(2), XGBoost (features ex_ante), Prophet ; horizons J+1…J+7 ; **évaluation de chaque date de test** avec **réajustement tous les 30 jours** (paramètre dans `config/params.yaml`) — ne pas confondre fréquence de réajustement et fréquence d'évaluation (piège rencontré : une évaluation mensuelle seulement). crystSi : les 5 modèles ; CIS et CdTe : persistance, climatologie, XGBoost. Sauvegarder les prévisions et observations par date dans `reports/forecasts/<ville>.parquet` (pour recalculer métriques et DM sans réentraîner). Durée mesurée : 6 min pour 3 villes ; ~60–90 min estimées pour 30 villes (lancer en tâche de fond avec reprise par ville).

**Références Tunis (étude historique, `resultats/py_metriques.csv`)** : climatologie RMSE 1,1002 ; ARIMA+Fourier 1,0892 ; XGBoost 1,0834 ; Prophet 1,0969 ; LSTM ex ante 1,0823 ; GRU ex ante 1,0820 ; LSTM global 1,0778 ; ex post : SARIMAX 0,7252, LSTM 0,6990, GRU 0,7135. **Écart non résolu à diagnostiquer** : le nouveau protocole donnait pour Tunis climatologie 1,131 et XGBoost 1,109 (moyenne J+1…J+7). Cause à établir (définition de la climatologie ? agrégation ? fenêtre de test 694 jours vs 688 origines ? features XGBoost ?), pas à attribuer au panel sans preuve.

**Pièges statistiques rencontrés** : (a) p-values Holm identiques pour tous les modèles (famille de test mal définie) ; (b) DM sans variance de long terme ; (c) tests « circulaires » (vérifier une règle avec elle-même).

---

## 2. Architecture cible (professionnelle, niveau MLOps 2 en local)

Inspirée de Cookiecutter Data Science + bonnes pratiques MLOps (reproductibilité, versionnement des données et des modèles, validation, suivi d'expériences, CI/CD, supervision, gouvernance). Applique-la **progressivement** : le nouveau code naît dans la nouvelle structure ; les scripts historiques sont déplacés seulement quand les tests passent, avec un wrapper de compatibilité et une table de correspondance dans `docs/MIGRATION.md`.

```
solarvision/
├── README.md                  # 1 page : objectif, démarrage rapide, carte du dépôt
├── CLAUDE.md  CHANGELOG.md  LICENSE
├── pyproject.toml  uv.lock    # dépendances verrouillées (Python 3.12)
├── Makefile  justfile?        # raccourcis ; la vraie CLI est python -m solarvision.cli
├── dvc.yaml  params.yaml?     # pipeline reproductible (voir §MLOps) ; params centralisés dans configs/
├── .pre-commit-config.yaml    # ruff, format, nettoyage notebooks, détection de secrets
├── .env.example  .gitignore  .dvcignore
│
├── configs/                   # TOUTE la configuration, aucune valeur en dur dans le code
│   ├── cities.yaml  params.yaml  reliability.yaml  economics.yaml  logging.yaml
│
├── data/                      # versionné par DVC (pas dans Git) ; jamais modifié à la main
│   ├── raw/        # brut immuable : pvgis/ open_meteo/ nasa_power/ rte/ ree/
│   ├── interim/    # nettoyé / imputé
│   ├── processed/  # tables par ville, panel, splits
│   ├── external/   # données tierces (RTE, REE, anciens jeux data/datasets)
│   └── manifest.yaml   # data card machine-lisible : source, licence, SHA256, période, unités
│
├── models/                    # artefacts (DVC/MLflow)
│   ├── registry/<nom>/<version>/{model, manifest.json, metrics.json, model_card.md}
│   └── registry/current.json  # pointeur « Production »
│
├── src/solarvision/           # package Python installable (pip install -e .)
│   ├── cli.py                 # typer : ingest | validate | features | train | evaluate | economics | recommend | register | serve | report
│   ├── config.py              # chargement/validation de configs/ (pydantic)
│   ├── data/                  # ingestion, imputation, qualité (Pandera), manifeste
│   ├── features/              # panel, calendrier, Fourier, retards, ex_ante/ex_post, splits
│   ├── models/                # baselines.py statistical.py (ARIMA/SARIMA/VAR/GARCH) ml.py (XGBoost/Prophet) deep.py (LSTM/GRU/global)
│   ├── evaluation/            # métriques, walk-forward, Diebold-Mariano (HLN), Holm, bootstrap par blocs
│   ├── recommender/           # fiabilité par technologie + modèle de recommandation (leave-one-city-out)
│   ├── economics/             # VAN, payback, TRI, LCOE, CO₂, Monte-Carlo
│   ├── mlops/                 # registre, promotion, rollback, intégrité SHA
│   ├── serving/               # API FastAPI (/v1/predict, /v1/recommend-tech, /v1/economics, /v1/cities, /v1/models, /health)
│   └── monitoring/            # dérive (Evidently), qualité des entrées, performance glissante
│
├── pipelines/                 # définition des étapes DVC / flows
├── notebooks/                 # numérotés : 01_exploration … 09_llm ; sorties nettoyées ; exécutables de bout en bout
├── app/                       # frontend multi-pages
├── tests/                     # unit/ data/ leakage/ api/ integration/ ; un test « smoke fast » de bout en bout
├── reports/                   # tables, figures, rapport généré (jamais saisi à la main)
├── docs/                      # architecture.md (Mermaid), PROGRESS.md, MIGRATION.md, adr/ (décisions), model_cards/, data_cards/, runbook.md, DEFENSE_GUIDE.md, llm/
├── infra/                     # Dockerfile (multi-stage), docker-compose.yml, .github/workflows/
├── scripts/                   # utilitaires ponctuels documentés
├── python/  mlops/  rapport/  # HISTORIQUE : conservés, migrés plus tard avec wrappers
└── r_standalone/              # ISOLÉ : voir §3 (aucun lien avec le reste)
```

**Règles MLOps à appliquer (checklist)** :
1. *Reproductibilité* : lockfile, seed, `params`, pipeline DVC (`dvc repro`), mode `--fast` (3 villes, peu d'époques) pour tests/CI.
2. *Contrats de données* : schémas Pandera par source et par table traitée ; échec → pipeline arrêté ; `manifest.yaml` + data cards.
3. *Suivi d'expériences* : MLflow (backend local SQLite/fichiers) avec params, métriques, hash des données, commit Git, seed, versions de librairies, tags `ville/technologie/scenario`.
4. *Registre et cycle de vie* : Staging → Production. **Règle de promotion codée** : un modèle n'est promu que s'il bat la climatologie ET la version courante sur les mêmes dates de test ; rollback par une commande ; vérification SHA au chargement ; model card générée à chaque version.
5. *Serving* : FastAPI versionnée `/v1`, schémas pydantic, `/health` (version du modèle, date d'entraînement, données utilisées, SHA vérifié), intervalles de prédiction dans les réponses, journalisation des requêtes.
6. *Monitoring* : rapport Evidently (dérive des entrées/cible), erreur glissante quand les observations arrivent, seuils d'alerte configurables. Documente honnêtement ce qui est fait en local et ce qui ne l'est pas (pas de cloud, pas de ré-entraînement automatique).
7. *CI* (GitHub Actions) : ruff, tests, `dvc repro --fast` (3 villes), exécution du notebook en mode fast, build Docker. Test de non-régression « golden metrics » (tolérance explicite).
8. *Gouvernance* : ADR (une décision = un fichier), CHANGELOG, versions sémantiques des modèles, section « limites et risques » dans chaque model card.
9. *Tests* : unitaires, données, anti-fuite temporelle, API, intégration fast.
10. *Sécurité/licences* : `.env.example`, pas de secrets, licence et attribution des données (PVGIS/JRC, Open-Meteo, NASA POWER, RTE, REE).

Livre `docs/architecture.md` avec : diagramme Mermaid (sources → ingestion → validation → features → entraînement → évaluation → registre → API/app → monitoring), tableau « où trouver quoi » (datasets, modèles, métriques, rapports), et les limites.

---

## 3. Dossier R isolé (`r_standalone/`)

Objectif : un dossier **totalement autonome** qui contient **tout le code R existant** du projet, sans aucun lien avec le reste du dépôt.

1. Inventorie tout le code R du dépôt : `*.R`, `*.Rmd`, `*.qmd`, chunks R de notebooks, scripts appelés par R, ainsi que les fichiers de config R (`renv.lock`, `DESCRIPTION`). Produis `r_standalone/INVENTAIRE.md` : fichier d'origine → fichier copié, rôle, entrées, sorties, packages utilisés.
2. **Copie** (ne déplace pas, ne modifie pas les originaux) dans `r_standalone/` avec cette structure :
   ```
   r_standalone/
   ├── README.md           # objectif, prérequis R, ordre d'exécution, durée, sorties
   ├── INVENTAIRE.md
   ├── renv.lock  (ou DESCRIPTION)   # packages et versions
   ├── run_all.R           # exécute tout dans l'ordre, s'arrête à la première erreur, journalise
   ├── R/                  # scripts copiés (01_exploration.R, 02_stationnarite.R, 03_arima.R, 04_var_coint.R, 05_garch.R, ...)
   ├── notebooks/          # Rmd copiés
   ├── data/               # COPIE des seuls jeux nécessaires (petits CSV) avec data/README.md (source, SHA256)
   └── outputs/            # figures, tables produites (générées, pas versionnées)
   ```
3. **Isolation stricte** : aucun chemin vers `..`, aucun `source()` ou `read.csv()` qui sort de `r_standalone/`, aucun chemin absolu. Utilise `here::here()` ancré par un fichier `.here` placé dans `r_standalone/`, ou `rprojroot`. Remplace les chemins par des chemins relatifs au dossier. Tous les paramètres (seed, dates de coupure 90/10) sont en tête de `run_all.R`.
4. Aucun fichier du projet principal ne doit référencer `r_standalone/` et inversement. Ajoute un test automatique (`tests/test_r_isolation.py`) qui scanne les fichiers et échoue si un chemin sort du dossier ou si le reste du dépôt le référence.
5. **Vérification réelle** : si R est installé, copie `r_standalone/` ailleurs (dossier temporaire hors dépôt), restaure l'environnement (`renv::restore()`), lance `Rscript run_all.R` et rapporte : réussite/échec par script, durée, fichiers produits. Si R n'est pas installé, dis-le, fais une vérification statique et liste ce qui reste à tester.
6. Le code R doit rester celui d'origine (même résultats). N'ajoute que : les chemins relatifs, les en-têtes de commentaires (« pourquoi »), la seed et les packages explicites. Signale tout script R qui dépendait d'un fichier produit par Python et comment tu l'as rendu autonome (copie du jeu d'entrée dans `data/`).
7. Cette partie ne dépend pas des 30 villes : elle couvre le socle classique existant (Tunis) exigé par le cahier des charges (R ET Python).

---

## 4. Phases détaillées

### Phase 0 — Prise en main (P0)
- Sauvegarde : crée une branche Git `backup-original` (ou un zip hors dépôt si pas de Git). Vérifie `git status`.
- Audit court → `docs/AUDIT_V1.md` : ce qui existe, ce qui est cassé, non portable (`.venv` ancien, chemins absolus), versions, tests.
- Environnement : Python 3.12 via uv, `pyproject.toml` + lockfile, vérifie les imports (pandas, statsmodels, arch, pmdarima, prophet, xgboost, torch, fastapi, pyarrow, pyyaml, pandera, mlflow, evidently, typer, pydantic). Dis ce qui échoue et propose une alternative. Lance les tests existants.
- Détecte `_import_pc1/` et décris précisément ce qu'il contient. Crée `docs/PROGRESS.md`.
- Ne modifie aucune logique de modélisation.

### Phase 1 — Architecture et R isolé (P0)
- Crée le squelette de §2 (dossiers vides avec `.gitkeep` + README courts, `pyproject.toml`, `cli.py` minimal, `config.py`, pre-commit, `.gitignore`, `.env.example`). Aucun script historique n'est déplacé dans cette phase.
- Écris `docs/architecture.md` (Mermaid) et `docs/MIGRATION.md` (ancien chemin → nouveau chemin, statut).
- Réalise le dossier R isolé (§3) et son test d'isolation.
- Montre `tree` (profondeur 2) et les résultats des tests.

### Phase 2 — Données 30 villes (P0)
- Si `_import_pc1/` est présent : vérifie les coordonnées de `cities.yaml`, relance les tests, copie le cache brut et les scripts audités dans la structure. Sinon : implémente l'ingestion décrite en §1 dans `src/solarvision/data/` (ou en étendant `collecte_donnees.py` avec wrapper), puis collecte.
- Collecte réelle d'abord en `--fast` (Paris, Tunis, Madrid) dans `data/fast/`, montre fichiers, lignes, période, colonnes. Puis les 30 villes en tâche de fond, avec reprise. Gère les 429 (lecture de `Retry-After`, arrêt propre avec heure de reprise).
- Imputation active **avant** tout traitement ; vérifie les 13 dates de Tunis (test non circulaire), puis le tableau des jours imputés par ville.
- Sorties : 30 tables traitées, `data/manifest.yaml`, rapports qualité par ville (manquants, imputés, aberrants IQR, statut ok/failed — produits par le pipeline, pas par script manuel), `data/failures.json`.
- Tests : schéma Pandera, 30 tables x 6939 lignes, couverture des 3 technologies, cohérence de l'imputation.
- Ne simule jamais une ville manquante.

### Phase 3 — Panel, splits, anti-fuite (P0)
- Construis le panel (§1), `splits_90_10.yaml`, features ex_ante/ex_post séparées, nom du fichier = nombre réel de villes + alias de compatibilité, métadonnée `villes_manquantes`.
- Test anti-fuite : aucune feature ex_ante à la date t n'utilise d'information postérieure à t (retards, moyennes glissantes passées, Fourier calendaire) ; split sans mélange de dates.
- Garde la compatibilité avec l'ancien `panel_9_villes_journalier.csv`.

### Phase 4a — Modèles classiques et ML (P0)
- Conserve l'étude statistique détaillée de Tunis (notebooks Python et code R) : ADF/KPSS, ACF/PACF (brute et différenciée, avec interprétation écrite), STL, ARIMA/SARIMA identifiés à la main puis comparés à `pmdarima`, diagnostics (Ljung-Box, Shapiro/Jarque-Bera, ARCH-LM), VAR (AIC/BIC) + Granger + Johansen/VECM si justifié, GARCH (diagnostic des résidus standardisés, volatilité conditionnelle).
- Protocole pour toutes les villes : voir §1 « Protocole de modélisation 4a ».
- **D'abord** : diagnostique l'écart sur Tunis avec l'étude historique (§1) et explique la cause avec preuves avant de lancer les 30 villes.
- Estime le temps et prototype sur 3 villes, puis lance les 30 villes en tâche de fond avec reprise, en sauvegardant les prévisions.
- Évaluation : MSE, RMSE, MAE, MAPE, WAPE ; DM correct (HLN, h-1 retards, famille Holm par (ville, technologie, horizon), pertes carrée et absolue) ; tableau unique de tous les modèles.
- Sorties : `reports/metrics_tidy.csv` (ville, pays, technologie, modele, horizon, scenario, metrique, valeur), `reports/dm_tests.csv`, `reports/synthese_ville.csv` (meilleur modèle ex_ante, gain vs climatologie, erreur par horizon et saison).
- Analyse de sensibilité : métriques avec et sans jours imputés.

### Phase 4b — Réseaux de neurones (P0 pour le barème)
- Réutilise l'existant (`entrainer_modeles_app.py`, `partie_B.py`) : LSTM/GRU par ville (fenêtre 14 jours, couche cachée 64 dans l'étude historique), LSTM global multi-villes avec embedding de ville, hybride ARIMA+LSTM (optionnel, valorisé).
- Validation walk-forward temporelle (jamais de k-fold), courbes de perte train/validation, dropout et fenêtre justifiés, scénarios ex_ante et ex_post séparés.
- Estime le temps AVANT : pleine étude sur Tunis, protocole allégé (peu d'époques, early stopping) sur les autres villes, mode `--fast`.
- Même table `metrics_tidy`, mêmes dates de test que 4a, DM contre la climatologie.

### Phase 5 — Technologies PV (P1)
- Données : les 3 technologies sont déjà collectées. Analyse secondaire : 3 orientations (sud, est-ouest, optimale) pour la technologie retenue (appels PVGIS supplémentaires si le quota le permet, sinon signaler).
- `configs/reliability.yaml` : score de fiabilité **calculé** (jamais subjectif) : (1) prévisibilité = WAPE/RMSE du meilleur modèle ex_ante ; (2) stabilité = coefficient de variation journalier/mensuel et écart P10–P50 de la production annuelle ; (3) sensibilité à la température (pente production vs température, perte les jours > 35 °C) ; (4) performance en faible irradiation ; (5) rendement annuel (kWh/kWc/an). Normalisation par pays, poids configurables, **analyse de sensibilité des poids**, version Pareto sans score composite.
- `src/solarvision/recommender/` : modèle qui prédit la technologie la plus fiable à partir des caractéristiques de la ville (latitude, altitude, irradiation et température moyennes/maximales, nébulosité, variabilité), **validation leave-one-city-out**, comparaison avec la règle simple « meilleur score ». Intervalles par bootstrap par blocs. Si l'écart entre technologies est dans la marge d'incertitude, le dire (« ex æquo ») au lieu de forcer un gagnant.
- Sorties : `reports/tech_recommendation.csv` (ville, techno recommandée, score, 2ᵉ choix, incertitude, justification chiffrée), graphiques, carte.
- Limites à écrire : simulations PVGIS (pas des mesures), dégradation et fiabilité mécanique non modélisées par PVGIS.

### Phase 6 — Bénéfices économiques (P1)
- `configs/economics.yaml` : tous les paramètres sont des hypothèses `TODO_VERIFY` avec leur source à confirmer (STEG Tunisie ; EDF OA/CRE France ; PVPC / compensation des excédents Espagne) : prix d'achat, rachat, autoconsommation, coût d'investissement par technologie (€/kWc), O&M, durée de vie 25 ans, dégradation, taux d'actualisation, inflation de l'énergie, taux de change, facteur d'émission CO₂.
- Calculs par ville × technologie : kWh/kWc/an, économie annuelle, revenu de rachat, payback, VAN sur 25 ans, TRI, LCOE, CO₂ évité.
- Valeur de la prévision : plan basé sur la climatologie vs meilleur modèle ex_ante avec un modèle de coût d'erreur explicite ; si le gain est faible, l'afficher tel quel.
- Monte-Carlo sur les hypothèses (P10/P50/P90 pour VAN et payback). Aucune valeur unique sans intervalle. Tests unitaires sur VAN et LCOE avec cas calculés à la main.
- Sorties : `reports/economics_by_city.csv`, classement, graphiques (barres, tornado). Mention explicite : ce n'est pas un conseil financier.

### Phase 7 — MLOps (P1)
- Applique la checklist de §2 : DVC (`dvc.yaml` des étapes ingest → validate → features → train → evaluate → recommend → economics → register), MLflow (tracking + registre), règle de promotion codée, rollback, API FastAPI `/v1`, monitoring Evidently, Docker multi-stage + compose (`api`, `app`, `mlflow`, `monitoring`), CI GitHub Actions.
- Migre progressivement l'ancien `mlops/registry` avec note de migration (version active : conserver la lisibilité de `current.json`).
- Page ou rapport « Architecture & registre » : datasets (depuis `manifest.yaml`), modèles (depuis MLflow), version active, dérive.

### Phase 8 — Application multi-pages (P2 ; version minimale P1)
Une URL par page, navigation commune, toutes les données issues de l'API ou de `reports/` (rien en dur) : 1 Accueil (KPI, carte) ; 2 Villes ; 3 Prévisions (J+1…J+7, intervalles, ex_ante vs ex_post étiquetés) ; 4 Technologies PV ; 5 Économie (curseurs d'hypothèses, intervalles) ; 6 Comparaison des villes ; 7 Modèles & métriques (tableau unique, DM) ; 8 Architecture MLOps ; 9 Méthodologie & limites. Test : chaque page se charge, ex_ante/ex_post visibles.

### Phase 9 — Notebook, rapport, LLM, soutenance (P0)
- Notebook exécutable de bout en bout (Jupyter ; Rmd pour la partie R), seed fixée, versions de packages en en-tête, exécutable en `--fast` sans erreur sur une machine vierge (testé via une exécution propre).
- Rapport (Word ou PDF) généré par `python -m solarvision.cli report` à partir des artefacts : 15–25 pages hors annexes, **un chapitre par page** (saut de page, table des matières). Chapitres : introduction/thématique (justifiée en une phrase), données et 30 villes, exploration, modèles classiques, modèles avancés, technologies PV, économie, architecture MLOps, IA générative, prévision et évaluation, discussion critique. Aucun chiffre saisi à la main.
- **Section LLM (4 points du barème)** : prépare `docs/llm/` avec gabarits et scripts qui produisent les statistiques descriptives (moyenne, variance, skewness, kurtosis, ADF/KPSS) à fournir au LLM ; fichiers vides à compléter pour : prompt n°1 (hypothèses de modèles) + réponse intégrale ; prompt n°2 (explication vulgarisée pour décideur, en annexe) ; prompt n°3 (recommandations de gestion avec limites que le LLM formule lui-même, puis complétées de façon critique) ; **interprétation experte de l'étudiant à rédiger AVANT de solliciter le LLM** (ne la rédige pas à sa place) ; tableau « convergences / erreurs / simplifications / causalités inventées / p-values inventées du LLM ». Le barème note la détection des erreurs du LLM.
- `docs/DEFENSE_GUIDE.md` : pour chaque choix (split, imputation, ordres ARIMA, GARCH, DM/Holm, walk-forward, score de fiabilité, économie, architecture), explication en 5 lignes + 3 questions probables de soutenance avec réponses. L'étudiant doit pouvoir défendre tout le code.
- Discussion critique : limites des modèles, hypothèses violées, avantages/inconvénients de l'IA générative dans le domaine.

### Phase 10 — Audit final (P0)
- Relis le cahier des charges point par point → `reports/conformite_v2.md` : exigence → fichier qui la satisfait → statut (fait / partiel / non fait). Liste honnêtement ce qui n'a pas pu être fait ou vérifié (quota, temps de calcul, hypothèses à confirmer).
- Exécute `python -m solarvision.cli` fast de bout en bout depuis un clone propre, tests complets, notebook, test d'isolation R.
- Génère `RUN_ME.md` (commandes exactes, PowerShell et bash) et `CHANGELOG_V2.md`. Prépare l'archive `.zip` à envoyer (code + rapport + notebook), sans `.venv`, sans `data/raw` volumineux, avec `data/manifest.yaml` expliquant comment reconstruire.

---

## 5. Idées supplémentaires (ajoute-les quand la priorité le permet)

- **[P1] Intervalles de prédiction** : conformal prediction (split conformal) ou quantiles pour XGBoost/LSTM, évaluation de la couverture empirique (cible 80/95 %).
- **[P1] Analyse de sensibilité aux jours imputés** (avec/sans) sur Tunis et sur 3 villes, dans le rapport.
- **[P1] Clustering climatique des villes** (k-means sur irradiation, température, nébulosité) pour justifier un LSTM global ou des modèles par cluster.
- **[P1] Model cards et data cards** pour chaque modèle promu et chaque source.
- **[P1] Test de non-régression « golden metrics »** en CI (tolérance explicite).
- **[P2] Vrai ex ante météo** : prévisions météo historiques archivées (Open-Meteo « Historical Forecast API », à vérifier : disponibilité et période) sur la fenêtre de test pour remplacer l'ex post par un scénario opérationnel ; attention au quota.
- **[P2] Dégradation annuelle** des modules et comparaison d'orientations dans le calcul économique.
- **[P2] Carte interactive** des villes (folium/plotly) dans l'app et le rapport.
- **[P2] Corrélation dynamique** entre deux séries (corrélation glissante ou DCC-GARCH, bonus du cahier des charges, section 7) pour deux villes proches (ex. Tunis/Sfax).
- **[P2] N-BEATS ou TFT** sur Tunis (bonus bloc D), seulement si tout le reste est validé.

---

## 6. Critères d'acceptation globaux

- Un clone propre + `uv sync` + une commande reproduit le mode fast de bout en bout ; le notebook s'exécute sans erreur.
- 30 villes, 10 par pays, ajout d'une ville par simple entrée YAML.
- Tunis : 13 dates imputées identiques à l'ancien jeu ; panel 208170 lignes ; split 6245/694.
- Une technologie recommandée par ville avec incertitude et justification chiffrée.
- Bénéfices par ville avec intervalles et hypothèses visibles et vérifiables.
- On trouve en 10 secondes où sont datasets, modèles, métriques et rapports (arborescence + `docs/architecture.md` + `manifest.yaml`).
- `r_standalone/` s'exécute seul, copié ailleurs, et aucun fichier du projet ne le référence.
- Ex ante et ex post toujours séparés ; aucun chiffre du rapport saisi à la main ; limites écrites honnêtement.
- `reports/conformite_v2.md` couvre tout le cahier des charges.

**Commence maintenant par la Phase 0 uniquement.**
