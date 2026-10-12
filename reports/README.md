# reports/

Tables, figures et rapports **générés par le code**. Rien n'est saisi à la main ici, à une exception près :
`conformite_v2.md`, qui est l'audit de conformité rédigé à la fin du travail.

| Fichier | Contenu | Produit par |
|---|---|---|
| `cities_verification.csv` | Coordonnées et altitudes comparées à GeoNames | `python scripts/verify_cities.py` |
| `exploration_stats.csv` | Moments, saisonnalité, ADF et KPSS par ville | `report`, `llm-pack` |
| `forecasts/`, `forecasts_deep/` | Prévisions et observations, origine par origine | `train`, `deep` |
| `metrics_tidy.csv`, `metrics_wide.csv` | Toutes les métriques, par ville, technologie, modèle, horizon, scénario | `evaluate` |
| `dm_tests.csv` | Tests de Diebold-Mariano contre la climatologie, corrigés par Holm | `evaluate` |
| `synthese_ville.csv` | Meilleur modèle ex ante par ville, gain, erreur par horizon et par saison | `evaluate` |
| `coverage.csv` | Couverture des intervalles de prévision | `evaluate` |
| `sensitivity_imputed.csv` | Résultats avec et sans les jours imputés | `train --sensitivity` |
| `diagnostic_ecart_climatologie_tunis.csv` | Effet de la définition de la normale sur l'erreur de la climatologie | `python scripts/diagnose_climatology_gap.py` |
| `deep/` | Validation glissante et courbes de perte des réseaux | `deep` |
| `tech_indicators.csv`, `tech_scores.csv`, `tech_recommendation.csv` | Indicateurs, scores et recommandation par ville | `recommend` |
| `tech_recommender_*.csv`, `tech_recommender_tree.txt`, `city_features.csv` | Arbre de décision validé ville par ville | `recommend` |
| `tech_orientations.csv` | Plein sud, est-ouest et orientation optimisée | `recommend --orientations` |
| `economics_by_city.csv`, `economics_ranking.csv`, `economics_tornado.csv` | Résultats économiques avec intervalles, classement, sensibilité | `economics` |
| `forecast_value.csv` | Valeur d'une meilleure prévision | `economics` |
| `arima_fourier_params.json` | Paramètres du modèle AR(1) de chaque ville | `register` |
| `monitoring/` | Dérive, erreur glissante, résumé des alertes, journal des requêtes | `monitor`, `serve` |
| `figures/` | Figures du rapport | `report` |
| `rapport/` | Rapport Word, PDF et source Markdown | `report` |
| `conformite_v2.md` | Audit de conformité | Rédigé à la main |
| `fast/` | Les mêmes sorties pour le parcours rapide (3 villes) | Commandes avec `--fast` |

Toutes les commandes se lancent par `python -m solarvision.cli <commande>`.
