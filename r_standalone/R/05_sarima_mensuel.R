# 05_sarima_mensuel.R
# SARIMA saisonnier (s = 12) sur la série mensuelle et évaluation à 6 mois.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : mensuel), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : mensuel ----
# Série mensuelle (somme des productions journalières) : période 12, SARIMA au sens strict.
mm <- tapply(y_all, format(df$date, "%Y-%m"), sum)
ym <- ts(as.numeric(mm), start = c(2005, 1), frequency = 12)
nm <- length(ym); nm_train <- floor(TRAIN_FRACTION * nm)
ym_train <- window(ym, end = time(ym)[nm_train])
# Canova-Hansen demande le package uroot : on utilise le test de force saisonnière (« seas », défaut de forecast).
cat("D suggéré : OCSB =", nsdiffs(ym_train, test = "ocsb"), "| force saisonnière =", nsdiffs(ym_train, test = "seas"), "\n")
par(mfrow = c(1, 2)); Acf(diff(ym_train, 12), lag.max = 36, main = "ACF - diff. saisonnière (12)")
Pacf(diff(ym_train, 12), lag.max = 36, main = "PACF - diff. saisonnière (12)")
grille_m <- do.call(rbind, lapply(list(c(0, 0, 0), c(1, 0, 0), c(0, 0, 1), c(1, 0, 1)), function(o)
  do.call(rbind, lapply(list(c(0, 1, 1), c(1, 1, 0), c(1, 1, 1), c(2, 1, 0)), function(s) {
    m <- tryCatch(Arima(ym_train, order = o, seasonal = s), error = function(e) NULL)
    if (is.null(m)) return(NULL)
    data.frame(ordre = paste(o, collapse = ","), saisonnier = paste(s, collapse = ","), AIC = AIC(m), BIC = BIC(m))
  }))))
grille_m <- grille_m[order(grille_m$BIC), ]; rownames(grille_m) <- NULL
head(grille_m, 5)
OM <- as.integer(strsplit(grille_m$ordre[1], ",")[[1]]); SM <- as.integer(strsplit(grille_m$saisonnier[1], ",")[[1]])
m_mens <- Arima(ym_train, order = OM, seasonal = SM)
m_mens_auto <- auto.arima(ym_train)
m_mens; m_mens_auto
rm_ <- as.numeric(residuals(m_mens))[-(1:13)]
cat("Diagnostic : LB(12) p =", round(Box.test(rm_, 12, "Ljung-Box", fitdf = length(coef(m_mens)))$p.value, 4),
    "| JB p =", round(jarque.bera.test(rm_)$p.value, 4), "| ARCH-LM(4) p =", round(ArchTest(rm_, lags = 4)$p.value, 4), "\n")
# Évaluation à 6 mois depuis chaque origine du test.
HM <- 6; orig_m <- nm_train:(nm - HM)
Ym <- t(sapply(orig_m, function(t) ym[(t + 1):(t + HM)]))
clim_m <- tapply(as.numeric(ym_train), cycle(ym_train), mean)
pm_ <- list("Naïf saisonnier (même mois N-1)" = t(sapply(orig_m, function(t) ym[(t + 1 - 12):(t + HM - 12)])),
            "Moyenne mensuelle" = t(sapply(orig_m, function(t) clim_m[cycle(ym)[(t + 1):(t + HM)]])),
            "SARIMA manuel" = t(sapply(orig_m, function(t) forecast(Arima(ym[1:t], order = OM, seasonal = list(order = SM, period = 12),
                                                                       fixed = coef(m_mens), transform.pars = FALSE), h = HM)$mean)),
            "SARIMA auto" = t(sapply(orig_m, function(t) forecast(Arima(ts(ym[1:t], frequency = 12, start = c(2005, 1)), model = m_mens_auto), h = HM)$mean)))
tab_mens <- t(sapply(pm_, function(P) c(RMSE = sqrt(mean((Ym - P)^2)), MAE = mean(abs(Ym - P)), MAPE = 100 * mean(abs(Ym - P) / Ym))))
write.csv(tab_mens, here::here("outputs", "tables", "R_metriques_mensuel.csv"))
round(tab_mens, 2)
