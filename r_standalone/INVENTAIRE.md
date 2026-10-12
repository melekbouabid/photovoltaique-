# Inventaire du code R

## Code R trouvé dans le projet

Recherche faite sur `*.R`, `*.Rmd`, `*.qmd`, `renv.lock`, `DESCRIPTION`, `*.Rproj` et sur les blocs R
des notebooks Jupyter.

| Fichier d'origine | Nature | Repris |
|---|---|---|
| `mini_projet_R.Rmd` | Notebook R Markdown, 540 lignes, 25 blocs de code | Oui, en entier |
| `mini_projet_R.html` | Version compilée du notebook | Non : sortie, régénérée dans `outputs/` |

Aucun autre fichier R, aucun fichier `renv.lock` ou `DESCRIPTION`, aucun bloc R dans le notebook Jupyter.

## Correspondance

| Blocs d'origine | Fichier copié | Rôle |
|---|---|---|
| Tout le notebook | `notebooks/mini_projet_R.Rmd` | Code et commentaires de lecture |
| `packages`, `donnees` | `R/01_donnees.R` | Packages, lecture, découpage 90/10 |
| `graphique`, `descriptives`, `acf`, `stl`, `aberrants` | `R/02_exploration.R` | Analyse exploratoire |
| `stationnarite` | `R/03_stationnarite.R` | ADF et KPSS |
| `grille`, `auto-arima`, `ajustements`, `diagnostics`, `diag-graph` | `R/04_arima.R` | ARIMA à termes de Fourier |
| `mensuel` | `R/05_sarima_mensuel.R` | SARIMA mensuel |
| `var`, `granger`, `cointegration` | `R/06_var_cointegration.R` | VAR, Granger, Johansen, VECM |
| `garch`, `garch-vol` | `R/07_garch.R` | ARCH et GARCH |
| `normale`, `previsions`, `metriques`, `dm` | `R/08_prevision_evaluation.R` | Prévision et évaluation |

Deux blocs ne sont pas repris dans `R/` : `setup` (options d'affichage de knitr) et `session`
(`sessionInfo()`, écrit par `run_all.R` dans `outputs/session_info.txt`).

## Entrées

| Fichier | Lu par | Origine |
|---|---|---|
| `data/tn_photovoltaique_journalier.csv` | `R/01_donnees.R` | Jeu produit par la collecte Python du projet principal |
| `data/fr_solaire_national_rte_journalier.csv` | `R/06_var_cointegration.R` | Idem |
| `data/es_fotovoltaica_ree_journalier.csv` | `R/06_var_cointegration.R` | Idem |

Le code d'origine lisait ces trois fichiers dans le dossier de données du projet principal, où la collecte
Python les écrit. Pour rendre le dossier autonome, ils ont été **copiés** dans `data/`. Empreintes SHA256 dans
`data/README.md`.

## Sorties

| Script | Fichiers écrits dans `outputs/tables/` |
|---|---|
| `R/03_stationnarite.R` | `R_stationnarite.csv` |
| `R/04_arima.R` | `R_grille_arima.csv`, `R_diagnostics_arima.csv` |
| `R/05_sarima_mensuel.R` | `R_metriques_mensuel.csv` |
| `R/06_var_cointegration.R` | `R_granger.csv`, `R_johansen.csv` |
| `R/07_garch.R` | `R_garch_comparaison.csv` |
| `R/08_prevision_evaluation.R` | `R_metriques.csv`, `R_diebold_mariano.csv` |

## Packages

| Package | Version | Usage |
|---|---|---|
| here | 1.0.2 | Chemins relatifs au dossier (ajouté pour l'autonomie) |
| forecast | 9.0.2 | `Arima`, `auto.arima`, `forecast`, `dm.test`, `Acf`, `Pacf` |
| urca | 1.3-4 | `ur.df`, `ca.jo`, `cajorls` |
| vars | 1.6-1 | `VARselect`, `VAR`, `serial.test`, `Bcoef` |
| tseries | 0.10-63 | `adf.test`, `kpss.test`, `jarque.bera.test` |
| FinTS | 0.4-9 | `ArchTest` |
| rugarch | 1.5-6 | `ugarchspec`, `ugarchfit` |
| lmtest | 0.9-40 | `coeftest` |
| jsonlite | 2.0.0 | Chargé par le code d'origine |

## Modifications par rapport au code d'origine

Le code de calcul est inchangé. Seuls ont changé :

| Modification | Raison |
|---|---|
| Chemins de lecture et d'écriture écrits avec `here::here()` | Aucun chemin ne sort du dossier |
| Sorties dans `outputs/tables/` et `outputs/figures/` | Séparer ce qui est généré de ce qui est versionné |
| `set.seed(42)` devenu `set.seed(SEED)` | Graine définie en tête de `run_all.R` |
| `floor(0.9 * n)` devenu `floor(TRAIN_FRACTION * n)`, `H <- 7` devenu `H <- HORIZON` | Découpage et horizon définis en tête de `run_all.R` |
| Message d'erreur du fichier manquant | Il renvoyait à un script du projet principal |
| En-tête de commentaires dans chaque script | Dire d'où vient le code et pourquoi il est là |
| Texte d'introduction du notebook | Il décrivait les fichiers du projet principal |
