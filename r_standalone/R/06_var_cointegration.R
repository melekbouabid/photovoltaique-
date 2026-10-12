# 06_var_cointegration.R
# VAR, causalité de Granger, test de Johansen et VECM (Tunis, puis France-Espagne).
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : var, granger, cointegration), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : var ----
# VAR en niveaux sur (production, nébulosité, température), cycle annuel en variables exogènes.
F3 <- fourier_k(3)
endog <- cbind(pv = df$pv_kwh_kwc, neb = df$nebulosite_pct, temp = df$t2m_moy_c)
sel <- VARselect(endog[1:n_train, ], lag.max = 14, type = "const", exogen = F3[1:n_train, ])
sel$selection
P_VAR <- as.integer(sel$selection["SC(n)"])
var_fit <- VAR(endog[1:n_train, ], p = P_VAR, type = "const", exogen = F3[1:n_train, ])
pt <- serial.test(var_fit, lags.pt = 20, type = "PT.asymptotic")
rv <- residuals(var_fit)
cat("VAR(", P_VAR, ") - Portmanteau(20) : p =", signif(pt$serial$p.value, 3), "| module max des racines :",
    round(max(roots(var_fit)), 3), "\n")
cat("Ljung-Box(10) par équation :", round(apply(rv, 2, function(v) Box.test(v, 10, "Ljung-Box")$p.value), 4), "\n")
cat("ARCH-LM(7) par équation :", signif(apply(rv, 2, function(v) ArchTest(v, lags = 7)$p.value), 3), "\n")

# ---- bloc d'origine : granger ----
# Causalité de Granger deux à deux : test de Wald (forme F) de la nullité des retards de la variable
# « cause » dans l'équation de la variable « effet », à partir de la matrice de covariance des coefficients.
granger <- do.call(rbind, lapply(colnames(endog), function(cause) do.call(rbind, lapply(setdiff(colnames(endog), cause), function(effet) {
  eq <- var_fit$varresult[[effet]]
  noms <- grep(paste0("^", cause, "\\.l"), names(coef(eq)), value = TRUE)
  b <- coef(eq)[noms]; V <- vcov(eq)[noms, noms]
  Fst <- as.numeric(t(b) %*% solve(V) %*% b) / length(noms)
  data.frame(cause = cause, effet = effet, F = Fst, p = pf(Fst, length(noms), df.residual(eq), lower.tail = FALSE))
}))))
write.csv(granger, here::here("outputs", "tables", "R_granger.csv"), row.names = FALSE)
granger

# ---- bloc d'origine : cointegration ----
# Cointégration sur le VAR de Tunis : séries stationnaires, le test de Johansen doit trouver le rang plein.
jo <- ca.jo(endog[1:n_train, ], type = "trace", ecdet = "const", K = max(P_VAR, 2), spec = "transitory")
tab_jo <- data.frame(H0 = rev(paste("r <=", 0:2)), trace = round(jo@teststat, 2), crit_5pct = jo@cval[, "5pct"])
tab_jo

# Cas réellement non stationnaire : production solaire nationale mesurée, France (RTE) et Espagne (REE),
# mensuelle, en log, avec indicatrices saisonnières et tendance dans la relation de long terme.
rte <- read.csv(here::here("data", "fr_solaire_national_rte_journalier.csv")); rte$date <- as.Date(rte$date)
ree <- read.csv(here::here("data", "es_fotovoltaica_ree_journalier.csv")); ree$date <- as.Date(ree$date)
mensuel <- function(d, col) { m <- tapply(d[[col]], format(d$date, "%Y-%m"), function(v) if (length(v) >= 25) sum(v) else NA); m }
nat <- merge(data.frame(mois = names(mensuel(rte, "production_gwh")), fr = as.numeric(mensuel(rte, "production_gwh"))),
             data.frame(mois = names(mensuel(ree, "produccion_gwh")), es = as.numeric(mensuel(ree, "produccion_gwh"))))
nat <- na.omit(nat[nat$mois <= "2026-08", ])
lnat <- log(as.matrix(nat[, c("fr", "es")]))
cat("Période :", nat$mois[1], "->", nat$mois[nrow(nat)], "(", nrow(nat), "mois )\n")
# Comme en Python, les tests portent sur les séries désaisonnalisées (régression sur les mois) : sur la série
# brute, le cycle annuel fait passer pour un retour à la moyenne ce qui n'est qu'une saisonnalité.
mois_f <- factor(substr(nat$mois, 6, 7))
ldes <- apply(lnat, 2, function(v) residuals(lm(v ~ mois_f)) + mean(v))
adf_nat <- t(sapply(1:2, function(j) {
  t1 <- ur.df(ldes[, j], type = "trend", lags = 6, selectlags = "AIC")
  t2 <- ur.df(diff(ldes[, j]), type = "drift", lags = 6, selectlags = "AIC")
  c(tau_niveau = t1@teststat[1], seuil_5pct = t1@cval[1, 2], tau_difference = t2@teststat[1], seuil_5pct_diff = t2@cval[1, 2])
}))
rownames(adf_nat) <- c("log France (désaisonnalisé)", "log Espagne (désaisonnalisé)")
round(adf_nat, 2)
jo_n <- ca.jo(lnat, type = "trace", ecdet = "trend", K = 4, season = 12, spec = "transitory")
tab_jo_n <- data.frame(H0 = rev(c("r = 0", "r <= 1")), trace = round(jo_n@teststat, 2), crit_5pct = jo_n@cval[, "5pct"])
write.csv(rbind(cbind(systeme = "Tunis", tab_jo), cbind(systeme = "France-Espagne", tab_jo_n)),
          here::here("outputs", "tables", "R_johansen.csv"), row.names = FALSE)
tab_jo_n
# Rang par la procédure séquentielle : premier r dont l'hypothèse « rang <= r » n'est pas rejetée.
stat_croiss <- rev(jo_n@teststat); crit_croiss <- rev(jo_n@cval[, "5pct"])
RANG_N <- which(stat_croiss <= crit_croiss)[1] - 1; if (is.na(RANG_N)) RANG_N <- 2
cat("Rang de cointégration France-Espagne :", RANG_N, "\n")
vecm <- cajorls(jo_n, r = 1)
cat("VECM de rang 1 (vérification) - beta :", round(vecm$beta[, 1], 4), "\n")
print(round(coef(summary(vecm$rlm))[[1]]["ect1", ], 4)); print(round(coef(summary(vecm$rlm))[[2]]["ect1", ], 4))
