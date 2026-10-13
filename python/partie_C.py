# %% [markdown]
# ## 6. Prévision et évaluation
#
# **Protocole.** Pour chacune des origines du test (une par jour), chaque modèle prévoit les 7 jours
# suivants. Les paramètres restent ceux estimés sur l'apprentissage ; seules les observations disponibles
# à la date d'origine sont utilisées. On obtient ainsi près de 690 erreurs par horizon, ce qui permet un
# test de Diebold-Mariano (une seule prévision de 7 jours n'y suffirait pas).
#
# **Deux références naïves**, car aucune ne domine à tous les horizons pour une série solaire :
# - *persistance* : demain comme aujourd'hui (difficile à battre à un jour, la météo étant persistante) ;
# - *climatologie* : la normale saisonnière du jour (difficile à battre à une semaine).
#
# **Deux jeux d'information** distingués dans tous les tableaux : *ex ante* (seule la date du futur est
# connue) et *ex post* (la météo observée des 7 jours est fournie : borne optimiste, une vraie prévision
# météo étant elle-même entachée d'erreur).

# %%
# Prévisions à origine glissante. Pour les ARIMA, moyenne et variance de prévision sont calculées à partir
# des états filtrés (même résultat que get_prediction, vérifié ci-dessous sur une origine).
Y = np.stack([y_all[t + 1:t + 1 + H] for t in origines])
Z975 = stats.norm.ppf(0.975)


def var_prev_arima(res_complet, origines_):
    """Variance de prévision à 1..H pas : P(t+h|t) = T P T' + RQR', var = Z P Z' + H."""
    fr = res_complet.filter_results
    T, Z = fr.transition[:, :, 0], fr.design[:, :, 0]
    RQR = fr.selection[:, :, 0] @ fr.state_cov[:, :, 0] @ fr.selection[:, :, 0].T
    h_obs = fr.obs_cov[0, 0, 0]
    v = np.zeros((len(origines_), H))
    for i, t in enumerate(origines_):
        P = fr.filtered_state_cov[:, :, t]
        for h in range(H):
            P = T @ P @ T.T + RQR
            v[i, h] = (Z @ P @ Z.T)[0, 0] + h_obs
    return v


def prev_arima(res, X):
    complet = res.apply(y_all, exog=X)
    moy = prev_arima_toutes(complet)[origines]
    sd = np.sqrt(var_prev_arima(complet, origines))
    i_c = 50
    p_ = complet.get_prediction(start=origines[i_c] + 1, end=origines[i_c] + H, dynamic=0)
    assert np.allclose(p_.predicted_mean, moy[i_c], atol=1e-6) and np.allclose(p_.se_mean, sd[i_c], atol=1e-6)
    return moy, moy - Z975 * sd, moy + Z975 * sd


def prev_var():
    # Paramètres du VAR estimés sur l'apprentissage, prévision depuis chaque origine avec son intervalle.
    moy, bas, haut = (np.empty((len(origines), H)) for _ in range(3))
    for i, t in enumerate(origines):
        m_, b_, h_ = var_fit.forecast_interval(endog_var[t + 1 - P_VAR:t + 1], H, alpha=0.05,
                                               exog_future=Xv[t + 1:t + 1 + H])
        moy[i], bas[i], haut[i] = m_[:, 0], b_[:, 0], h_[:, 0]
    return moy, bas, haut


prev = {}
prev["Persistance (J)"] = (np.stack([np.repeat(y_all[t], H) for t in origines]), None, None)
prev["Climatologie"] = (np.stack([CLIM_M[t + 1:t + 1 + H] for t in origines]), None, None)
for k in ("Persistance (J)", "Climatologie"):
    duree[k], nb_param[k] = 0.0, 0 if k.startswith("Pers") else 2 * 365
prev["ARIMA-Fourier manuel"] = prev_arima(m_man, fourier(K_F))
prev["ARIMA-Fourier auto"] = prev_arima(m_auto, fourier(K_F))
t0 = time.time()
prev["VAR"] = prev_var()
duree["VAR"], nb_param["VAR"] = time.time() - t0, int(var_fit.params.size)
prev["Prophet (ex ante)"] = tuple(np.stack([v[t + 1:t + 1 + H] for t in origines]) for v in (yh, yl, yu))
for nom in ("LSTM (ex ante)", "GRU (ex ante)"):
    prev[nom] = (prev_rnn[nom], None, None)
prev["Hybride ARIMA + LSTM (ex ante)"] = (P_HYBRIDE, None, None)
prev["XGBoost direct (ex ante)"] = (P_XGB, None, None)
prev["LSTM global 9 villes (ex ante)"] = (P_GLOBAL, None, None)
prev["SARIMAX météo (ex post)"] = prev_arima(m_meteo, np.column_stack([fourier(K_F), X_meteo]))
duree["SARIMAX météo (ex post)"], nb_param["SARIMAX météo (ex post)"] = duree["SARIMAX météo"], nb_param["SARIMAX météo"]
for nom in ("LSTM (ex post)", "GRU (ex post)"):
    prev[nom] = (prev_rnn[nom], None, None)
EX_POST = [k for k in prev if "ex post" in k]
EX_ANTE = [k for k in prev if k not in EX_POST]
print(f"{len(prev)} modèles évalués sur {len(origines)} origines x {H} horizons")

# %%
# Tableau récapitulatif unique : métriques d'erreur (tous horizons confondus), RMSE aux horizons 1 et 7,
# couverture des intervalles à 95 %, coût de calcul, complexité et interprétabilité.
FAMILLE = {"Persistance (J)": "référence", "Climatologie": "référence", "ARIMA-Fourier manuel": "classique",
           "ARIMA-Fourier auto": "classique", "VAR": "classique", "Prophet (ex ante)": "additionnel",
           "LSTM (ex ante)": "neuronal", "GRU (ex ante)": "neuronal", "Hybride ARIMA + LSTM (ex ante)": "hybride",
           "XGBoost direct (ex ante)": "additionnel", "LSTM global 9 villes (ex ante)": "neuronal",
           "SARIMAX météo (ex post)": "classique", "LSTM (ex post)": "neuronal", "GRU (ex post)": "neuronal"}
LISIBLE = {"référence": "totale", "classique": "élevée (coefficients testables)", "additionnel": "moyenne",
           "neuronal": "faible (boîte noire)", "hybride": "moyenne"}
lignes = []
for nom, (P, bas, haut) in prev.items():
    e = Y - P
    lignes.append({"modèle": nom, "information": "ex post" if nom in EX_POST else "ex ante", "famille": FAMILLE[nom],
                   "MSE": np.mean(e ** 2), "RMSE": np.sqrt(np.mean(e ** 2)), "MAE": np.mean(np.abs(e)),
                   "MAPE (%)": 100 * np.mean(np.abs(e) / Y), "WAPE (%)": 100 * np.sum(np.abs(e)) / np.sum(Y),
                   "RMSE h=1": np.sqrt(np.mean(e[:, 0] ** 2)), "RMSE h=7": np.sqrt(np.mean(e[:, 6] ** 2)),
                   "couverture IC 95 % (%)": np.nan if bas is None else 100 * np.mean((Y >= bas) & (Y <= haut)),
                   "durée d'ajustement (s)": duree[nom], "nb paramètres": nb_param[nom],
                   "interprétabilité": LISIBLE[FAMILLE[nom]]})
tab = pd.DataFrame(lignes).set_index("modèle")
tab.to_csv(RES / "py_metriques.csv")
rmse_h = pd.DataFrame({nom: np.sqrt(np.mean((Y - P) ** 2, axis=0)) for nom, (P, _, _) in prev.items()},
                      index=[f"h={h}" for h in range(1, H + 1)]).T
rmse_h.to_csv(RES / "py_rmse_par_horizon.csv")
pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
print(tab.drop(columns=["famille", "interprétabilité"]).to_string())
print("\nComplexité et interprétabilité :\n", tab[["famille", "nb paramètres", "durée d'ajustement (s)", "interprétabilité"]].to_string())
print("\nRMSE (kWh/kWc) par horizon :\n", rmse_h.round(3).to_string())
pd.reset_option("display.float_format")
print("\nMoyenne de la production sur le test :", round(Y.mean(), 3), "kWh/kWc/jour ; minimum :", round(Y.min(), 3))
for ref in ("Persistance (J)", "Climatologie"):
    print(f"Gain de RMSE par rapport à {ref} (%) :", (100 * (1 - tab["RMSE"] / tab.loc[ref, "RMSE"])).round(1).to_dict())
# Couverture des intervalles par saison : la variance des erreurs n'est pas la même l'hiver et l'été.
mois_o = df.index[origines + 1].month
hiver = np.isin(mois_o, [11, 12, 1, 2, 3])
for nom in ("ARIMA-Fourier manuel", "SARIMAX météo (ex post)", "VAR"):
    P, bas, haut = prev[nom]
    dedans = (Y >= bas) & (Y <= haut)
    print(f"Couverture IC 95 % {nom} : novembre-mars {100 * dedans[hiver].mean():.1f} % ; avril-octobre "
          f"{100 * dedans[~hiver].mean():.1f} %")

# %% [markdown]
# **Lecture du tableau.**
# - **Les références :** la persistance se trompe beaucoup (RMSE de 1,434 kWh/kWc, et déjà 1,24 à un jour) : la météo change trop vite. La climatologie (1,100) est la référence difficile à battre.
# - **Ex ante, tous les modèles se tiennent dans un mouchoir :** le LSTM global (1,078) est le meilleur, devant le VAR (1,081), les réseaux locaux (1,082), XGBoost (1,083), l'hybride (1,085), l'ARIMA-Fourier (1,089) et Prophet (1,097). Le gain sur la climatologie va de 0,3 à 2,0 %. Il est concentré sur les deux premiers jours (RMSE de 0,985 à 1,03 à un jour, 7 à 10 % de mieux que la climatologie) ; dès le troisième jour, tous les modèles rejoignent la normale (figure 15). C'est la conséquence directe de l'AR(1) de coefficient 0,26 identifié en section 2.
# - **Ce que vaut la météo :** avec la météo observée des jours à prévoir, l'erreur baisse d'un tiers (SARIMAX météo 0,725 ; LSTM ex post 0,699 ; GRU ex post 0,714) et reste stable à tous les horizons, chaque jour recevant sa propre météo. C'est la réponse à la question posée, avec la réserve habituelle : c'est une borne optimiste, une vraie prévision météo étant elle-même imparfaite.
# - **MAPE et WAPE :** le MAPE (30 % pour la climatologie) est gonflé par les journées très couvertes, où une petite erreur absolue devient une grosse erreur relative ; le WAPE (19 %) en donne une image plus juste.
# - **Intervalles :** ceux de l'ARIMA (95,0 %), du VAR (95,2 %), de Prophet (94,6 %) et du SARIMAX (95,2 %) sont bien calibrés en moyenne, mais pas par saison : 93,5 % de novembre à mars contre 95,9 % d'avril à octobre pour l'ARIMA (92,6 % et 96,8 % pour le SARIMAX). C'est le défaut de variance constante identifié en section 3.3.
# - **Coût :** les modèles classiques ont 7 à 48 paramètres et s'ajustent en moins d'une seconde ; les réseaux en ont 20 000 à 27 000, demandent 7 à 51 secondes et ne fournissent pas d'intervalle.

# %%
# Test de Diebold-Mariano (correction de Harvey, Leybourne et Newbold, perte quadratique et absolue) :
# une différence de RMSE peut être due au hasard ; le test dit si elle est significative.
# Statistique positive = le second modèle est meilleur que la référence.
def diebold_mariano(e_ref, e_mod, h, puissance=2):
    d = np.abs(e_ref) ** puissance - np.abs(e_mod) ** puissance
    T_ = len(d)
    dc = d - d.mean()
    gamma = [np.sum(dc[k:] * dc[:T_ - k]) / T_ for k in range(h)]     # autocovariances jusqu'à h - 1
    var_ = (gamma[0] + 2 * sum(gamma[1:])) / T_
    if var_ <= 0:                                                     # estimateur non défini positif : repli
        var_ = gamma[0] / T_
    stat = d.mean() / np.sqrt(var_) * np.sqrt((T_ + 1 - 2 * h + h * (h - 1) / T_) / T_)
    return stat, 2 * stats.t.sf(abs(stat), T_ - 1)


def comparer(ref, candidats_):
    out = []
    for nom in candidats_:
        ligne = {"référence": ref, "modèle": nom}
        for h in (1, 7):
            e1, e2 = Y[:, h - 1] - prev[ref][0][:, h - 1], Y[:, h - 1] - prev[nom][0][:, h - 1]
            ligne[f"DM h={h}"], ligne[f"p h={h}"] = diebold_mariano(e1, e2, h, 2)
            ligne[f"DM abs h={h}"], ligne[f"p abs h={h}"] = diebold_mariano(e1, e2, h, 1)
        out.append(ligne)
    return pd.DataFrame(out)


meilleur_ante = tab.loc[[k for k in EX_ANTE if FAMILLE[k] != "référence"], "RMSE"].idxmin()
meilleur_post = tab.loc[EX_POST, "RMSE"].idxmin()
dm = pd.concat([
    comparer("Persistance (J)", [k for k in prev if k != "Persistance (J)"]),
    comparer("Climatologie", [k for k in prev if k not in ("Climatologie", "Persistance (J)")]),
    comparer(meilleur_ante, [k for k in EX_ANTE if k != meilleur_ante and FAMILLE[k] != "référence"]),
    comparer(meilleur_post, [k for k in EX_POST if k != meilleur_post]),
    comparer(meilleur_ante, [meilleur_post])], ignore_index=True)
dm.to_csv(RES / "py_diebold_mariano.csv", index=False)
print("Meilleur modèle ex ante :", meilleur_ante, "| meilleur modèle ex post :", meilleur_post)
print(dm.round(4).to_string(index=False))

# %% [markdown]
# **Lecture des tests de Diebold-Mariano et conclusion.**
# - **Contre la persistance :** tous les modèles font significativement mieux à 7 jours (p < 0,001). À un jour, en perte absolue, l'ARIMA-Fourier (p = 0,25), Prophet et la climatologie ne la battent pas : la plupart des jours ressemblent à la veille, mais la persistance commet de très grosses erreurs quand le temps tourne, d'où sa défaite en perte quadratique.
# - **Contre la climatologie :** à un jour, tous les modèles sauf Prophet font significativement mieux (p < 0,001). **À sept jours, aucun modèle ex ante ne fait significativement mieux** ; le LSTM local fait même significativement moins bien (statistique de -2,82 ; p = 0,005), comme XGBoost en perte absolue (p = 0,025). Les modèles ex post battent la climatologie à tous les horizons (p < 0,001).
# - **Meilleur modèle ex ante (LSTM global) :** significativement meilleur que l'ARIMA-Fourier (p < 0,001) et le VAR (p = 0,011) à un jour, mais pas à sept jours (p = 0,40 et 0,64). Il fait mieux que le LSTM local à sept jours (p = 0,008) mais pas à un jour : les données des autres villes rendent la prévision plus robuste aux horizons longs.
# - **Ex post :** le LSTM n'est pas significativement meilleur que le SARIMAX météo en perte quadratique (p = 0,32 à un jour, 0,074 à sept jours) ; il l'est en perte absolue (p = 0,045 et 0,0001).
#
# **Conclusion sur le meilleur modèle selon le cas d'usage.**
# - **Sans prévision météo :** au-delà de deux jours, rien ne bat la normale saisonnière, et il faut le dire. À un ou deux jours, le **VAR** est recommandé : un peu moins précis que le LSTM global (RMSE de 1,009 contre 0,989 à un jour, écart significatif mais de 2 %), il est interprétable (causalité de Granger, réponse impulsionnelle), fournit un intervalle calibré et s'ajuste en une demi-seconde. Le LSTM global est le plus précis, mais son avantage est faible et il n'apporte ni intervalle ni explication.
# - **Avec une prévision météo :** le **SARIMAX météo** pour un exploitant qui doit justifier ses décisions (effet chiffré des nuages, de la pluie et des poussières, intervalle calibré) ; le LSTM ex post si seule compte la précision (RMSE inférieur de 3,6 %). Le gain réel dépendra de la qualité de la prévision météo utilisée.

# %%
# Graphiques de synthèse : RMSE par horizon, puis deux exemples de prévision à 7 jours (un épisode
# nuageux d'hiver, une semaine d'été) avec l'intervalle à 95 % de l'ARIMA-Fourier.
fig, ax = plt.subplots(1, 2, figsize=(14, 4.8), sharey=True)
# Onze modèles ex ante ne se lisent pas en couleurs distinctes : on met en évidence les références et les
# meilleurs modèles de chaque famille, les autres restent en gris fin (étiquetés dans le tableau).
EVIDENCE = {"Persistance (J)": ("#898781", ":"), "Climatologie": ("#0b0b0b", ":"),
            "ARIMA-Fourier manuel": ("#2a78d6", "-"), "VAR": ("#1baf7a", "-"),
            "LSTM global 9 villes (ex ante)": ("#eb6834", "-"), "SARIMAX météo (ex post)": ("#2a78d6", "-"),
            "LSTM (ex post)": ("#eb6834", "-"), "GRU (ex post)": ("#1baf7a", "-")}
for nom in prev:
    a = ax[0] if nom in EX_ANTE else ax[1]
    if nom in EVIDENCE:
        c, ls = EVIDENCE[nom]
        a.plot(range(1, H + 1), rmse_h.loc[nom], ls=ls, color=c, lw=2, marker="o", ms=4, label=nom, zorder=3)
    else:
        a.plot(range(1, H + 1), rmse_h.loc[nom], color="#c3c2b7", lw=1, zorder=1)
ax[0].plot([], [], color="#c3c2b7", lw=1, label="autres modèles ex ante (voir tableau)")
for ref in ("Persistance (J)", "Climatologie"):
    c, ls = EVIDENCE[ref]
    ax[1].plot(range(1, H + 1), rmse_h.loc[ref], ls=ls, color=c, lw=1.5, label=f"rappel : {ref}")
for a, titre in zip(ax, ("Information ex ante", "Information ex post (météo observée connue)")):
    a.set_title(titre); a.set_xlabel("horizon (jours)"); a.legend(fontsize=7, loc="center right")
ax[0].set_ylabel("RMSE (kWh/kWc)")
ax[0].set_ylim(0.6, rmse_h.to_numpy().max() * 1.04)
montrer(fig, "15_rmse_par_horizon")

i_hiver = int(np.argmax([np.std(y_all[t + 1:t + 1 + H]) if df.index[t].month in (12, 1, 2) else 0 for t in origines]))
i_ete = int(np.argmin([abs(df.index[t].dayofyear - 190) + 1000 * (df.index[t].year != 2023) for t in origines]))
fig, ax = plt.subplots(1, 2, figsize=(14, 4.2))
for a, i in zip(ax, (i_hiver, i_ete)):
    t = origines[i]
    jp = df.index[t + 1:t + 1 + H]
    a.plot(df.index[t - 20:t + 1 + H], y_all[t - 20:t + 1 + H], color="k", marker="o", ms=3, label="observé")
    P, bas, haut = prev["ARIMA-Fourier manuel"]
    a.fill_between(jp, bas[i], haut[i], color="#1a8a8a", alpha=0.2, label="IC 95 % ARIMA-Fourier")
    a.plot(jp, P[i], color="#1a8a8a", lw=2, label="ARIMA-Fourier")
    a.plot(jp, prev["SARIMAX météo (ex post)"][0][i], color="#e0a030", lw=2, label="SARIMAX météo (ex post)")
    a.plot(jp, prev["LSTM (ex ante)"][0][i], color="#8e44ad", lw=1.5, ls="--", label="LSTM (ex ante)")
    a.plot(jp, prev["Climatologie"][0][i], color="grey", lw=1, ls=":", label="climatologie")
    a.axvline(df.index[t], color="grey", ls=":")
    a.set_title(f"Prévision à 7 jours depuis le {df.index[t].date()}"); a.set_ylabel("kWh/kWc")
    a.tick_params(axis="x", labelrotation=30)
ax[0].legend(fontsize=7)
montrer(fig, "16_exemples_prevision")

# %%
# Vérification croisée avec R : si le notebook R a été exécuté, on met côte à côte les RMSE des modèles
# communs. Des écarts faibles confirment que les deux implémentations estiment le même modèle.
f_r = RES / "R_metriques.csv"
if f_r.exists():
    r_tab = pd.read_csv(f_r, index_col=0)
    commun = [k for k in r_tab.index if k in tab.index]
    croise = pd.DataFrame({"RMSE Python": tab.loc[commun, "RMSE"], "RMSE R": r_tab.loc[commun, "RMSE"],
                           "MAE Python": tab.loc[commun, "MAE"], "MAE R": r_tab.loc[commun, "MAE"]})
    croise["écart RMSE (%)"] = 100 * (croise["RMSE R"] / croise["RMSE Python"] - 1)
    croise.to_csv(RES / "comparaison_R_python.csv")
    print(croise.round(4).to_string())
else:
    print("Fichier resultats/R_metriques.csv absent : compiler d'abord mini_projet_R.Rmd.")

# %% [markdown]
# **Lecture.** Les deux langages donnent les mêmes résultats : RMSE identiques pour la persistance, la climatologie et le VAR, écart de 0,002 % pour l'ARIMA-Fourier et de 0,15 % pour le SARIMAX météo. Ces petits écarts viennent des algorithmes d'estimation (maximum de vraisemblance exact en R, algorithme des innovations avec moindres carrés généralisés en Python) et du filtre, appliqué en R aux 500 jours qui précèdent chaque origine. Les deux grilles et les deux recherches automatiques retiennent le même ARIMA(1,0,0) à deux harmoniques.

# %% [markdown]
# ## 7. Extensions
# ### 7.1 Corrélation dynamique entre pays
#
# Une corrélation statique unique cache des variations dans le temps. On mesure, sur une fenêtre glissante
# de 90 jours, la corrélation entre les anomalies de production de Tunis et celles de trois autres villes.

# %%
# Anomalies = écart au cycle annuel (Fourier, estimé sur l'apprentissage) ; corrélation glissante 90 jours.
anoms = pd.DataFrame({SITES[s]["ville"]: anomalie_site(s) for s in ("tunis", "tozeur", "seville", "marseille", "paris")},
                     index=df.index)
glis = {v: anoms["Tunis"].rolling(90).corr(anoms[v]) for v in ("Tozeur", "Séville", "Marseille", "Paris")}
fig, ax = plt.subplots(figsize=(12, 3.8))
# Couleur du pays de la ville comparée (Tunisie, Espagne, France) ; Paris en tirets pour la distinguer de Marseille.
for v, c, ls in zip(glis, (COULEUR_PAYS["Tunisie"], COULEUR_PAYS["Espagne"], COULEUR_PAYS["France"], COULEUR_PAYS["France"]),
                    ("-", "-", "-", "--")):
    ax.plot(glis[v], lw=0.9, ls=ls, label=f"Tunis / {v}", color=c)
ax.axhline(0, color="k", lw=0.6); ax.set_ylabel("corrélation glissante (90 j)"); ax.legend(fontsize=8, ncol=4)
ax.set_title("Corrélation dynamique des anomalies de production avec Tunis")
montrer(fig, "17_correlation_dynamique")
corr_saison = pd.DataFrame({v: {s_: anoms.loc[np.isin(anoms.index.month, m_), "Tunis"].corr(anoms.loc[np.isin(anoms.index.month, m_), v])
                                for s_, m_ in (("hiver (DJF)", [12, 1, 2]), ("printemps (MAM)", [3, 4, 5]),
                                               ("été (JJA)", [6, 7, 8]), ("automne (SON)", [9, 10, 11]))}
                            for v in ("Tozeur", "Séville", "Marseille", "Paris")})
corr_saison.to_csv(RES / "py_correlation_saisonniere.csv")
print("Corrélation des anomalies avec Tunis, par saison :\n", corr_saison.round(3).to_string())
print("Distance approximative à Tunis (km) :", {v: int(6371 * np.arccos(
    np.sin(np.radians(SITES["tunis"]["lat"])) * np.sin(np.radians(SITES[s]["lat"])) +
    np.cos(np.radians(SITES["tunis"]["lat"])) * np.cos(np.radians(SITES[s]["lat"])) *
    np.cos(np.radians(SITES[s]["lon"] - SITES["tunis"]["lon"])))) for v, s in
    (("Tozeur", "tozeur"), ("Séville", "seville"), ("Marseille", "marseille"), ("Paris", "paris"))})

# %% [markdown]
# **Lecture.** Le même jour, Tunis et Tozeur (370 km) partagent une partie de leur météo : corrélation de 0,28 en hiver à 0,40 en été, avec des pointes à 0,7 lors de certains épisodes. Avec Séville, Marseille et Paris, la corrélation fluctue autour de zéro (|r| ≤ 0,14 par saison) : les anomalies des trois pays sont presque indépendantes le même jour. Conséquence pratique : un portefeuille d'installations réparties entre la France, l'Espagne et la Tunisie lisserait fortement la production journalière. La corrélation glissante varie beaucoup (de -0,4 à +0,5 pour Paris) : les épisodes météorologiques communs sont ponctuels, ce qu'une corrélation statique unique masquerait.

# %% [markdown]
# ### 7.2 Validation externe : la simulation PVGIS face à la production nationale mesurée
#
# Les séries PVGIS sont simulées à partir d'images satellite. Sont-elles réalistes ? On les confronte aux
# productions mesurées sur les réseaux français (RTE) et espagnol (REE). La production nationale croît
# avec le parc installé : on divise chaque série par sa moyenne glissante centrée sur 365 jours, ce qui
# retire la croissance du parc et garde les variations météorologiques jour après jour.

# %%
# Division par la moyenne glissante sur un an : retire la croissance du parc installé (absente de PVGIS, simulé à
# puissance constante) pour ne comparer que les variations météorologiques journalières.
def normaliser_tendance(s_):
    return s_ / s_.rolling(365, center=True, min_periods=300).mean()


pv_fr = panel[panel["code_pays"] == "FR"].groupby("date")[CIBLE].mean()
pv_es = panel[panel["code_pays"] == "ES"].groupby("date")[CIBLE].mean()
val = pd.DataFrame({"PVGIS France (moyenne 3 villes)": normaliser_tendance(pv_fr),
                    "RTE France (mesuré)": normaliser_tendance(rte["production_gwh"]),
                    "PVGIS Espagne (moyenne 3 villes)": normaliser_tendance(pv_es),
                    "REE Espagne (mesuré)": normaliser_tendance(ree["produccion_gwh"])}).loc["2016":"2023"]
r_fr = val["PVGIS France (moyenne 3 villes)"].corr(val["RTE France (mesuré)"])
r_es = val["PVGIS Espagne (moyenne 3 villes)"].corr(val["REE Espagne (mesuré)"])
d_fr = (val["PVGIS France (moyenne 3 villes)"] - 1).corr(val["RTE France (mesuré)"] - 1, method="spearman")
print(f"Corrélation journalière (2016-2023, tendance retirée) : France r = {r_fr:.3f} ; Espagne r = {r_es:.3f}")
an_corr = pd.DataFrame({"France": val.groupby(val.index.year).apply(
    lambda g: g["PVGIS France (moyenne 3 villes)"].corr(g["RTE France (mesuré)"])),
    "Espagne": val.groupby(val.index.year).apply(lambda g: g["PVGIS Espagne (moyenne 3 villes)"].corr(g["REE Espagne (mesuré)"]))})
an_corr.to_csv(RES / "py_validation_externe.csv")
print("Corrélation par année :\n", an_corr.round(3).to_string())
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
seg = val.loc["2022-03-01":"2022-06-30"]
ax[0].plot(seg.index, seg["PVGIS France (moyenne 3 villes)"], label="PVGIS (3 villes)", color=COULEUR_PAYS["France"])
ax[0].plot(seg.index, seg["RTE France (mesuré)"], label="RTE (national, mesuré)", color="k", lw=1)
ax[0].set_title(f"France, printemps 2022 (r sur 2016-2023 = {r_fr:.2f})"); ax[0].legend(fontsize=8)
ax[0].set_ylabel("production / moyenne glissante 365 j"); ax[0].tick_params(axis="x", labelrotation=30)
ax[1].scatter(val["PVGIS Espagne (moyenne 3 villes)"], val["REE Espagne (mesuré)"], s=3, alpha=0.3, color=COULEUR_PAYS["Espagne"])
ax[1].set_xlabel("PVGIS Espagne (3 villes)"); ax[1].set_ylabel("REE Espagne (mesuré)")
ax[1].set_title(f"Espagne, 2016-2023 (r = {r_es:.2f})")
montrer(fig, "18_validation_externe")

# %% [markdown]
# **Lecture.** Une fois retirée la croissance du parc, la moyenne des trois villes PVGIS suit de très près la production nationale mesurée : corrélation journalière de 0,91 pour la France (83 % de la variance) et de 0,87 pour l'Espagne sur 2016-2023, stable d'une année à l'autre (0,89 à 0,93 en France). Les données satellitaires utilisées dans tout le projet décrivent donc bien la réalité du terrain. L'écart résiduel a des causes connues : trois villes ne représentent pas tout un parc national, et beaucoup de centrales espagnoles suivent le soleil au lieu d'être fixes. La baisse observée en Espagne en 2023 (0,72) reste à expliquer ; deux hypothèses, que nos données ne permettent pas de trancher, sont la croissance très rapide du parc cette année-là (mal corrigée par la moyenne glissante) et l'écrêtement de la production aux heures de prix bas.

# %% [markdown]
# ## 5. IA générative : construction des prompts
#
# Les prompts sont construits à partir des sorties de ce notebook, pour que le LLM raisonne sur les vrais
# chiffres et que chaque affirmation de sa réponse puisse être vérifiée. Les réponses sont obtenues par le
# script `llm/interroger_llm.py` et conservées intégralement dans `llm/` ; notre interprétation, rédigée
# avant de solliciter le LLM, est dans `llm/interpretation_experte.md`, et l'analyse critique dans le rapport.

# %%
# Prompt 1 : statistiques descriptives et tests de stationnarité seulement (aucun résultat de modèle),
# pour que le LLM propose des hypothèses de modèles « à l'aveugle ».
LLM = RACINE / "llm"
LLM.mkdir(exist_ok=True)
prompt1 = f"""Tu es un statisticien spécialiste des séries temporelles. Voici les statistiques descriptives d'une série journalière, sans autre information sur les modèles déjà essayés.

Série : production photovoltaïque journalière simulée par PVGIS pour 1 kWc installé à Tunis (kWh/kWc), du {train.index[0].date()} au {train.index[-1].date()} ({len(train)} observations). Séries associées : éclairement horizontal, nébulosité, température, pluie, aérosols.

Statistiques descriptives :
{stats_desc.to_string()}

Production moyenne par mois (kWh/kWc/jour) : {mois_moy['mean'].round(2).tolist()}
Écart-type par mois : {mois_moy['std'].round(2).tolist()}
Autocorrélation de la production aux retards 1, 2, 7, 30, 182, 365 : {np.round(acf_v[[1, 2, 7, 30, 182, 365]], 3).tolist()}
Autocorrélation de la série désaisonnalisée aux retards 1 à 7 : {np.round(acf_a[1:8], 3).tolist()}

Tests de stationnarité (ADF : H0 = racine unitaire ; KPSS : H0 = stationnarité) :
{tab_stat[['ADF stat', 'ADF p', 'KPSS stat', 'KPSS p']].to_string()}

Questions :
1. Quelles hypothèses de modèles proposes-tu de tester (au moins quatre), et pourquoi ?
2. Quels ordres de différenciation (d et D) recommandes-tu, et comment traiter la saisonnalité annuelle ?
3. Faut-il transformer la série ?
4. Quels pièges vois-tu ?
Réponds en français, de façon concise et structurée."""

# Prompt 2 : les résultats, pour une explication vulgarisée destinée à un décideur.
res_txt = tab[["information", "RMSE", "MAE", "MAPE (%)", "RMSE h=1", "RMSE h=7"]].round(3).to_string()
g_neb = granger[(granger["cause"] == "nebulosite_pct") & (granger["effet"] == CIBLE)].iloc[0]
prompt2 = f"""Voici les résultats d'une étude de prévision de la production photovoltaïque journalière d'une installation de 1 kWc à Tunis, à 7 jours. Les modèles ont été estimés sur {len(train)} jours ({train.index[0].date()} au {train.index[-1].date()}) et évalués sur {len(test)} jours ({test.index[0].date()} au {test.index[-1].date()}), avec {len(origines)} prévisions glissantes de 7 jours.

« ex ante » : le modèle ne connaît du futur que la date. « ex post » : il reçoit en plus la météo réellement observée sur les 7 jours (nébulosité, pluie, humidité, aérosols).

Erreurs de prévision (kWh/kWc/jour ; production moyenne sur le test : {Y.mean():.2f} kWh/kWc/jour) :
{res_txt}

Autres résultats :
- Causalité de Granger : le passé de la nébulosité aide à prévoir la production (F = {g_neb['F']:.1f}, p = {g_neb['p']:.1e}).
- Dans le SARIMAX météo, 10 points de nébulosité supplémentaires changent la production de {10 * coef.loc['nebulosite_pct', 'coef']:+.3f} kWh/kWc, plus {10 * coef.loc['neb_x_potentiel', 'coef'] / 100:+.4f} kWh/kWc par kWh/m² de rayonnement extraterrestre (effet plus fort l'été).
- Les erreurs ont une variance non constante (test ARCH-LM, p = {lm_p:.1e}), plus forte l'hiver, modélisée par : {NOM_G}.

Explique ces résultats à un décideur non statisticien (gestionnaire d'un parc de toitures solaires à Tunis), en 250 mots au maximum, sans jargon. Dis quel modèle tu recommandes et pourquoi."""

# Prompt 3 : recommandations de gestion à partir des prévisions, avec limites formulées par le LLM.
prompt3 = f"""À partir des résultats ci-dessous, propose des recommandations de gestion pour l'exploitant d'installations photovoltaïques en toiture à Tunis (planification de la maintenance et du nettoyage des modules, pilotage d'une batterie, engagement de production auprès du réseau, information des usagers).

Résultats :
- Meilleur modèle sans prévision météo (ex ante) : {meilleur_ante}, erreur absolue moyenne {tab.loc[meilleur_ante, 'MAE']:.2f} kWh/kWc/jour (MAPE {tab.loc[meilleur_ante, 'MAPE (%)']:.1f} %), RMSE à 1 jour {tab.loc[meilleur_ante, 'RMSE h=1']:.2f} et à 7 jours {tab.loc[meilleur_ante, 'RMSE h=7']:.2f}.
- Meilleur modèle avec météo observée (ex post) : {meilleur_post}, erreur absolue moyenne {tab.loc[meilleur_post, 'MAE']:.2f} kWh/kWc/jour (MAPE {tab.loc[meilleur_post, 'MAPE (%)']:.1f} %).
- Références : persistance (demain = aujourd'hui) MAE {tab.loc['Persistance (J)', 'MAE']:.2f} ; normale saisonnière MAE {tab.loc['Climatologie', 'MAE']:.2f}.
- Production annuelle d'1 kWc à Tunis : {synth.loc['tunis', 'productible_kwh_kwc_an']:.0f} kWh ; production moyenne en janvier {mois_moy['mean'].iloc[0]:.2f} et en juillet {mois_moy['mean'].iloc[6]:.2f} kWh/kWc/jour.
- L'incertitude des prévisions est plus forte de novembre à mars (variance conditionnelle, modèle {NOM_G}).
- Les données sont simulées par PVGIS à partir d'images satellite (2005-2023), pas mesurées sur une installation réelle.

Donne 4 recommandations concrètes. Pour chacune, formule toi-même ses limites et ses risques. Termine par une liste de ce que ces résultats ne permettent PAS de conclure. Réponds en français, 350 mots au maximum."""

for k, txt in enumerate((prompt1, prompt2, prompt3), start=1):
    (LLM / f"prompt_{k}.txt").write_text(txt, encoding="utf-8")
print(prompt1[:1500], "\n[...]")

# %%
# Affichage des réponses du LLM si elles ont déjà été générées (voir llm/interroger_llm.py).
for k in (1, 2, 3):
    f = LLM / f"reponse_{k}.md"
    print(f"\n{'=' * 30} Réponse au prompt {k} {'=' * 30}")
    print(f.read_text(encoding="utf-8") if f.exists() else "(pas encore générée)")

# %%
# Versions des bibliothèques, pour la reproductibilité.
import arch, sklearn, statsmodels, prophet, xgboost
print("python", sys.version.split()[0])
for mod in (np, pd, matplotlib, statsmodels, pm, arch, sklearn, xgboost, torch, prophet):
    print(f"{mod.__name__:12s} {mod.__version__}")
