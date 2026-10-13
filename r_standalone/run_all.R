# run_all.R - exécute tout le code R de ce dossier, dans l'ordre, et s'arrête à la première erreur.
# Usage : Rscript run_all.R
# Ce dossier est autonome : il ne lit et n'écrit rien en dehors de lui-même.

# ------------------------------------------------------------------------------ paramètres
SEED <- 42                           # graine : rugarch utilise un optimiseur à départs aléatoires
TRAIN_FRACTION <- 0.9                # découpage chronologique 90/10 (apprentissage = 90 % des jours les plus anciens)
HORIZON <- 7                         # horizon de prévision, en jours
EXPECTED_SPLIT_DATE <- "2022-02-05"  # dernier jour d'apprentissage attendu pour Tunis : garde-fou sur le découpage
RENDER_NOTEBOOK <- TRUE              # compile aussi notebooks/mini_projet_R.Rmd en HTML si pandoc est disponible
PACKAGES <- c("here", "forecast", "urca", "vars", "tseries", "FinTS", "rugarch", "lmtest", "jsonlite")
SCRIPTS <- c("01_donnees.R", "02_exploration.R", "03_stationnarite.R", "04_arima.R", "05_sarima_mensuel.R",
             "06_var_cointegration.R", "07_garch.R", "08_prevision_evaluation.R")
# ------------------------------------------------------------------------------------------

# Le répertoire de travail devient le dossier du script : la commande marche depuis n'importe où.
args <- commandArgs(trailingOnly = FALSE)
script <- sub("^--file=", "", args[grep("^--file=", args)])
if (length(script) == 1) setwd(dirname(normalizePath(script)))

# Contrôle des packages avant tout calcul : un message clair vaut mieux qu'une erreur au milieu.
missing <- PACKAGES[!vapply(PACKAGES, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  stop("Packages manquants : ", paste(missing, collapse = ", "),
       "\nInstaller avec : install.packages(c(", paste0('"', missing, '"', collapse = ", "), "))")
}
here::i_am("run_all.R")              # ancre here::here() sur ce dossier (fichier .here)

for (d in c("figures", "tables")) dir.create(here::here("outputs", d), recursive = TRUE, showWarnings = FALSE)
log_file <- file(here::here("outputs", "run_all.log"), open = "wt", encoding = "UTF-8")
sink(log_file, split = TRUE)         # tout ce qui s'affiche est aussi écrit dans le journal
cat("Début :", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "| R", as.character(getRversion()), "\n")
cat("Paramètres : SEED =", SEED, "| TRAIN_FRACTION =", TRAIN_FRACTION, "| HORIZON =", HORIZON, "\n\n")

# Les figures vont dans un seul PDF : Rscript n'a pas de fenêtre graphique.
pdf(here::here("outputs", "figures", "figures_R.pdf"), width = 10, height = 6)
summary_rows <- list()
t_start <- Sys.time()
for (s in SCRIPTS) {
  cat("\n==================== ", s, " ====================\n", sep = "")
  t0 <- Sys.time()
  ok <- tryCatch({
    # Environnement global partagé : chaque script réutilise les objets des précédents, comme dans le notebook.
    source(here::here("R", s), local = FALSE, encoding = "UTF-8", print.eval = TRUE)
    TRUE
  }, error = function(e) {
    cat("\nERREUR dans ", s, " : ", conditionMessage(e), "\n", sep = "")
    FALSE
  })
  secs <- round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 1)
  summary_rows[[s]] <- data.frame(script = s, statut = if (ok) "réussi" else "échec", duree_s = secs)
  if (!ok) break
  if (s == "01_donnees.R") {
    # Garde-fou : le découpage doit tomber sur la date attendue, sinon les résultats ne sont plus comparables.
    stopifnot(format(df$date[n_train]) == EXPECTED_SPLIT_DATE)
  }
}
dev.off()

summary_table <- do.call(rbind, summary_rows)
rownames(summary_table) <- NULL
cat("\n==================== bilan ====================\n")
print(summary_table)
failed <- any(summary_table$statut != "réussi") || nrow(summary_table) < length(SCRIPTS)

if (!failed && RENDER_NOTEBOOK) {
  if (requireNamespace("rmarkdown", quietly = TRUE) && rmarkdown::pandoc_available()) {
    cat("\nCompilation du notebook R...\n")
    t0 <- Sys.time()
    rmarkdown::render(here::here("notebooks", "mini_projet_R.Rmd"), output_dir = here::here("outputs"),
                      knit_root_dir = here::here(), quiet = TRUE, envir = new.env())
    cat("Notebook compilé en", round(as.numeric(difftime(Sys.time(), t0, units = "secs"))), "s : outputs/mini_projet_R.html\n")
  } else {
    cat("\nNotebook non compilé : rmarkdown ou pandoc absent (les scripts de R/ couvrent tout le code).\n")
  }
}

writeLines(capture.output(sessionInfo()), here::here("outputs", "session_info.txt"))
cat("\nFichiers produits dans outputs/ :\n")
print(list.files(here::here("outputs"), recursive = TRUE))
cat("\nDurée totale :", round(as.numeric(difftime(Sys.time(), t_start, units = "mins")), 1), "min\n")
sink()
close(log_file)
if (failed) quit(status = 1)
