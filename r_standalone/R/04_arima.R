# 04_arima.R
# ARIMA à termes de Fourier : grille manuelle, auto.arima, variante avec météo, diagnostic des résidus.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : grille, auto-arima, ajustements, diagnostics, diag-graph), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : grille ----
# Grille guidée par l'ACF/PACF : p et q faibles, d = 0, K harmoniques de 2 à 4 ; choix par BIC.
ordres <- list(c(1, 0, 0), c(2, 0, 0), c(3, 0, 0), c(1, 0, 1), c(2, 0, 1), c(1, 0, 2), c(2, 0, 2))
res_g <- do.call(rbind, lapply(2:4, function(K) do.call(rbind, lapply(ordres, function(o) {
  m <- tryCatch(Arima(y_train, order = o, xreg = fourier_k(K)[1:n_train, ], include.constant = TRUE),
                error = function(e) NULL)     # un candidat qui ne converge pas est ignoré
  if (is.null(m)) return(NULL)
  data.frame(ordre = paste(o, collapse = ","), K = K, AIC = AIC(m), BIC = BIC(m))
}))))
res_g <- res_g[order(res_g$BIC), ]; rownames(res_g) <- NULL
write.csv(res_g, here::here("outputs", "tables", "R_grille_arima.csv"), row.names = FALSE)
head(res_g, 8)
ORDRE <- as.integer(strsplit(res_g$ordre[1], ",")[[1]]); K_F <- res_g$K[1]
FK <- fourier_k(K_F)

# ---- bloc d'origine : auto-arima ----
# Confirmation par recherche automatique : auto.arima choisit d et les ordres, mêmes termes de Fourier.
m_auto <- auto.arima(y_train, xreg = FK[1:n_train, ], seasonal = FALSE)
m_auto

# ---- bloc d'origine : ajustements ----
# Trois modèles : manuel, automatique, et manuel enrichi de la météo du jour (« ex post »).
meteo <- cbind(nebulosite = df$nebulosite_pct, neb_x_potentiel = df$nebulosite_pct / 100 * df$irr_extraterrestre_kwh_m2,
               precipitation = df$precipitation_mm, humidite = df$humidite_pct,
               amplitude = df$amplitude_thermique_c, aod = df$aerosols_aod)
X_meteo <- cbind(FK, meteo)
m_man <- Arima(y_train, order = ORDRE, xreg = FK[1:n_train, ], include.constant = TRUE)
m_meteo <- Arima(y_train, order = ORDRE, xreg = X_meteo[1:n_train, ], include.constant = TRUE)
modeles <- list("ARIMA-Fourier manuel" = m_man, "ARIMA-Fourier auto" = m_auto, "SARIMAX météo" = m_meteo)
data.frame(AIC = sapply(modeles, AIC), BIC = sapply(modeles, BIC), sigma = sqrt(sapply(modeles, function(m) m$sigma2)))
coeftest(m_meteo)

# ---- bloc d'origine : diagnostics ----
# Diagnostic des résidus : bruit blanc (Ljung-Box), normalité (Jarque-Bera), variance constante (ARCH-LM).
diagnostic <- function(m) {
  r <- as.numeric(residuals(m))[-(1:7)]
  k <- sum(grepl("^(ar|ma)", names(m$coef)))
  c(LB10_p = Box.test(r, lag = 10, type = "Ljung-Box", fitdf = k)$p.value,
    LB30_p = Box.test(r, lag = 30, type = "Ljung-Box", fitdf = k)$p.value,
    JB_p = jarque.bera.test(r)$p.value, skewness = mean((r - mean(r))^3) / sd(r)^3,
    kurtosis = mean((r - mean(r))^4) / sd(r)^4, ARCH_LM7_p = ArchTest(r, lags = 7)$p.value)
}
tab_diag <- t(sapply(modeles, diagnostic))
write.csv(tab_diag, here::here("outputs", "tables", "R_diagnostics_arima.csv"))
round(tab_diag, 4)

# ---- bloc d'origine : diag-graph ----
# Les quatre vues qui accompagnent les tests : résidus dans le temps (variance saisonnière), ACF (indépendance),
# histogramme (normalité) et ACF des carrés (effets ARCH). Les 7 premiers résidus, phase de mise en route, sont écartés.
r_man <- as.numeric(residuals(m_man))[-(1:7)]
par(mfrow = c(2, 2), mar = c(4, 4, 2.5, 1))
plot(train$date[-(1:7)], r_man, type = "l", lwd = 0.4, xlab = "", ylab = "", main = "Résidus de l'ARIMA-Fourier")
Acf(r_man, lag.max = 40, main = "ACF des résidus")
hist(r_man, breaks = 80, freq = FALSE, col = "#1f3a5f", border = NA, main = "Histogramme et loi normale", xlab = "")
curve(dnorm(x, mean(r_man), sd(r_man)), add = TRUE, col = "#e0a030", lwd = 2)
Acf(r_man^2, lag.max = 40, main = "ACF des résidus au carré (effets ARCH)")
