# 02_exploration.R
# Analyse exploratoire : graphiques, statistiques descriptives, ACF/PACF, décomposition STL, valeurs aberrantes.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : graphique, descriptives, acf, stl, aberrants), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : graphique ----
# Production, nébulosité et température : trois échelles différentes, donc trois panneaux.
par(mfrow = c(3, 1), mar = c(2, 4.5, 1.5, 1))
plot(df$date, y_all, type = "l", lwd = 0.4, col = "#1f3a5f", xlab = "", ylab = "kWh/kWc",
     main = "Production journalière d'1 kWc à Tunis")
lines(df$date, stats::filter(y_all, rep(1 / 365, 365), sides = 2), col = "black", lwd = 1.5)
abline(v = df$date[n_train + 1], lty = 2)
plot(df$date, df$nebulosite_pct, type = "l", lwd = 0.4, col = "#6b7b8c", xlab = "", ylab = "nébulosité (%)")
plot(df$date, df$t2m_moy_c, type = "l", lwd = 0.4, col = "#d03b3b", xlab = "", ylab = "température (°C)")

# ---- bloc d'origine : descriptives ----
# Statistiques descriptives sur l'apprentissage (moments d'ordre 3 et 4 compris).
desc <- function(v) c(moyenne = mean(v), ecart_type = sd(v), min = min(v), max = max(v),
                      skewness = mean((v - mean(v))^3) / sd(v)^3, kurtosis_exces = mean((v - mean(v))^4) / sd(v)^4 - 3)
round(t(sapply(train[, c("pv_kwh_kwc", "nebulosite_pct", "t2m_moy_c", "precipitation_mm", "aerosols_aod")], desc)), 3)
mois <- as.integer(format(train$date, "%m"))
round(rbind(moyenne = tapply(y_train, mois, mean), ecart_type = tapply(y_train, mois, sd)), 2)

# ---- bloc d'origine : acf ----
# Termes de Fourier construits comme en Python (t = 0, 1, ... depuis le 1er janvier 2005) :
# ils représentent le cycle annuel déterministe.
fourier_k <- function(K, t = 0:(n - 1)) {
  M <- do.call(cbind, lapply(1:K, function(k) cbind(sin(2 * pi * k * t / 365.25), cos(2 * pi * k * t / 365.25))))
  colnames(M) <- paste0(rep(c("S", "C"), K), rep(1:K, each = 2)); M
}
F4 <- fourier_k(4)
anomalie <- y_all - cbind(1, F4) %*% coef(lm(y_train ~ F4[1:n_train, ]))
par(mfrow = c(3, 2), mar = c(4, 4, 2.5, 1))
Acf(y_train, lag.max = 40, main = "ACF - série brute"); Pacf(y_train, lag.max = 40, main = "PACF - série brute")
Acf(diff(y_train), lag.max = 40, main = "ACF - différence d'ordre 1"); Pacf(diff(y_train), lag.max = 40, main = "PACF - différence d'ordre 1")
Acf(anomalie[1:n_train], lag.max = 40, main = "ACF - désaisonnalisée (Fourier)"); Pacf(anomalie[1:n_train], lag.max = 40, main = "PACF - désaisonnalisée (Fourier)")
a_acf <- acf(anomalie[1:n_train], plot = FALSE, lag.max = 7)$acf[-1]
a_pacf <- pacf(anomalie[1:n_train], plot = FALSE, lag.max = 7)$acf
round(rbind(ACF = a_acf, PACF = a_pacf), 3)

# ---- bloc d'origine : stl ----
# Décomposition STL robuste (période 365 jours) sur l'apprentissage.
dec <- stl(ts(y_train, frequency = 365), s.window = 7, robust = TRUE)
plot(dec, main = "Décomposition STL de la production de Tunis")
comp <- dec$time.series
round(c(tendance = var(comp[, "trend"]), saison = var(comp[, "seasonal"]), residu = var(comp[, "remainder"])) / var(y_train), 3)

# ---- bloc d'origine : aberrants ----
# Boxplot glissant sur le résidu STL (quartiles sur 61 jours centrés) : la dispersion change avec la
# saison, une règle de l'IQR globale signalerait surtout les jours d'hiver.
r_stl <- as.numeric(comp[, "remainder"])
q_gl <- t(vapply(seq_along(r_stl), function(i) {
  w <- r_stl[max(1, i - 30):min(length(r_stl), i + 30)]; quantile(w, c(0.25, 0.75))
}, numeric(2)))
iqr <- q_gl[, 2] - q_gl[, 1]
ab <- r_stl < q_gl[, 1] - 1.5 * iqr | r_stl > q_gl[, 2] + 1.5 * iqr
bas <- ab & r_stl < 0
expl <- bas & (train$precipitation_mm >= 5 | train$nebulosite_pct >= 80 | train$aerosols_aod >= 0.8)
cat("Jours signalés :", sum(ab), "(", round(100 * mean(ab), 1), "% ) dont", sum(bas), "bas ;",
    sum(expl), "jours bas expliqués par la pluie, un ciel couvert ou des poussières\n")
