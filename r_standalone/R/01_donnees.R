# 01_donnees.R
# Chargement des packages, lecture des données de Tunis et découpage chronologique 90/10.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : packages, donnees), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : packages ----
# Chargement des packages et graine : rugarch utilise un optimiseur à départs aléatoires, la graine
# garantit des résultats identiques d'une exécution à l'autre.
library(forecast); library(urca); library(vars); library(tseries)
library(FinTS); library(rugarch); library(lmtest); library(jsonlite)
set.seed(SEED)
for (d in c("figures", "tables")) dir.create(here::here("outputs", d), recursive = TRUE, showWarnings = FALSE)

# ---- bloc d'origine : donnees ----
# Lecture du jeu de données « photovoltaïque - Tunisie » (3 villes) et sélection de Tunis. Le fichier est
# une copie placée dans data/ : ce dossier ne dépend d'aucun autre.
f <- here::here("data", "tn_photovoltaique_journalier.csv")
if (!file.exists(f)) stop("Fichier absent : ", f)
tn <- read.csv(f, stringsAsFactors = FALSE)
df <- tn[tn$site == "tunis", ]
df$date <- as.Date(df$date)
df <- df[order(df$date), ]
stopifnot(all(diff(df$date) == 1))                 # pas de jour manquant : la série est régulière
n <- nrow(df); n_train <- floor(TRAIN_FRACTION * n); H <- HORIZON
y_all <- df$pv_kwh_kwc
# Objet série temporelle natif, fréquence annuelle déclarée (365,25 jours par cycle).
y_ts <- ts(y_all, start = c(2005, 1), frequency = 365.25)
y_train <- y_all[1:n_train]
train <- df[1:n_train, ]
cat("Période :", format(df$date[1]), "->", format(df$date[n]), "|", n, "jours | apprentissage jusqu'au",
    format(df$date[n_train]), "(", n_train, "jours ) | test :", n - n_train, "jours\n")
cat("Jours dont le rayonnement PVGIS a été imputé (trous de la base SARAH3) :", sum(df$jour_impute_pvgis), "\n")
