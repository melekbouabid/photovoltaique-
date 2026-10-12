# 08_prevision_evaluation.R
# Prévisions à 7 jours sur le test, métriques, intervalles et tests de Diebold-Mariano.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : normale, previsions, metriques, dm), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : normale ----
# Normale saisonnière calculée exactement comme en Python : moyenne par jour de l'année sur
# l'apprentissage, lissée par une moyenne mobile circulaire de 31 jours.
jour <- pmin(as.integer(format(df$date, "%j")), 365)
lisser <- function(a) as.numeric(stats::filter(c(a, a, a), rep(1 / 31, 31), sides = 2))[366:730]
CLIM_M <- lisser(as.numeric(tapply(y_train, jour[1:n_train], mean)))[jour]

# ---- bloc d'origine : previsions ----
# Origines glissantes sur tout le test ; paramètres figés à leur valeur estimée sur l'apprentissage.
# Le filtre est appliqué aux 500 derniers jours avant chaque origine : avec un AR(1) de coefficient
# voisin de 0,26, l'état filtré ne dépend pas des observations plus anciennes.
origines <- n_train:(n - H)
Y <- t(sapply(origines, function(t) y_all[(t + 1):(t + H)]))
prev_arima <- function(fit, X) {
  P <- B <- U <- matrix(NA, length(origines), H)
  for (i in seq_along(origines)) {
    t <- origines[i]; w <- (t - 499):t
    fc <- forecast(Arima(y_all[w], model = fit, xreg = X[w, , drop = FALSE]), h = H, level = 95,
                   xreg = X[(t + 1):(t + H), , drop = FALSE])
    P[i, ] <- fc$mean; B[i, ] <- fc$lower; U[i, ] <- fc$upper
  }
  list(moy = pmax(P, 0), bas = B, haut = U)
}
# VAR : prévision récursive depuis chaque origine avec les coefficients estimés sur l'apprentissage.
Bv <- Bcoef(var_fit)
prev_var <- t(sapply(origines, function(t) {
  hist <- endog[(t - P_VAR + 1):t, , drop = FALSE]; out <- numeric(H)
  for (h in 1:H) {
    z <- c(as.vector(t(hist[nrow(hist):(nrow(hist) - P_VAR + 1), , drop = FALSE])), 1, F3[t + h, ])
    yh <- as.numeric(Bv %*% z); out[h] <- yh[1]; hist <- rbind(hist, yh)
  }
  out
}))
prev <- list("Persistance (J)" = list(moy = t(sapply(origines, function(t) rep(y_all[t], H)))),
             "Climatologie" = list(moy = t(sapply(origines, function(t) CLIM_M[(t + 1):(t + H)]))),
             "ARIMA-Fourier manuel" = prev_arima(m_man, FK), "ARIMA-Fourier auto" = prev_arima(m_auto, FK),
             "VAR" = list(moy = prev_var), "SARIMAX météo (ex post)" = prev_arima(m_meteo, X_meteo))

# ---- bloc d'origine : metriques ----
# Les quatre métriques de l'énoncé, calculées sur les mêmes origines et horizons pour tous les modèles (tableau
# unique), puis le RMSE par horizon : c'est lui qui montre où chaque modèle gagne ou perd.
metriques <- function(P) { e <- Y - P
  c(MSE = mean(e^2), RMSE = sqrt(mean(e^2)), MAE = mean(abs(e)), MAPE = 100 * mean(abs(e) / Y)) }
tab_m <- t(sapply(prev, function(p) metriques(p$moy)))
rmse_h <- t(sapply(prev, function(p) sqrt(colMeans((Y - p$moy)^2)))); colnames(rmse_h) <- paste0("RMSE_h", 1:H)
couv <- sapply(prev, function(p) if (is.null(p$bas)) NA else 100 * mean(Y >= p$bas & Y <= p$haut))
tab_m <- cbind(tab_m, couverture_IC95 = couv)
write.csv(cbind(tab_m, rmse_h), here::here("outputs", "tables", "R_metriques.csv"))
round(tab_m, 4)
round(rmse_h, 3)

# ---- bloc d'origine : dm ----
# Diebold-Mariano (HLN) contre la climatologie et contre la persistance, horizons 1 et 7,
# pertes quadratique et absolue. Statistique positive = le modèle fait mieux que la référence.
dm <- do.call(rbind, lapply(c("Persistance (J)", "Climatologie"), function(ref)
  do.call(rbind, lapply(setdiff(names(prev), ref), function(nm) do.call(rbind, lapply(c(1, 7), function(h) {
    e_ref <- Y[, h] - prev[[ref]]$moy[, h]; e_mod <- Y[, h] - prev[[nm]]$moy[, h]
    d <- dm.test(e_ref, e_mod, h = h, power = 2); da <- dm.test(e_ref, e_mod, h = h, power = 1)
    data.frame(reference = ref, modele = nm, horizon = h, DM = as.numeric(d$statistic), p = d$p.value,
               DM_abs = as.numeric(da$statistic), p_abs = da$p.value)
  }))))))
write.csv(dm, here::here("outputs", "tables", "R_diebold_mariano.csv"), row.names = FALSE)
dm[, 3:7] <- round(dm[, 3:7], 4)
dm
