# %% [markdown]
# ### 3.3 Volatilité conditionnelle : ARCH et GARCH

# %%
# Le test ARCH-LM de la section 3.1 rejette l'homoscédasticité des résidus : leur variance dépend du
# passé (et de la saison). On la modélise par un GARCH estimé sur les écarts à la tendance et au
# cycle annuel, c'est-à-dire les erreurs de prévision à un jour de l'ARIMA-Fourier manuel.
from arch import arch_model

# Le filtre de l'ARIMA est prolongé sur toute la période, paramètres figés : sur le test, les
# résidus sont de vraies erreurs de prévision à un jour, hors échantillon.
X_man = fourier(K_F)
complet_man = m_man.apply(y_all, exog=X_man)
e_tout = np.asarray(complet_man.resid)
e_train = e_tout[BRULAGE:n_train]
idx_e = df.index[BRULAGE:n_train]
lm, lm_p, _, _ = het_arch(e_train, nlags=7)
print(f"ARCH-LM(7) sur les résidus de l'ARIMA-Fourier : LM = {lm:.1f}, p = {lm_p:.2e}")
print("ACF des résidus au carré, retards 1 à 7 :", np.round(sm.tsa.acf(e_train ** 2, nlags=7)[1:], 3))

candidats = {"ARCH(1) normale": dict(p=1, q=0, dist="normal"), "GARCH(1,1) normale": dict(p=1, q=1, dist="normal"),
             "GARCH(1,1) Student": dict(p=1, q=1, dist="t"), "GARCH(1,1) Student asym.": dict(p=1, q=1, dist="skewt"),
             "GARCH(2,1) Student asym.": dict(p=2, q=1, dist="skewt"),
             "GJR-GARCH(1,1) Student asym.": dict(p=1, o=1, q=1, dist="skewt"),
             "EGARCH(1,1) Student asym.": dict(p=1, o=1, q=1, vol="EGARCH", dist="skewt")}


def ajuster_garch(e, kw):
    kw = dict(kw)
    vol = kw.pop("vol", "GARCH")
    return arch_model(e, mean="Zero", vol=vol, **kw).fit(disp="off")


ajust_g = {nom: ajuster_garch(e_train, kw) for nom, kw in candidats.items()}

# Variante « saisonnière » : la variance des erreurs suit d'abord le calendrier (hiver pluvieux,
# été sec). On la retire par une régression de log(e²) sur des termes de Fourier, puis on estime un
# GARCH sur les résidus réduits. La vraisemblance est ramenée à l'échelle de e (jacobien) pour que
# l'AIC soit comparable à celui des autres modèles.
Xs = sm.add_constant(fourier(2))
b_s = np.linalg.lstsq(Xs[BRULAGE:n_train], np.log(e_train ** 2 + 1e-4), rcond=None)[0]
# exp(ajusté / 2) sous-estime l'écart-type (E[log chi²(1)] < 0) : on renormalise pour que les résidus
# réduits aient une variance unité sur l'apprentissage.
sig_saison_tout = np.exp(0.5 * (Xs @ b_s))
sig_saison_tout *= np.sqrt(np.mean((e_train / sig_saison_tout[BRULAGE:n_train]) ** 2))
z_saison = e_train / sig_saison_tout[BRULAGE:n_train]
g_sais = ajuster_garch(z_saison, dict(p=1, q=1, dist="skewt"))
ll_sais = g_sais.loglikelihood - np.sum(np.log(sig_saison_tout[BRULAGE:n_train]))
k_sais = len(g_sais.params) + len(b_s)


def ligne_g(g, ll=None, k=None, z=None):
    ll = g.loglikelihood if ll is None else ll
    k = len(g.params) if k is None else k
    z = np.asarray(g.std_resid) if z is None else z
    return {"log-vraisemblance": ll, "AIC": -2 * ll + 2 * k, "BIC": -2 * ll + k * np.log(len(z)), "nb paramètres": k,
            "LB(10) sur z² p": acorr_ljungbox(z ** 2, lags=[10])["lb_pvalue"].iloc[0],
            "ARCH-LM(7) sur z p": het_arch(z, nlags=7)[1], "kurtosis de z": stats.kurtosis(z, fisher=False)}


tab_g = pd.DataFrame({nom: ligne_g(g) for nom, g in ajust_g.items()}).T
tab_g.loc["Variance saisonnière + GARCH(1,1) Student asym."] = ligne_g(
    g_sais, ll_sais, k_sais, np.asarray(g_sais.std_resid))
tab_g.to_csv(RES / "py_garch_comparaison.csv")
print(tab_g.round(4).to_string())

# %%
# Diagnostic : si la volatilité est bien modélisée, les résidus standardisés (résidu / écart-type
# conditionnel) ne doivent plus présenter d'effet ARCH. On examine le GARCH(1,1) de référence, puis on
# retient le modèle de plus petit BIC parmi ceux qui passent le test ARCH-LM à 5 %.
g11 = ajust_g["GARCH(1,1) Student asym."]
print(g11.summary().tables[1], "\n", g11.summary().tables[2])
persist = g11.params["alpha[1]"] + g11.params["beta[1]"]
print(f"GARCH(1,1) : persistance alpha + beta = {persist:.3f} ; demi-vie d'un choc de volatilité = "
      f"{np.log(0.5) / np.log(persist):.1f} jours")
valides = tab_g[tab_g["ARCH-LM(7) sur z p"] > 0.05]
NOM_G = (valides if len(valides) else tab_g)["BIC"].idxmin()
print(f"\nModèles qui passent le test ARCH-LM à 5 % : {list(valides.index)}")
print(f"Modèle de volatilité retenu : {NOM_G}")
SAISONNIER = NOM_G.startswith("Variance saisonnière")
g_ret = g_sais if SAISONNIER else ajust_g[NOM_G]
if SAISONNIER:
    print(g_sais.summary().tables[1])
    print("Coefficients de la variance saisonnière (log e² ~ Fourier K = 2) :", np.round(b_s, 3))
z = np.asarray(g_ret.std_resid)
z11 = np.asarray(g11.std_resid)


def diag_vol(v):
    return [acorr_ljungbox(v, lags=[10])["lb_pvalue"].iloc[0], acorr_ljungbox(v ** 2, lags=[10])["lb_pvalue"].iloc[0],
            het_arch(v, nlags=7)[1], stats.skew(v), stats.kurtosis(v, fisher=False)]


diag_g = pd.DataFrame({"résidus bruts": diag_vol(e_train), "standardisés GARCH(1,1)": diag_vol(z11),
                       f"standardisés {NOM_G}": diag_vol(z)},
                      index=["Ljung-Box(10) p", "Ljung-Box(10) sur les carrés p", "ARCH-LM(7) p", "skewness", "kurtosis"])
diag_g.to_csv(RES / "py_garch_diagnostic.csv")
print(diag_g.round(4).to_string())

# %%
# Volatilité conditionnelle dans le temps, mise en relation avec la saison et avec les épisodes de
# pluie identifiés dans les données (et non avec des événements supposés).
vol = pd.Series(np.asarray(g_ret.conditional_volatility) * (sig_saison_tout[BRULAGE:n_train] if SAISONNIER else 1),
                index=idx_e)
vol11 = pd.Series(np.asarray(g11.conditional_volatility), index=idx_e)
fig, ax = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
ax[0].plot(idx_e, e_train, lw=0.4, color="grey"); ax[0].set_ylabel("résidu (kWh/kWc)")
ax[0].set_title(f"Erreurs à un jour de l'ARIMA-Fourier et volatilité conditionnelle ({NOM_G})")
ax[1].plot(vol, color="#1f3a5f", lw=0.8, label=NOM_G)
ax[1].plot(vol11, color="#e0a030", lw=0.6, alpha=0.8, label="GARCH(1,1) Student asym.")
ax[1].set_ylabel("écart-type conditionnel"); ax[1].legend(fontsize=8)
ax[2].bar(idx_e, train["precipitation_mm"].iloc[BRULAGE:], width=1, color="#2a78d6")
ax[2].set_ylabel("pluie (mm)")
montrer(fig, "13_garch_volatilite")
print("Volatilité moyenne par mois :", vol.groupby(vol.index.month).mean().round(3).to_dict())
top = vol.sort_values(ascending=False).head(10)
evts = pd.DataFrame({"volatilité": top.round(3), "pluie (mm) J-1": train["precipitation_mm"].shift(1).reindex(top.index).round(1),
                     "nébulosité J-1 (%)": train["nebulosite_pct"].shift(1).reindex(top.index).round(0),
                     "erreur J-1": pd.Series(e_tout, index=df.index).shift(1).reindex(top.index).round(2)})
print("Les 10 jours de plus forte volatilité conditionnelle et la météo de la veille :\n", evts.to_string())
pluie_v = train["precipitation_mm"].shift(1).iloc[BRULAGE:] >= 5
print("Volatilité moyenne : lendemain de pluie (>= 5 mm) =", round(vol[pluie_v.to_numpy()].mean(), 3),
      "| autres jours =", round(vol[~pluie_v.to_numpy()].mean(), 3))

# %%
# Utilité pratique : le GARCH ne change pas la prévision ponctuelle mais adapte la largeur de
# l'intervalle. On compare sur le test, par saison, le taux de couverture d'un intervalle à 95 % à un
# jour : variance constante, GARCH(1,1) et modèle retenu.
a_tout = e_tout[BRULAGE:]
n0 = n_train - BRULAGE


def sigma_un_jour(nom):
    """Écart-type prévu à un jour pour chaque jour du test, paramètres estimés sur l'apprentissage."""
    if nom.startswith("Variance saisonnière"):
        zz = a_tout / sig_saison_tout[BRULAGE:]
        g_ = arch_model(zz, mean="Zero", vol="GARCH", p=1, q=1, dist="skewt").fit(last_obs=n0, disp="off")
        v_ = g_.forecast(horizon=1, start=n0 - 1, reindex=False).variance.to_numpy().ravel()[:-1]
        return np.sqrt(v_) * sig_saison_tout[n_train:], g_
    kw = dict(candidats[nom]); vol_ = kw.pop("vol", "GARCH")
    g_ = arch_model(a_tout, mean="Zero", vol=vol_, **kw).fit(last_obs=n0, disp="off")
    v_ = g_.forecast(horizon=1, start=n0 - 1, reindex=False).variance.to_numpy().ravel()[:-1]
    return np.sqrt(v_), g_


e_test = e_tout[n_train:]
mois_test = test.index.month
sais_test = np.where(np.isin(mois_test, [11, 12, 1, 2, 3]), "novembre-mars", "avril-octobre")
lignes_ic = []
for nom in ("variance constante", "GARCH(1,1) Student asym.", NOM_G):
    if nom == "variance constante":
        sig, q_bas, q_haut = np.full(len(e_test), e_train.std()), -1.96, 1.96
    else:
        sig, g_ = sigma_un_jour(nom)
        k_d = g_.model.distribution.num_params           # paramètres de forme de la loi (0, 1 ou 2)
        q_bas, q_haut = g_.model.distribution.ppf([0.025, 0.975], g_.params[-k_d:] if k_d else None)
    dedans = (e_test >= q_bas * sig) & (e_test <= q_haut * sig)
    ligne = {"modèle": nom, "couverture IC 95 % (%)": 100 * dedans.mean(),
             "demi-largeur moyenne": float(np.mean((q_haut - q_bas) / 2 * sig))}
    for s_ in ("novembre-mars", "avril-octobre"):
        ligne[f"couverture {s_} (%)"] = 100 * dedans[sais_test == s_].mean()
    lignes_ic.append(ligne)
ic_garch = pd.DataFrame(lignes_ic).drop_duplicates("modèle").set_index("modèle")
ic_garch.to_csv(RES / "py_garch_intervalles.csv")
print(ic_garch.round(2).to_string())

# %% [markdown]
# **Lecture.**
# - **Effet ARCH confirmé :** LM = 235 (p de l'ordre de 1e-47) ; l'ACF des résidus au carré décroît lentement (0,14 ; 0,11 ; 0,09...).
# - **Loi des erreurs :** la loi de Student asymétrique est très nettement préférée à la loi normale (BIC de 16 469 contre 18 196 pour le GARCH(1,1)) ; son paramètre d'asymétrie (-0,59) confirme que les erreurs négatives sont les plus fortes.
# - **Le GARCH(1,1) ne suffit pas, et sa persistance est un artefact.** Il estime alpha + beta = 1,000 : un GARCH intégré, comme si chaque choc de volatilité durait indéfiniment. En réalité, la variance suit les saisons, et le GARCH prend un changement déterministe pour des chocs persistants. Ses résidus standardisés échouent encore au test ARCH-LM (p = 0,007), comme ceux des ordres voisins, du GJR-GARCH et de l'EGARCH (p ≤ 0,03), malgré de meilleurs AIC pour ces deux derniers.
# - **Modèle retenu : variance saisonnière + GARCH(1,1) Student asymétrique.** On retire d'abord la composante saisonnière de la variance (régression de log e² sur deux harmoniques), puis on modélise le reste par un GARCH(1,1). C'est le seul candidat qui passe le diagnostic (ARCH-LM p = 0,39 ; Ljung-Box sur les carrés p = 0,12), et il a le meilleur AIC et le meilleur BIC (15 632, vraisemblance ramenée à l'échelle des résidus). Sa persistance tombe à alpha + beta = 0,53 : une fois la saison retirée, un choc de volatilité s'éteint en un à deux jours. Ses résidus standardisés gardent des queues épaisses (kurtosis de 7,7), que la loi de Student prend en charge.
# - **Lien avec les événements :** la volatilité est quatre fois plus forte en mars (1,68 kWh/kWc) qu'en juillet (0,42). Les dix jours de plus forte volatilité tombent tous en mars ou en avril, au lendemain d'une erreur de -3,6 à -4,1 kWh/kWc sous un ciel couvert (69 à 100 %), souvent pluvieux (14 mm la veille du 14 mars 2014). La volatilité moyenne vaut 1,49 au lendemain d'une pluie d'au moins 5 mm, contre 1,09 les autres jours.
# - **Utilité pratique :** à variance constante, l'intervalle à 95 % à un jour couvre 95,1 % des jours du test, mais seulement 92,9 % de novembre à mars et 96,5 % d'avril à octobre : trop étroit l'hiver, trop large l'été. Le modèle retenu couvre 97,4 % et 96,7 % : la couverture devient homogène entre les saisons, avec un intervalle en moyenne plus étroit (demi-largeur de 2,03 contre 2,16 kWh/kWc), au prix d'un léger excès de prudence. Le GARCH(1,1) seul ne corrige pas le défaut hivernal (92,5 %).

# %% [markdown]
# ## 4. Modélisation avancée
# ### 4.1 Réseaux de neurones récurrents : LSTM et GRU
#
# **Mise en forme.** Chaque exemple est une fenêtre glissante de `L` jours passés (production, nébulosité,
# température, humidité, pluie, aérosols, position dans l'année), à partir de laquelle le réseau prévoit
# les 7 jours suivants en une passe (prévision directe multi-horizon). Les variables sont centrées-réduites
# avec les statistiques **de l'apprentissage seulement**.
#
# **Cible.** La production est d'abord ramenée à son écart à la normale saisonnière : z = (y - normale du
# jour) / écart-type du jour, normales calculées sur l'apprentissage et lissées sur 31 jours. Le réseau
# prévoit z ; la prévision vaut normale + z x écart-type. Il part donc de la climatologie et n'apprend
# que l'écart, ce qui convient à une série dont la saison explique l'essentiel de la variance.
#
# **Deux jeux d'information**, pour une comparaison équitable avec les modèles classiques :
# - *ex ante* : du futur, le réseau ne connaît que la date (comme l'ARIMA-Fourier et le VAR) ;
# - *ex post* : il reçoit aussi la météo observée des 7 jours à prévoir (comme le SARIMAX météo).

# %%
# Préparation des tenseurs. La graine et les algorithmes déterministes de PyTorch rendent
# l'entraînement reproductible sur une même machine.
import torch
import torch.nn as nn
from sklearn.model_selection import TimeSeriesSplit

torch.manual_seed(SEED)
torch.set_num_threads(4)
torch.use_deterministic_algorithms(True)


def normales(v, index, fin):
    """Moyenne et écart-type par jour de l'année, calculés sur [0, fin) et lissés sur 31 jours."""
    base = pd.Series(np.asarray(v[:fin], dtype=float), index=index[:fin])
    jour = np.minimum(base.index.dayofyear, 365)
    m = base.groupby(jour).mean().reindex(range(1, 366)).interpolate(limit_direction="both").to_numpy()
    s = base.groupby(jour).std().reindex(range(1, 366)).interpolate(limit_direction="both").to_numpy()
    lisser = lambda a: pd.Series(np.tile(a, 3)).rolling(31, center=True).mean().to_numpy()[365:730]
    j_all = np.minimum(index.dayofyear, 365) - 1
    return lisser(m)[j_all], lisser(s)[j_all]


def normer(v, fin=n_train):
    v = np.asarray(v, dtype=float)
    return (v - np.nanmean(v[:fin])) / np.nanstd(v[:fin])


CLIM_M, CLIM_S = normales(y_all, df.index, n_train)
z_all = (y_all - CLIM_M) / CLIM_S
doy = np.column_stack([df["jds_sin"].to_numpy(), df["jds_cos"].to_numpy()])
meteo_rnn = np.column_stack([normer(df["nebulosite_pct"].ffill()), normer(df["t2m_moy_c"]),
                             normer(df["humidite_pct"].ffill()), normer(np.log1p(df["precipitation_mm"].ffill())),
                             normer(df["aerosols_aod"].ffill()), normer(df["amplitude_thermique_c"])])
SEQ = np.column_stack([z_all, meteo_rnn, doy])        # ce que le réseau voit du passé
FUT = {"ex ante": doy, "ex post": np.column_stack([doy, meteo_rnn])}   # ce qu'il sait du futur


def fenetres(origines_, L, info, seq=SEQ, cible=None, fut=FUT, z=z_all):
    """Construit (passé, futur connu, cible) pour une liste de jours d'origine."""
    xs = np.stack([seq[t - L + 1:t + 1] for t in origines_])
    xf = np.stack([fut[info][t + 1:t + 1 + H].ravel() for t in origines_])
    yd = np.stack([z[t + 1:t + 1 + H] for t in origines_]) if cible is None else np.stack([cible[t] for t in origines_])
    return [torch.tensor(a, dtype=torch.float32) for a in (xs, xf, yd)]


class Reseau(nn.Module):
    """Cellule récurrente (LSTM ou GRU) suivie d'une tête dense qui reçoit aussi le futur connu."""

    def __init__(self, cellule, n_seq, n_fut, cache=32, couches=1, dropout=0.1):
        super().__init__()
        rnn = {"LSTM": nn.LSTM, "GRU": nn.GRU}[cellule]
        self.rnn = rnn(n_seq, cache, num_layers=couches, batch_first=True, dropout=dropout if couches > 1 else 0.0)
        self.tete = nn.Sequential(nn.Dropout(dropout), nn.Linear(cache + n_fut, 64), nn.ReLU(), nn.Linear(64, H))

    def forward(self, xs, xf):
        sortie, _ = self.rnn(xs)
        return self.tete(torch.cat([sortie[:, -1], xf], dim=1))


def entrainer(cellule, donnees_app, donnees_val, cache=32, couches=1, dropout=0.1, graine=SEED,
              epoques=80, patience=10, lr=2e-3, lot=128):
    """Entraîne avec arrêt anticipé sur la validation ; renvoie le meilleur modèle et l'historique."""
    torch.manual_seed(graine)
    xs, xf, yd = donnees_app
    vxs, vxf, vyd = donnees_val
    net = Reseau(cellule, xs.shape[2], xf.shape[1], cache, couches, dropout)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
    perte = nn.MSELoss()
    gen = torch.Generator().manual_seed(graine)
    histo, meilleur, etat, attente = [], np.inf, None, 0
    for ep in range(epoques):
        net.train()
        perm = torch.randperm(len(xs), generator=gen)
        tot = 0.0
        for i in range(0, len(xs), lot):
            idx = perm[i:i + lot]
            opt.zero_grad()
            l = perte(net(xs[idx], xf[idx]), yd[idx])
            l.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            tot += l.item() * len(idx)
        net.eval()
        with torch.no_grad():
            lv = perte(net(vxs, vxf), vyd).item()
        histo.append((tot / len(xs), lv))
        if lv < meilleur - 1e-5:
            meilleur, attente = lv, 0
            etat = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            attente += 1
            if attente >= patience:
                break
    net.load_state_dict(etat)
    net.eval()
    return net, np.array(histo)


def prevoir_kwh(net, donnees, origines_, clim_m=CLIM_M, clim_s=CLIM_S):
    """Prévision en kWh/kWc : normale saisonnière + écart prévu x écart-type saisonnier (bornée à 0)."""
    xs, xf, _ = donnees
    with torch.no_grad():
        zc = net(xs, xf).numpy()
    m = np.stack([clim_m[t + 1:t + 1 + H] for t in origines_])
    s_ = np.stack([clim_s[t + 1:t + 1 + H] for t in origines_])
    return np.clip(m + zc * s_, 0, None)


def rmse_kwh(P, origines_):
    vrai = np.stack([y_all[t + 1:t + 1 + H] for t in origines_])
    return float(np.sqrt(np.mean((vrai - P) ** 2)))


# %%
# Validation croisée temporelle (walk-forward, fenêtre d'apprentissage croissante) pour choisir la
# taille de fenêtre et la taille de l'état caché. Jamais de k-fold classique : chaque pli s'entraîne sur
# le passé et se valide sur le futur immédiat, avec un écart de H jours entre les deux.
L_MAX = 28
orig_app = np.arange(L_MAX - 1, n_train - H)        # origines dont les 7 cibles restent dans l'apprentissage
GRILLE = [(L, c) for L in (14, 28) for c in (32, 64)]
t0 = time.time()
lignes_cv = []
for cellule in ("LSTM", "GRU"):
    for L, cache in GRILLE:
        scores = []
        for pli, (i_app, i_val) in enumerate(TimeSeriesSplit(n_splits=3, gap=H).split(orig_app)):
            o_app, o_val = orig_app[i_app], orig_app[i_val]
            coupe = int(len(o_app) * 0.9)             # 10 % les plus récents pour l'arrêt anticipé
            net, _ = entrainer(cellule, fenetres(o_app[:coupe - H], L, "ex ante"),
                               fenetres(o_app[coupe:], L, "ex ante"), cache=cache)
            scores.append(rmse_kwh(prevoir_kwh(net, fenetres(o_val, L, "ex ante"), o_val), o_val))
        lignes_cv.append({"cellule": cellule, "fenêtre L": L, "état caché": cache, "RMSE pli 1": scores[0],
                          "RMSE pli 2": scores[1], "RMSE pli 3": scores[2], "RMSE moyen": np.mean(scores),
                          "écart-type": np.std(scores)})
tab_cv = pd.DataFrame(lignes_cv)
tab_cv.to_csv(RES / "py_validation_croisee_rnn.csv", index=False)
print(tab_cv.round(3).to_string(index=False))
print(f"Durée de la validation croisée : {time.time() - t0:.0f} s")
# Références sur les mêmes plis : climatologie (normale du jour) et persistance (valeur de la veille).
plis = list(TimeSeriesSplit(n_splits=3, gap=H).split(orig_app))
clim_cv = [rmse_kwh(np.stack([CLIM_M[t + 1:t + 1 + H] for t in orig_app[i_val]]), orig_app[i_val]) for _, i_val in plis]
pers_cv = [rmse_kwh(np.stack([np.repeat(y_all[t], H) for t in orig_app[i_val]]), orig_app[i_val]) for _, i_val in plis]
print("RMSE de la climatologie sur les 3 plis :", np.round(clim_cv, 3), "| de la persistance :", np.round(pers_cv, 3))
CONFIG = {c: tuple(int(v) for v in tab_cv[tab_cv["cellule"] == c].sort_values("RMSE moyen")
                   .iloc[0][["fenêtre L", "état caché"]]) for c in ("LSTM", "GRU")}
print("Configuration retenue (fenêtre, état caché) :", CONFIG)

# %% [markdown]
# **Lecture de la validation croisée et justification des hyperparamètres.**
# - **Les réseaux apprennent peu :** sur les trois plis, leur RMSE (1,081 à 1,127 kWh/kWc) est à peine inférieur à celui de la climatologie (1,087 à 1,130) et très inférieur à celui de la persistance (1,51 à 1,56). Sans connaître la météo à venir, il n'y a presque rien à apprendre au-delà du cycle annuel.
# - **Hyperparamètres non identifiables :** les huit configurations sont à moins de 0,003 kWh/kWc les unes des autres, alors que la dispersion entre plis atteint 0,02. On retient la plus petite erreur moyenne (fenêtre de 14 jours, 64 unités) sans prétendre qu'elle soit meilleure.
# - **Choix justifiés par la série :** une fenêtre de 14 jours suffit, la météo ne persistant qu'un ou deux jours (AR(1) de 0,26) ; une seule couche et un dropout de 0,1, car avec environ 5 600 fenêtres un réseau profond aurait bien plus de paramètres que d'exemples ; l'arrêt anticipé (patience de 10 époques) est la principale régularisation.

# %%
# Entraînement final sur tout l'apprentissage (les 10 % les plus récents servent à l'arrêt anticipé),
# pour les deux cellules et les deux jeux d'information. Trois graines par modèle : on mesure la
# sensibilité à l'initialisation au lieu de la cacher.
origines = np.arange(n_train - 1, n - H)             # origines du test (une par jour)
coupe = int(len(orig_app) * 0.9)
reseaux, histos, prev_rnn, sens = {}, {}, {}, []
for cellule in ("LSTM", "GRU"):
    L, cache = CONFIG[cellule]
    for info in ("ex ante", "ex post"):
        nom = f"{cellule} ({info})"
        t0 = time.time()
        for graine in (SEED, SEED + 1, SEED + 2):
            net, histo = entrainer(cellule, fenetres(orig_app[:coupe - H], L, info),
                                   fenetres(orig_app[coupe:], L, info), cache=cache, graine=graine)
            P = prevoir_kwh(net, fenetres(origines, L, info), origines)
            sens.append({"modèle": nom, "graine": graine, "époques": len(histo),
                         "époque retenue": int(np.argmin(histo[:, 1])) + 1, "RMSE test": rmse_kwh(P, origines)})
            if graine == SEED:                        # le modèle de référence est celui de la graine 42
                reseaux[nom], histos[nom], prev_rnn[nom] = net, histo, P
                duree[nom] = time.time() - t0
        nb_param[nom] = sum(p.numel() for p in net.parameters())
tab_sens = pd.DataFrame(sens).pivot(index="modèle", columns="graine", values="RMSE test")
tab_sens["moyenne"], tab_sens["écart-type"] = tab_sens.mean(axis=1), tab_sens.iloc[:, :3].std(axis=1)
tab_sens.to_csv(RES / "py_rnn_sensibilite_graine.csv")
print("RMSE sur le test (kWh/kWc) selon la graine :\n", tab_sens.round(4).to_string())
print("Époques parcourues / époque retenue (graine 42) :",
      {s["modèle"]: f"{s['époques']} / {s['époque retenue']}" for s in sens if s["graine"] == SEED})

fig, ax = plt.subplots(1, 4, figsize=(15, 3.4), sharey=True)
for a, (nom, h) in zip(ax, histos.items()):
    a.plot(h[:, 0], label="apprentissage"); a.plot(h[:, 1], label="validation")
    a.axvline(int(np.argmin(h[:, 1])), color="k", ls=":", lw=1)
    a.set_title(nom, fontsize=10); a.set_xlabel("époque")
ax[0].set_ylabel("perte MSE (écart normalisé)"); ax[0].legend(fontsize=8)
fig.suptitle("Courbes de perte (trait pointillé : époque retenue par l'arrêt anticipé)", y=1.03)
montrer(fig, "14_courbes_perte")

# %% [markdown]
# **Lecture.**
# - **Courbes de perte, ex ante :** la perte de validation reste plate (environ 0,92 en écart normalisé) dès les premières époques, puis remonte pendant que la perte d'apprentissage baisse : le réseau ne trouve pas de signal généralisable et se met à mémoriser l'apprentissage. L'arrêt anticipé retient une époque très précoce (la 3e pour le LSTM, la 7e pour le GRU) : le réseau prévoit alors presque la normale saisonnière, corrigée à un ou deux jours.
# - **Courbes de perte, ex post :** les deux courbes baissent ensemble jusqu'à environ 0,40, deux fois plus bas : avec la météo des jours à prévoir, il y a de l'information à apprendre (époque retenue : la 13e pour le LSTM, la 19e pour le GRU).
# - **Sensibilité à la graine :** l'écart-type du RMSE entre trois initialisations vaut 0,001 kWh/kWc ex ante et 0,005 à 0,014 ex post. C'est l'étalon pour juger les écarts entre réseaux.
# - **LSTM ou GRU :** équivalents (1,0832 contre 1,0825 ex ante, 0,694 contre 0,698 ex post, en moyenne sur trois graines) ; le GRU a 20 % de paramètres en moins.

# %% [markdown]
# ### 4.2 Approche hybride : ARIMA-Fourier + LSTM sur les erreurs

# %%
# Principe : l'ARIMA-Fourier capte la structure linéaire (cycle annuel, persistance de la météo). Un
# LSTM apprend ensuite à prévoir ses erreurs à 7 jours à partir du passé récent, notamment des
# variables météo que l'ARIMA ignore (nébulosité, humidité, aérosols). Tout reste ex ante.
#
# Les prévisions de l'ARIMA depuis chaque origine sont calculées en une fois à partir des états filtrés
# du filtre de Kalman : prévoir h pas depuis t revient à appliquer h fois la matrice de transition à
# l'état filtré en t. C'est exactement ce que fait `get_prediction`, en beaucoup plus rapide (vérifié).
def prev_arima_toutes(res_complet, h_max=H):
    """Matrice (n, h_max) : prévision à 1..h_max pas depuis chaque origine t (NaN au-delà des données)."""
    fr = res_complet.filter_results
    a = fr.filtered_state.copy()                       # états filtrés a(t|t)
    T, Z = fr.transition[:, :, 0], fr.design[:, :, 0]
    c = fr.state_intercept[:, :1]                      # constante d'état (nulle sauf tendance logée dans l'état)
    d = np.broadcast_to(fr.obs_intercept, (1, a.shape[1]))[0]
    out = np.full((a.shape[1], h_max), np.nan)
    for h in range(1, h_max + 1):
        a = T @ a + c                                   # a(t+h|t) = T a(t+h-1|t) + c
        moy = (Z @ a).ravel()                           # composante ARMA prévue à t + h
        out[:-h, h - 1] = moy[:-h] + d[h:]              # + partie déterministe (Fourier, constante) en t + h
    return out


t0 = time.time()
PREV_MAN = prev_arima_toutes(complet_man)
t_c = origines[100]
verif = complet_man.get_prediction(start=t_c + 1, end=t_c + H, dynamic=0).predicted_mean
assert np.allclose(PREV_MAN[t_c], verif, atol=1e-8), "prévision par états filtrés différente de get_prediction"
ERR = np.stack([y_all[t + 1:t + 1 + H] if t + H < n else np.full(H, np.nan) for t in range(n)]) - PREV_MAN
SD_E = np.nanstd(ERR[BRULAGE:n_train - H])
res1 = e_tout.copy()
res1[:BRULAGE] = 0.0
SEQ_H = np.column_stack([res1 / res1[BRULAGE:n_train].std(), meteo_rnn, doy])
L_H, CACHE_H = CONFIG["LSTM"]
cible_h = ERR / SD_E
net_h, histo_h = entrainer("LSTM", fenetres(orig_app[:coupe - H], L_H, "ex ante", SEQ_H, cible_h),
                           fenetres(orig_app[coupe:], L_H, "ex ante", SEQ_H, cible_h), cache=CACHE_H)
xs_, xf_, _ = fenetres(origines, L_H, "ex ante", SEQ_H, cible_h)
with torch.no_grad():
    corr = net_h(xs_, xf_).numpy() * SD_E
P_HYBRIDE = np.clip(PREV_MAN[origines] + corr, 0, None)
duree["Hybride ARIMA + LSTM (ex ante)"] = duree["ARIMA-Fourier manuel"] + time.time() - t0
nb_param["Hybride ARIMA + LSTM (ex ante)"] = nb_param["ARIMA-Fourier manuel"] + sum(p.numel() for p in net_h.parameters())
print(f"Hybride entraîné en {time.time() - t0:.0f} s, {len(histo_h)} époques ; part de la variance des erreurs "
      f"ARIMA expliquée sur le test : {1 - np.mean((ERR[origines] - corr) ** 2) / np.mean(ERR[origines] ** 2):.2%}")

# %% [markdown]
# **Lecture.** Le LSTM entraîné sur les erreurs de l'ARIMA-Fourier n'en explique que 0,8 % sur le test. Il améliore un peu la prévision à un jour (RMSE de 0,994 contre 1,030) mais pas au-delà (1,104 contre 1,099 à 7 jours) : une fois la structure linéaire retirée, il ne reste presque rien de non linéaire à exploiter sans information nouvelle sur la météo à venir. Ce résultat négatif est informatif : la limite vient de l'information disponible, pas de la classe de modèles.

# %% [markdown]
# ### 4.3 Modèles additionnels : Prophet, XGBoost et LSTM global multi-sites

# %%
# Prophet décompose la série en tendance + saisonnalité annuelle. Il est ajusté une fois sur
# l'apprentissage ; il n'utilise pas les dernières observations pour corriger sa prévision.
import logging
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)
from prophet import Prophet

t0 = time.time()
proph = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False, interval_width=0.95)
proph.fit(pd.DataFrame({"ds": train.index, "y": train[CIBLE].to_numpy()}))
pp = proph.predict(pd.DataFrame({"ds": df.index}))
duree["Prophet (ex ante)"] = time.time() - t0
nb_param["Prophet (ex ante)"] = int(sum(np.size(v) for k, v in proph.params.items() if k in ("k", "m", "delta", "beta", "sigma_obs")))
yh, yl, yu = (pp[c].to_numpy() for c in ("yhat", "yhat_lower", "yhat_upper"))
print(f"Prophet ajusté en {duree['Prophet (ex ante)']:.0f} s")

# %%
# XGBoost en prévision directe : un modèle par horizon h, nourri des variables retenues en 2.7
# (retards, météo de la veille, astronomie du jour visé, normale saisonnière). Il exploite les plus de
# 20 variables candidates et fournit une importance des variables cohérente avec la section 2.7.
from xgboost import XGBRegressor

COLS_XGB = ["pv_veille", "pv_j7", "pv_moy7_passe", "pv_ecart_type7_passe", "ghi_veille", "ghi_moy7_passe",
            "nebulosite_pct", "nebulosite_nasa_pct", "humidite_pct", "precipitation_mm", "point_rosee_c",
            "pression_hpa", "rafales_max_kmh", "t2m_moy_c", "amplitude_thermique_c", "aerosols_aod",
            "indice_clarte", "albedo", "et0_mm", "vent_moy_ms"]
base_x = df[COLS_XGB].copy()
base_x["pv_jour"] = df[CIBLE]                        # la valeur du jour d'origine est connue
base_x["pression_tendance"] = df["pression_hpa"].diff()
Xb = base_x.to_numpy(float)
t0 = time.time()
P_XGB = np.zeros((len(origines), H))
imp_xgb = []
o_tr = orig_app[orig_app >= 8]
for h in range(1, H + 1):
    def X_h(oo):
        return np.column_stack([Xb[oo], df["irr_extraterrestre_kwh_m2"].to_numpy()[oo + h], doy[oo + h], CLIM_M[oo + h]])
    cut = int(len(o_tr) * 0.9)
    xgb = XGBRegressor(n_estimators=600, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                       random_state=SEED, n_jobs=4, early_stopping_rounds=40)
    xgb.fit(X_h(o_tr[:cut]), y_all[o_tr[:cut] + h], eval_set=[(X_h(o_tr[cut:]), y_all[o_tr[cut:] + h])], verbose=False)
    P_XGB[:, h - 1] = np.clip(xgb.predict(X_h(origines)), 0, None)
    imp_xgb.append(xgb.feature_importances_)
noms_xgb = list(base_x.columns) + ["irr_extraterrestre (t+h)", "jds_sin (t+h)", "jds_cos (t+h)", "normale (t+h)"]
imp_xgb = pd.DataFrame(imp_xgb, columns=noms_xgb, index=[f"h={h}" for h in range(1, H + 1)]).T
imp_xgb.to_csv(RES / "py_xgboost_importance.csv")
duree["XGBoost direct (ex ante)"] = time.time() - t0
nb_param["XGBoost direct (ex ante)"] = int(H * 600)
print(f"XGBoost : 7 modèles entraînés en {duree['XGBoost direct (ex ante)']:.0f} s")
print("Importance (gain) à h = 1 et h = 7, 8 premières :\n",
      imp_xgb[["h=1", "h=7"]].sort_values("h=1", ascending=False).head(8).round(3).to_string())

# %%
# LSTM global : un seul réseau entraîné sur les 9 villes (France, Tunisie, Espagne), chaque ville étant
# ramenée à ses propres normales saisonnières. Question : les autres jeux de données aident-ils à
# prévoir Tunis, alors qu'ils décrivent d'autres climats ? Même découpage temporel pour toutes les villes.
t0 = time.time()
L_G, CACHE_G = CONFIG["LSTM"]
paquets_app, paquets_val, par_site = [], [], {}
for site in SITES:
    d_s = panel[panel["site"] == site].set_index("date").asfreq("D")
    y_s = d_s[CIBLE].to_numpy()
    m_s, s_s = normales(y_s, d_s.index, n_train)
    z_s = (y_s - m_s) / s_s
    met_s = np.column_stack([normer(d_s["nebulosite_pct"].ffill()), normer(d_s["t2m_moy_c"]),
                             normer(d_s["humidite_pct"].ffill()), normer(np.log1p(d_s["precipitation_mm"].ffill())),
                             normer(d_s["aerosols_aod"].ffill()), normer(d_s["amplitude_thermique_c"])])
    seq_s = np.column_stack([z_s, met_s, doy])
    fut_s = {"ex ante": doy}
    par_site[site] = (seq_s, fut_s, z_s, m_s, s_s)
    paquets_app.append(fenetres(orig_app[:coupe - H], L_G, "ex ante", seq_s, None, fut_s, z_s))
    paquets_val.append(fenetres(orig_app[coupe:], L_G, "ex ante", seq_s, None, fut_s, z_s))
app_g = [torch.cat([p[i] for p in paquets_app]) for i in range(3)]
val_g = [torch.cat([p[i] for p in paquets_val]) for i in range(3)]
net_g, histo_g = entrainer("LSTM", app_g, val_g, cache=CACHE_G)
seq_t, fut_t, z_t, m_t, s_t = par_site[SITE]
P_GLOBAL = prevoir_kwh(net_g, fenetres(origines, L_G, "ex ante", seq_t, None, fut_t, z_t), origines, m_t, s_t)
duree["LSTM global 9 villes (ex ante)"] = time.time() - t0
nb_param["LSTM global 9 villes (ex ante)"] = sum(p.numel() for p in net_g.parameters())
print(f"LSTM global : {len(app_g[0])} fenêtres d'apprentissage (9 villes), {len(histo_g)} époques, "
      f"{duree['LSTM global 9 villes (ex ante)']:.0f} s ; RMSE test Tunis = {rmse_kwh(P_GLOBAL, origines):.4f} "
      f"contre {tab_sens.loc['LSTM (ex ante)', SEED]:.4f} pour le LSTM local")
# Le même réseau prévoit aussi les 8 autres villes : on mesure son erreur relative partout.
glob_sites = {}
for site in SITES:
    seq_s, fut_s, z_s, m_s, s_s = par_site[site]
    y_s = panel[panel["site"] == site].set_index("date").asfreq("D")[CIBLE].to_numpy()
    P_s = prevoir_kwh(net_g, fenetres(origines, L_G, "ex ante", seq_s, None, fut_s, z_s), origines, m_s, s_s)
    Y_s = np.stack([y_s[t + 1:t + 1 + H] for t in origines])
    C_s = np.stack([m_s[t + 1:t + 1 + H] for t in origines])
    glob_sites[SITES[site]["ville"]] = {"RMSE LSTM global": np.sqrt(np.mean((Y_s - P_s) ** 2)),
                                        "RMSE climatologie": np.sqrt(np.mean((Y_s - C_s) ** 2)),
                                        "production moyenne test": Y_s.mean()}
glob_sites = pd.DataFrame(glob_sites).T
glob_sites["gain sur la climatologie (%)"] = 100 * (1 - glob_sites["RMSE LSTM global"] / glob_sites["RMSE climatologie"])
glob_sites.to_csv(RES / "py_lstm_global_par_ville.csv")
print(glob_sites.round(3).to_string())
torch.save({"etat": net_g.state_dict(), "L": L_G, "cache": CACHE_G}, RES / "lstm_global_pv.pt")

# %% [markdown]
# **Lecture.**
# - **Prophet** (RMSE de 1,097) n'est qu'une climatologie lissée : il n'utilise pas les dernières observations, et son erreur est la même à tous les horizons (de 1,098 à 1,094).
# - **XGBoost** (1,083) est le meilleur modèle ex ante à un jour (0,985), grâce à la météo du jour d'origine. Son importance des variables confirme la section 2.7 : la normale du jour visé (0,23), le cosinus du jour (0,21) et le rayonnement extraterrestre (0,14) dominent ; la nébulosité du jour d'origine (NASA 0,06, ERA5 0,04) et la production du jour (0,03) ne comptent qu'à un jour et perdent leur poids à 7 jours (0,015).
# - **LSTM global sur 9 villes** (50 238 fenêtres) : sur Tunis, il fait un peu mieux que le LSTM local (1,078 contre 1,082), différence non significative à un jour mais significative à 7 jours (section 6) : les autres climats servent de régularisation. Le même réseau bat la climatologie dans les 9 villes, de 1,2 % à Tozeur, où le ciel est le plus stable, à 3,8 % à Madrid, où les perturbations persistent davantage.
