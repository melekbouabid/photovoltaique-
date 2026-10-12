# 07_garch.R
# Effets ARCH et modèles GARCH sur les erreurs de l'ARIMA-Fourier.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : garch, garch-vol), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : garch ----
# Variance conditionnelle des erreurs à un jour de l'ARIMA-Fourier manuel (kWh/kWc).
e <- r_man
cat("ARCH-LM(7) : p =", signif(ArchTest(e, lags = 7)$p.value, 3), "| ACF des carrés (1 à 7) :",
    round(acf(e^2, plot = FALSE, lag.max = 7)$acf[-1], 3), "\n")
spec <- function(modele, ordre, loi) ugarchspec(variance.model = list(model = modele, garchOrder = ordre),
                                                mean.model = list(armaOrder = c(0, 0), include.mean = FALSE),
                                                distribution.model = loi)
candidats <- list("GARCH(1,1) normale" = spec("sGARCH", c(1, 1), "norm"),
                  "GARCH(1,1) Student" = spec("sGARCH", c(1, 1), "std"),
                  "GARCH(1,1) Student asym." = spec("sGARCH", c(1, 1), "sstd"),
                  "GARCH(2,1) Student asym." = spec("sGARCH", c(2, 1), "sstd"),
                  "GJR-GARCH(1,1) Student asym." = spec("gjrGARCH", c(1, 1), "sstd"),
                  "EGARCH(1,1) Student asym." = spec("eGARCH", c(1, 1), "sstd"))
# Plusieurs solveurs, meilleure vraisemblance retenue : un optimum local fausserait la comparaison.
ajuster_garch <- function(sp) {
  essais <- lapply(c("hybrid", "solnp", "nlminb"), function(sv) tryCatch(ugarchfit(sp, e, solver = sv), error = function(err) NULL))
  essais <- Filter(function(g) !is.null(g) && convergence(g) == 0, essais)
  if (length(essais) == 0) return(NULL)
  essais[[which.max(sapply(essais, likelihood))]]
}
ajust <- Filter(Negate(is.null), lapply(candidats, ajuster_garch))
tab_g <- t(sapply(ajust, function(g) { zz <- as.numeric(residuals(g, standardize = TRUE))
  c(logLik = likelihood(g), AIC = infocriteria(g)[1] * length(e), BIC = infocriteria(g)[2] * length(e),
    LB10_z2_p = Box.test(zz^2, 10, "Ljung-Box")$p.value, ARCH_LM7_z_p = ArchTest(zz, lags = 7)$p.value) }))
write.csv(tab_g, here::here("outputs", "tables", "R_garch_comparaison.csv"))
round(tab_g, 4)
g11 <- ajust[["GARCH(1,1) Student asym."]]
round(coef(g11), 4)
cat("Persistance alpha + beta :", round(sum(coef(g11)[c("alpha1", "beta1")]), 3), "\n")

# ---- bloc d'origine : garch-vol ----
# Volatilité conditionnelle dans le temps puis sa moyenne par mois : si elle suit le calendrier, le GARCH ne fait
# que reproduire une saisonnalité de la variance (hiver nuageux, été stable), pas des chocs persistants.
vol <- as.numeric(sigma(g11))
plot(train$date[-(1:7)], vol, type = "l", col = "#1f3a5f", xlab = "", ylab = "écart-type conditionnel",
     main = "Volatilité conditionnelle GARCH(1,1) des erreurs de l'ARIMA-Fourier")
round(tapply(vol, format(train$date[-(1:7)], "%m"), mean), 3)
