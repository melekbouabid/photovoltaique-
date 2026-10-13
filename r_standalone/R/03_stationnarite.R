# 03_stationnarite.R
# Tests de stationnarité ADF et KPSS, choix de l'ordre de différenciation.
# Pourquoi ce fichier : code d'origine du notebook mini_projet_R.Rmd (blocs : stationnarite), copié sans
# changement de logique. Les scripts partagent le même environnement : les lancer dans l'ordre, par run_all.R.

# ---- bloc d'origine : stationnarite ----
# ADF (H0 : racine unitaire) et KPSS (H0 : stationnarité). Attention : tseries::adf.test inclut une
# tendance et fixe le nombre de retards, alors que statsmodels le choisit par AIC.
tests <- function(v, nom) {
  a <- adf.test(v); k <- kpss.test(v, null = "Level")
  data.frame(serie = nom, ADF_stat = round(a$statistic, 3), ADF_p = round(a$p.value, 4),
             KPSS_stat = round(k$statistic, 3), KPSS_p = round(k$p.value, 4))
}
tab_stat <- rbind(tests(y_train, "production"), tests(diff(y_train), "production - diff. ordre 1"),
                  tests(anomalie[1:n_train], "production - désaisonnalisée"),
                  tests(train$nebulosite_pct, "nébulosité"), tests(train$t2m_moy_c, "température"))
rownames(tab_stat) <- NULL
write.csv(tab_stat, here::here("outputs", "tables", "R_stationnarite.csv"), row.names = FALSE)
tab_stat
