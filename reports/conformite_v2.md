# Conformité au cahier des charges — version 2

Audit du 11 octobre 2026.

> **Réserve.** Le PDF du cahier des charges (`Mini_Projet_Series_Temporelles_2026.pdf`) n'était pas dans le dossier. Les
> exigences ci-dessous viennent de la table de correspondance de la première étude (`docs/README_v1.md`, sections 1 à 8 de
> l'énoncé) et du plan de la v2 (`MASTER_PROMPT.md`). **Cette liste est à confronter au PDF avant le rendu.**

Statuts : **fait**, **partiel** (une partie manque, précisée), **non fait**.

## 1. Exigences de l'énoncé

| Exigence | Fichier qui la satisfait | Statut |
|---|---|---|
| 1. Données, objet série temporelle, découpage 90/10, sources | `mini_projet_python.ipynb` §1 ; `data/manifest.yaml` ; `data/processed/splits_90_10.yaml` ; rapport v2 ch. 2 | fait |
| 2. Visualisation, ACF et PACF commentées, décomposition, valeurs aberrantes | `mini_projet_python.ipynb` §2 ; notebook R ; rapport historique | fait, sur Tunis |
| 2. Tests ADF et KPSS | `reports/exploration_stats.csv` (30 villes) ; rapport v2 ch. 3 | fait |
| 3.1 ARIMA et SARIMA, identification manuelle et automatique, diagnostic | `mini_projet_python.ipynb` §3.1 ; notebook R ; rapport v2 ch. 4.1 | fait, sur Tunis |
| 3.1 Le même modèle sur toutes les villes | `src/solarvision/models/statistical.py` ; `reports/metrics_tidy.csv` | fait |
| 3.2 VAR, Granger, Johansen, VECM | `mini_projet_python.ipynb` §3.2 ; notebook R ; rapport v2 ch. 4.2 | fait, sur Tunis |
| 3.3 ARCH-LM, GARCH, diagnostic, volatilité | `mini_projet_python.ipynb` §3.3 ; notebook R ; rapport v2 ch. 4.3 | fait, sur Tunis |
| 4.1 LSTM et GRU, fenêtres, normalisation, courbes de perte, validation temporelle | `src/solarvision/models/deep.py` ; `reports/deep/` ; rapport v2 ch. 5 | fait |
| 4.2 Modèle hybride | `mini_projet_python.ipynb` §4.2 | partiel : fait sur Tunis en v1, non étendu aux 30 villes |
| 4.3 Prophet, XGBoost, LSTM global | `src/solarvision/models/ml.py`, `deep.py` ; rapport v2 ch. 5 | fait |
| 5. LLM : hypothèses, vulgarisation, recommandations, comparaison | v1 : `llm/` et rapport historique ; v2 : `docs/llm/` | partiel : statistiques et prompts générés ; **interprétation, réponses et comparaison à rédiger par le groupe** |
| 6. Prévision à 7 jours, intervalles, MSE, RMSE, MAE, MAPE | `reports/metrics_tidy.csv` ; `reports/coverage.csv` ; rapport v2 ch. 10 | fait |
| 6. Test de Diebold-Mariano, conclusion | `reports/dm_tests.csv` ; rapport v2 ch. 10.4 et 10.5 | fait |
| 7. Extension : variables exogènes | Scénario ex post (météo observée) ; rapport v2 ch. 5 et 10 | fait |
| 7. Extension : corrélation dynamique | `mini_projet_python.ipynb` §7 | partiel : fait en v1, non repris en v2 |
| 7. Extension : détection d'événements par embeddings de texte | — | non fait |
| 8. Code R et Python commenté | Dossier R autonome ; `src/solarvision/` ; `python/` | fait |
| 8. Rapport de 15 à 25 pages | `reports/rapport/Rapport_SolarVision_v2.pdf` : 24 pages hors sommaire et annexes | fait ; **noms du groupe à renseigner** |
| 8. Notebook exécutable | `notebooks/solarvision_v2.ipynb` (exécuté sans erreur) ; `mini_projet_python.ipynb` ; notebook R | fait |
| 8. Discussion critique | Rapport v2 ch. 11 | fait |

## 2. Objectifs de la version 2

| Objectif | Résultat | Statut |
|---|---|---|
| Étude sur 30 villes, 10 par pays | 30 villes traitées, 6 939 jours chacune, panel de 208 170 lignes | fait |
| Recommander la technologie la plus fiable par ville, avec incertitude | `reports/tech_recommendation.csv` ; 5 villes déclarées ex æquo | fait |
| Chiffrer les bénéfices avec intervalles | `reports/economics_by_city.csv` (P10, P50, P90) | fait ; **hypothèses non vérifiées** |
| Architecture lisible et reproductible | `docs/architecture.md`, `data/manifest.yaml`, registre, suivi | partiel : voir section 4 |
| Application multi-pages, rapport avec un chapitre par page | `app/pages/` (9 pages) ; rapport généré | fait |
| Dossier R isolé | Exécuté seul hors du projet ; tableaux identiques à l'étude d'origine | fait |
| Livrables de l'énoncé intacts | Aucun fichier de la v1 déplacé ni modifié | fait |

## 3. Critères d'acceptation du plan

| Critère | Constat | Statut |
|---|---|---|
| Un clone propre et une commande reproduisent le mode rapide | Clone Git neuf, `pipeline --fast` réussi de la collecte au suivi, puis rapport et tests | partiel : le cache brut des 3 villes a été copié dans le clone (quota d'Open-Meteo épuisé ce jour-là) ; `uv sync` non utilisé |
| Le notebook s'exécute sans erreur | 15 cellules de code exécutées, 0 erreur | fait |
| 30 villes, ajout d'une ville par une entrée YAML | `configs/cities.yaml` | fait |
| Tunis : 13 dates imputées identiques à l'ancien jeu | Test contre l'ancien jeu de données | fait |
| Panel de 208 170 lignes, découpage 6 245 / 694 | `data/processed/panel_meta.yaml`, `splits_90_10.yaml` | fait |
| Une technologie recommandée par ville, avec incertitude et justification chiffrée | Colonnes `probabilite_meilleure`, `ex_aequo`, `justification` | fait |
| Bénéfices par ville avec intervalles et hypothèses visibles | `configs/economics.yaml`, tout marqué `TODO_VERIFY` | fait |
| On trouve en 10 secondes où sont données, modèles, métriques, rapports | Carte du dépôt dans `README.md` ; `docs/architecture.md` | fait |
| Le dossier R s'exécute seul et rien ne le référence | Test d'isolation ; exécution hors du projet | fait |
| Ex ante et ex post séparés ; aucun chiffre saisi à la main ; limites écrites | Colonne `scenario` partout ; rapport généré ; chapitres 8.5 et 11 | fait |

## 4. Règles du projet (`CLAUDE.md`)

| Règle | Constat | Statut |
|---|---|---|
| Découpage chronologique 90/10 | `int(n * 0.9)`, testé | fait |
| Ex ante et ex post séparés | Rôle de chaque colonne déclaré et testé | fait |
| Aucun chiffre saisi à la main dans le rapport | Rapport généré par `python -m solarvision.cli report` | fait |
| Tests statistiques explicites (hypothèses, famille, Holm, sens, perte) | Rapport ch. 10.4 ; colonnes de `reports/dm_tests.csv` | fait |
| Diebold-Mariano avec h - 1 retards et correction HLN | Vérifié contre `forecast::dm.test` de R | fait |
| Jours imputés visibles, analyse de sensibilité | Colonne `jour_impute_pvgis` ; `reports/sensitivity_imputed.csv` | fait |
| Valeurs économiques en configuration, marquées `TODO_VERIFY` | `configs/economics.yaml`, testé | fait |
| Ne jamais simuler de données | Dix villes sont restées « manquantes » jusqu'au retour du quota | fait |
| Python 3.12 par `uv`, fichier de verrouillage | Python 3.14, sans `uv`, sans fichier de verrouillage | **non fait** |
| Graine fixée, aucun chemin absolu | `configs/params.yaml` ; aucun chemin absolu dans le code | fait |
| Pas de `.venv` ni de `data/` dans Git | `.gitignore` | fait |
| Un commit par étape, tests verts | Dépôt Git créé ; commits regroupés par lots de phases | partiel |
| Code commenté (le pourquoi), documentation en français, code en anglais | `src/solarvision/` | fait |
| Ne pas rédiger l'interprétation experte à la place de l'étudiant | Gabarit vide dans `docs/llm/` | fait |

## 5. Ce qui n'a pas été fait ou pas vérifié

| Point | Détail |
|---|---|
| Cahier des charges | PDF absent : la liste des exigences n'a pas pu être relue sur l'original |
| Python 3.12 et `uv` | Non installés (connexion lente, délai). Le fonctionnement sous Python 3.12 n'a pas été testé |
| DVC | `dvc.yaml` écrit, jamais exécuté : DVC n'est pas installé |
| Docker (v2) | `infra/Dockerfile` et `infra/docker-compose.yml` écrits, image non construite |
| Intégration continue | `.github/workflows/ci.yml` écrit, jamais exécuté : le dépôt n'est pas publié |
| Evidently | Non installé ; les mêmes statistiques de dérive sont calculées avec scipy |
| Registre MLflow | Le suivi d'expériences MLflow fonctionne ; le registre de modèles est un registre sur fichiers, pas celui de MLflow |
| Hypothèses économiques | Aucune n'est vérifiée auprès des sources indiquées |
| Section LLM de la v2 | Interprétation experte, réponses du LLM et tableau de comparaison non rédigés (travail du groupe) |
| Noms du groupe | Non renseignés dans le rapport (`report.authors` dans `configs/params.yaml`) |
| Clone propre avec téléchargements | Non testé de bout en bout ce jour : le quota d'Open-Meteo était épuisé |
| Réseaux récurrents | Entraînés une fois, sans réajustement tous les 30 jours |
| Modèle hybride, N-BEATS ou TFT, vrai ex ante météo, corrélation dynamique | Non faits en v2 |
| Carte interactive | Carte statique seulement |
| Application | Infobulles natives du navigateur, sans réticule interactif ; pas de thème sombre testé |

## 6. Vérifications exécutées

| Vérification | Commande | Résultat |
|---|---|---|
| Tests | `python -m pytest` | 72 réussis |
| Style | `ruff check src tests scripts` | aucune erreur |
| Dossier R, copié hors du projet | `Rscript run_all.R` | 8 scripts réussis, notebook compilé, 9 tableaux identiques à ceux de l'étude d'origine |
| Diebold-Mariano | Comparaison à `forecast::dm.test` (R 4.6.0) | identique pour 3 horizons et 2 pertes |
| Clone propre | `pipeline --fast`, `report --fast`, `pytest` | toutes les étapes réussies ; 69 tests réussis, 2 ignorés (jeux de la v1 absents du clone) |
| Notebook v2 | `nbconvert --execute` | 15 cellules, 0 erreur |
| Coordonnées des villes | `python scripts/verify_cities.py` | 30 villes à moins de 2 km de la référence |
| Qualité des données | `data/quality/summary.csv` | 30 villes au statut « ok », 11 à 15 jours imputés par ville |
| Écart sur la climatologie de Tunis | `reports/diagnostic_ecart_climatologie_tunis.csv` | expliqué : normale non lissée (1,1324) contre lissée sur 31 jours (1,1002) |
| Pages de l'application | Tests de l'API | 9 pages chargées, mentions ex ante et ex post présentes |
