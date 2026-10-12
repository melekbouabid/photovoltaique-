# Socle classique en R — dossier autonome

Ce dossier contient tout le code R du projet et les données qu'il lit. Il ne dépend d'aucun autre
dossier : on peut le copier ailleurs et l'exécuter tel quel.

## Objectif

Étudier en R la production journalière d'une installation photovoltaïque de 1 kWc à Tunis (2005-2023) :
exploration, stationnarité, ARIMA et SARIMA, VAR et cointégration, GARCH, puis prévision à 7 jours et
évaluation.

## Prérequis

- R 4.3 ou plus récent (résultats produits avec R 4.6.0).
- Les packages listés dans `DESCRIPTION` :

```r
install.packages(c("here", "forecast", "urca", "vars", "tseries", "FinTS", "rugarch", "lmtest",
                   "jsonlite", "rmarkdown"))
```

- pandoc, seulement pour compiler le notebook en HTML (fourni avec RStudio).

## Exécution

```
Rscript run_all.R
```

Le script s'arrête à la première erreur et écrit tout ce qu'il affiche dans `outputs/run_all.log`.
Les paramètres (graine, découpage 90/10, horizon) sont en tête de `run_all.R`.

## Ordre d'exécution

| Ordre | Script | Contenu |
|---|---|---|
| 1 | `R/01_donnees.R` | Packages, lecture des données, découpage chronologique |
| 2 | `R/02_exploration.R` | Graphiques, statistiques descriptives, ACF et PACF, STL, valeurs aberrantes |
| 3 | `R/03_stationnarite.R` | Tests ADF et KPSS |
| 4 | `R/04_arima.R` | ARIMA à termes de Fourier, `auto.arima`, diagnostic des résidus |
| 5 | `R/05_sarima_mensuel.R` | SARIMA saisonnier sur la série mensuelle |
| 6 | `R/06_var_cointegration.R` | VAR, causalité de Granger, Johansen, VECM |
| 7 | `R/07_garch.R` | Effets ARCH et modèles GARCH |
| 8 | `R/08_prevision_evaluation.R` | Prévisions, métriques, Diebold-Mariano |

Les scripts partagent le même environnement : chacun réutilise les objets créés par les précédents.
Ils ne se lancent donc pas isolément.

## Durée

Environ 5 minutes pour les scripts, autant pour la compilation du notebook.

## Sorties

Tout est écrit dans `outputs/`, dossier généré et non versionné.

| Fichier | Contenu |
|---|---|
| `outputs/tables/R_*.csv` | Stationnarité, grille ARIMA, diagnostics, Granger, Johansen, GARCH, métriques, Diebold-Mariano |
| `outputs/figures/figures_R.pdf` | Toutes les figures |
| `outputs/mini_projet_R.html` | Notebook compilé |
| `outputs/run_all.log` | Journal de l'exécution |
| `outputs/session_info.txt` | Versions exactes des packages |

## Contenu du dossier

| Élément | Rôle |
|---|---|
| `run_all.R` | Point d'entrée |
| `R/` | Les huit scripts |
| `notebooks/mini_projet_R.Rmd` | Le même code, avec les commentaires de lecture |
| `data/` | Copies des trois jeux de données (origine et empreintes dans `data/README.md`) |
| `DESCRIPTION` | Packages et versions |
| `INVENTAIRE.md` | Origine de chaque fichier |
| `.here` | Marque la racine du dossier pour `here::here()` |
