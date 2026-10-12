# %% [markdown]
# # Mini-projet Séries Temporelles : production photovoltaïque et éclairement solaire
# ## France, Tunisie, Espagne - données PVGIS issues des liens du rapport SolarVision
#
# **Thématique : option B (environnement et énergie).** Notebook Python complet (sections 1 à 6 de
# l'énoncé, extensions comprises). Le socle classique (sections 1 à 3 et l'évaluation) est aussi
# codé en R dans `mini_projet_R.Rmd`.
#
# **Pourquoi cette série :** le rapport SolarVision estime la production d'une toiture à Tunis avec une
# irradiation supposée de 1 800 kWh/m²/an « à remplacer par la valeur PVGIS » ; nous partons du lien
# PVGIS de ce rapport pour passer d'un ordre de grandeur annuel à une prévision journalière.
#
# **Question de modélisation :** peut-on prévoir à 7 jours la production journalière d'une installation
# photovoltaïque à Tunis, et que gagne-t-on à connaître la météo à venir (nébulosité, pluie, aérosols) ?
# Les huit autres villes (France, Tunisie, Espagne) servent de comparaison et à entraîner un modèle global.
#
# **Packages requis** (versions utilisées, voir `requirements.txt`) : python 3.14, numpy 2.3.5,
# pandas 2.3.3, matplotlib 3.10.8, scipy 1.17.0, statsmodels 0.15.0, pmdarima 2.1.1, arch 8.0.0,
# scikit-learn 1.8.0, xgboost 3.1.3, torch 2.12.1 (CPU), prophet 1.5.0, requests 2.32.5, pypdf 6.10.2,
# pyarrow 22.0.0.
#
# **Reproductibilité :** graine fixée à 42, calcul sur CPU. Si `data/datasets/` est vide, la première
# cellule de données lance la collecte (`python/collecte_donnees.py`, environ 20 minutes de
# téléchargement). Durée d'exécution du notebook ensuite : environ 30 minutes.

# %%
# Imports et réglages globaux : la graine rend identiques, d'une exécution à l'autre, les réseaux
# de neurones et tous les tirages aléatoires.
import json
import os
import random
import sys
import time
import warnings
from pathlib import Path

import matplotlib
if "get_ipython" not in globals():
    matplotlib.use("Agg")  # exécution en script : pas de fenêtre graphique
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import statsmodels.api as sm
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import jarque_bera
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller, coint, kpss
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.api import VAR
from statsmodels.tsa.vector_ar.vecm import VECM, coint_johansen

warnings.filterwarnings("ignore")
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
pd.set_option("display.width", 170)
pd.set_option("display.max_columns", 30)
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False})

RACINE = Path.cwd()
DATA, JEUX, FIG, RES = RACINE / "data", RACINE / "data" / "datasets", RACINE / "figures", RACINE / "resultats"
for d in (FIG, RES):
    d.mkdir(exist_ok=True)
# Couleurs par pays, réutilisées dans toutes les figures comparatives : trois premiers emplacements d'une
# palette catégorielle validée pour les daltonismes (le rouge reste réservé aux alertes).
COULEUR_PAYS = {"France": "#2a78d6", "Tunisie": "#eb6834", "Espagne": "#1baf7a"}


def montrer(fig, nom):
    """Enregistre la figure pour le rapport puis l'affiche dans le notebook."""
    fig.tight_layout()
    fig.savefig(FIG / f"{nom}.png", dpi=150, bbox_inches="tight")
    plt.show()
    plt.close(fig)


# %% [markdown]
# ## 1. Importation et préparation des données
#
# ### 1.1 Des liens du rapport SolarVision aux jeux de données
#
# Le script `python/collecte_donnees.py` lit les hyperliens du PDF du rapport SolarVision, visite chacun
# d'eux et interroge le seul qui donne accès à des séries temporelles : l'API de **PVGIS** (Commission
# européenne, JRC). Il complète PVGIS par deux sources de variables exogènes (Open-Meteo/ERA5 et NASA
# POWER) et par les productions solaires nationales mesurées par RTE (France) et REE (Espagne).
#
# | Source | Contenu utilisé | Fréquence |
# |---|---|---|
# | PVGIS 5.3 (lien du rapport) | puissance d'1 kWc, éclairement incliné et horizontal, hauteur du soleil, température, vent | horaire |
# | Open-Meteo (ERA5) | nébulosité, ensoleillement, pluie, humidité, point de rosée, pression, rafales, ET0, rayonnement ERA5 | journalière |
# | NASA POWER | rayonnement par ciel clair, indice de clarté, aérosols, UV, albédo, rayonnement photosynthétique | journalière |
# | RTE éCO2mix, REE | production solaire nationale mesurée (France, Espagne) | 30 min / journalière |
#
# **Période :** 2005-2023 pour PVGIS (couverture de la base satellitaire SARAH3), soit 6 939 jours par ville.

# %%
# Collecte : si les jeux de données n'existent pas encore, on les télécharge et on les construit
# (le script met chaque réponse d'API en cache dans data/brut/, une relance est donc rapide).
sys.path.insert(0, str(RACINE / "python"))
from collecte_donnees import SITES, assurer_donnees  # noqa: E402

assurer_donnees()
catalogue = json.loads((DATA / "catalogue_datasets.json").read_text(encoding="utf-8"))
tab_cat = pd.DataFrame([{"jeu de données": c["fichier"].split("/")[-1], "thème": c["theme"], "pays": c["pays"],
                         "lignes": c["lignes"], "colonnes": c["colonnes"],
                         "manquants (%)": c["valeurs_manquantes_pct"]} for c in catalogue])
print(f"{len(tab_cat)} jeux de données :\n", tab_cat.to_string(index=False))
liens = json.loads((RACINE / "sources" / "liens_rapport_solarvision.json").read_text(encoding="utf-8"))
print("\nLiens du rapport SolarVision par catégorie :",
      pd.Series([l["categorie"] for l in liens]).value_counts().to_dict())

# %%
# Table de modélisation : le panel des 9 villes, indexé par date avec une fréquence journalière
# déclarée (objet série temporelle natif de pandas).
panel = pd.read_csv(JEUX / "panel_9_villes_journalier.csv", parse_dates=["date"])
SITE = "tunis"
CIBLE = "pv_kwh_kwc"
df = panel[panel["site"] == SITE].set_index("date").asfreq("D")
variables = [c for c in df.columns if c not in ("site", "ville", "pays", "code_pays", "latitude", "longitude")]
print("Dimensions (Tunis) :", df.shape, "| période :", df.index.min().date(), "->", df.index.max().date(),
      "| fréquence :", df.index.freqstr, "| variables :", len(variables))
manq = df[variables].isna().sum()
print("Valeurs manquantes par variable (non nulles seulement) :", manq[manq > 0].to_dict())
print("Heures de rayonnement reconstruites par PVGIS :", int(df["heures_reconstruites"].sum()),
      "sur", len(df) * 24)
df[[CIBLE, "ghi_kwh_m2", "nebulosite_pct", "t2m_moy_c", "aerosols_aod"]].head()

# %%
# Lien avec le rapport SolarVision : il suppose G = 1 800 kWh/m²/an à Tunis, un rendement de 20 %
# et un ratio de performance de 0,8, soit 28 800 kWh/an pour 100 m² utiles. On recalcule avec PVGIS.
synth = pd.read_csv(DATA / "reference" / "pvgis_synthese_9_villes.csv", index_col="site")
G_RAPPORT, ETA, PR = 1800, 0.20, 0.80
for site in synth.index:
    synth.loc[site, "ghi_annuel_kwh_m2"] = panel[panel["site"] == site].groupby(
        panel.loc[panel["site"] == site, "date"].dt.year)["ghi_kwh_m2"].sum().mean()
synth["production_100m2_kwh_an"] = synth["productible_kwh_kwc_an"] * 100 * ETA     # 100 m² x 0,2 kWc/m²
print(synth[["ville", "pays", "pente_optimale_deg", "ghi_annuel_kwh_m2", "irradiation_plan_kwh_m2_an",
             "productible_kwh_kwc_an", "production_100m2_kwh_an"]].round(0).to_string())
t = synth.loc["tunis"]
print(f"\nRapport SolarVision (Tunis, 100 m²) : {100 * G_RAPPORT * ETA * PR:,.0f} kWh/an avec G = {G_RAPPORT}")
print(f"PVGIS (Tunis, 100 m² = 20 kWc) : {t['production_100m2_kwh_an']:,.0f} kWh/an ; irradiation horizontale "
      f"{t['ghi_annuel_kwh_m2']:,.0f} kWh/m²/an, sur le plan optimal ({t['pente_optimale_deg']:.0f}°) "
      f"{t['irradiation_plan_kwh_m2_an']:,.0f} kWh/m²/an")
print(f"Surface nécessaire pour 45 000 kWh/an : rapport {45000 / (G_RAPPORT * ETA * PR):.0f} m² ; "
      f"PVGIS {45000 / (t['productible_kwh_kwc_an'] * ETA):.0f} m²")

# %% [markdown]
# **Lecture.**
# - **Jeux de données :** 14 fichiers, dont les 6 demandés (photovoltaïque et éclairement pour chacun des trois pays, 3 villes par pays). Le panel complet compte 62 451 lignes et 58 variables par ville et par jour ; hors variables retardées (7 premiers jours), aucune valeur ne manque.
# - **Liens du rapport :** sur 21 liens distincts, un seul (PVGIS) donne des séries temporelles. Les 14 articles ont fourni leur résumé au corpus de l'assistant ; les 5 jeux d'images ont seulement été décrits, car ce ne sont pas des séries temporelles.
# - **Le chiffre du rapport SolarVision était juste, mais pour le plan horizontal.** PVGIS donne 1 815 kWh/m²/an d'irradiation horizontale à Tunis, très proche des 1 800 supposés. Mais des modules inclinés à la pente optimale (33°) reçoivent 2 045 kWh/m²/an (+13 %), et les pertes calculées par PVGIS (22,5 %, soit un ratio de performance de 0,78) sont proches du 0,8 supposé. D'où 31 694 kWh/an pour 100 m² au lieu de 28 800 (+10 %), et 142 m² au lieu de 156 m² pour couvrir 45 000 kWh/an.
# - **Hiérarchie des sites :** Tozeur (1 785 kWh/kWc/an), Sfax (1 700) et Séville (1 672) en tête, Paris (1 131) en dernier. Tunis (1 585), ville côtière plus nuageuse en hiver que le sud tunisien, se situe au niveau de Madrid (1 620) et de Marseille (1 627).

# %%
# Découpage chronologique 90 % / 10 % (jamais aléatoire : on n'apprend pas sur le futur).
# Horizon de prévision H = 7 jours, dans la fourchette de 5 à 10 pas demandée.
n = len(df)
n_train = int(n * 0.9)
H = 7
train, test = df.iloc[:n_train], df.iloc[n_train:]
y_all = df[CIBLE].to_numpy()
y_train = y_all[:n_train]
print(f"Apprentissage : {len(train)} jours, {train.index[0].date()} -> {train.index[-1].date()}")
print(f"Test          : {len(test)} jours, {test.index[0].date()} -> {test.index[-1].date()}")

# %% [markdown]
# ## 2. Analyse exploratoire
# ### 2.1 Visualisation

# %%
# Vue d'ensemble de la série multidimensionnelle de Tunis : production, éclairement horizontal,
# nébulosité et température n'ont pas la même échelle, on les trace sur des axes séparés.
fig, ax = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
for a, (col, lib, c) in zip(ax, [(CIBLE, "Production (kWh/kWc)", "#1f3a5f"),
                                 ("ghi_kwh_m2", "Éclairement horizontal (kWh/m²)", "#e0a030"),
                                 ("nebulosite_pct", "Nébulosité (%)", "#6b7b8c"),
                                 ("t2m_moy_c", "Température (°C)", "#d03b3b")]):
    a.plot(df.index, df[col], lw=0.4, color=c)
    a.plot(df.index, df[col].rolling(365, center=True).mean(), color="k", lw=1.5, label="moyenne mobile 365 j")
    a.set_ylabel(lib, fontsize=9)
    a.axvline(test.index[0], color="k", ls="--", lw=1)
ax[0].legend(loc="upper right", fontsize=8)
ax[0].text(test.index[0], ax[0].get_ylim()[1] * 0.95, " test", fontsize=8)
fig.suptitle("Tunis, 2005-2023 : production d'1 kWc, éclairement, nébulosité et température (journalier)")
montrer(fig, "01_series_tunis")

COLS_STAT = [CIBLE, "ghi_kwh_m2", "nebulosite_pct", "t2m_moy_c", "precipitation_mm", "aerosols_aod"]
stats_desc = pd.DataFrame({"moyenne": train[COLS_STAT].mean(), "écart-type": train[COLS_STAT].std(),
                           "variance": train[COLS_STAT].var(), "min": train[COLS_STAT].min(),
                           "max": train[COLS_STAT].max(), "skewness": train[COLS_STAT].skew(),
                           "kurtosis (excès)": train[COLS_STAT].kurt()}).round(3)
stats_desc.to_csv(RES / "py_stats_descriptives.csv")
print(stats_desc.to_string())
mois_moy = train.groupby(train.index.month)[CIBLE].agg(["mean", "std"])
print("\nProduction moyenne par mois (kWh/kWc/j) :", mois_moy["mean"].round(2).to_dict())
print("Écart-type par mois                     :", mois_moy["std"].round(2).to_dict())
print("Production annuelle (kWh/kWc) :", df.groupby(df.index.year)[CIBLE].sum().round(0).astype(int).to_dict())

# %%
# Comparaison des 9 villes : profil saisonnier moyen et production annuelle. Les échelles sont
# directement comparables puisque toutes les séries sont exprimées pour 1 kWc.
fig, ax = plt.subplots(1, 2, figsize=(14, 4.6))
styles = ["-", "--", ":"]
for pays, couleur in COULEUR_PAYS.items():
    sites_p = [s for s, v in SITES.items() if v["pays"] == pays]
    for st, s in zip(styles, sites_p):
        d = panel[panel["site"] == s]
        prof = d.groupby(d["date"].dt.month)[CIBLE].mean()
        ax[0].plot(prof.index, prof.to_numpy(), ls=st, color=couleur, marker="o", ms=3, label=SITES[s]["ville"])
ax[0].set_xticks(range(1, 13)); ax[0].set_xlabel("mois"); ax[0].set_ylabel("kWh/kWc/jour")
ax[0].set_title("Profil saisonnier moyen (2005-2023)"); ax[0].legend(fontsize=7, ncol=3)
annuel = panel.groupby(["site", panel["date"].dt.year])[CIBLE].sum().groupby("site").agg(["mean", "std"])
annuel = annuel.loc[list(SITES)]
ax[1].bar([SITES[s]["ville"] for s in annuel.index], annuel["mean"], yerr=annuel["std"], capsize=3,
          color=[COULEUR_PAYS[SITES[s]["pays"]] for s in annuel.index])
ax[1].set_ylabel("kWh/kWc/an"); ax[1].set_title("Production annuelle moyenne (barre : écart-type interannuel)")
ax[1].tick_params(axis="x", labelrotation=30)
montrer(fig, "02_comparaison_villes")
print("Production annuelle moyenne (kWh/kWc) :", annuel["mean"].round(0).astype(int).to_dict())
print("Écart-type interannuel (kWh/kWc)      :", annuel["std"].round(0).astype(int).to_dict())

# %%
# Relation production / nébulosité : la forme du nuage de points guide le choix des variables
# exogènes (linéaires ou non) avant tout modèle multivarié.
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
saison = train.index.month.map(lambda m: "été (juin-août)" if m in (6, 7, 8) else
                               "hiver (déc.-févr.)" if m in (12, 1, 2) else "intersaison")
for s_, c in (("hiver (déc.-févr.)", "#2a78d6"), ("intersaison", "#999999"), ("été (juin-août)", "#e0a030")):
    m = saison == s_
    ax[0].scatter(train.loc[m, "nebulosite_pct"], train.loc[m, CIBLE], s=4, alpha=0.4, color=c, label=s_)
ax[0].set_xlabel("Nébulosité ERA5 (%)"); ax[0].set_ylabel("Production (kWh/kWc)"); ax[0].legend(fontsize=8)
ax[0].set_title("Production et nébulosité : effet plus fort l'hiver ?")
ax[1].scatter(train["indice_clarte"], train[CIBLE] / train["irr_extraterrestre_kwh_m2"], s=4, alpha=0.4, color="#1f3a5f")
ax[1].set_xlabel("Indice de clarté NASA POWER"); ax[1].set_ylabel("Production / irradiation extraterrestre")
ax[1].set_title("Une fois la saison retirée, relation presque linéaire")
montrer(fig, "03_production_nebulosite")
print("Corrélation production / nébulosité :", round(train[CIBLE].corr(train["nebulosite_pct"]), 3),
      "| par saison :", {s_: round(train.loc[saison == s_, CIBLE].corr(train.loc[saison == s_, "nebulosite_pct"]), 3)
                         for s_ in ("hiver (déc.-févr.)", "intersaison", "été (juin-août)")})
print("Corrélation production normalisée / indice de clarté :",
      round((train[CIBLE] / train["irr_extraterrestre_kwh_m2"]).corr(train["indice_clarte"]), 3))

# %% [markdown]
# **Lecture.**
# - **Saisonnalité annuelle marquée mais modérée :** la production moyenne va de 3,06 kWh/kWc par jour en décembre à 5,43 en juillet, un rapport de 1,8 (environ 3 à Paris, figure 02).
# - **Une variance qui baisse quand le niveau monte :** l'écart-type journalier vaut 1,25 à 1,53 kWh/kWc de décembre à avril, et seulement 0,41 en juillet. L'été tunisien est presque toujours clair ; l'hiver et le printemps alternent journées claires et perturbations.
# - **Pas de tendance :** la moyenne mobile sur 365 jours reste entre 4,1 et 4,5 kWh/kWc ; la production annuelle varie de 1 508 (2005) à 1 635 kWh/kWc (2017), avec un écart-type d'une année à l'autre de 37 kWh/kWc (2,3 %). La température, elle, monte (section 2.6).
# - **Distribution asymétrique à gauche (skewness -0,82) :** la production est bornée par le ciel clair ; les mauvaises journées sont rares mais très basses (2,1 % des jours sous 1 kWh/kWc, minimum 0,21).
# - **Neuf villes, deux régimes :** le gradient nord-sud est surtout hivernal. En décembre, Paris produit 1,35 kWh/kWc par jour contre environ 4,1 à Tozeur ; en juillet, les neuf villes sont entre 4,2 et 5,5. La production varie davantage d'une année à l'autre au nord (écart-type de 55 kWh/kWc à Lyon, 49 à Paris) qu'au sud (24 à Sfax).
# - **Lien avec la nébulosité :** corrélation de -0,69, de -0,61 en hiver à -0,67 en été. Le nuage de points est large : à nébulosité égale, la production varie beaucoup (nuages fins ou épais, moment de la journée). Divisée par le rayonnement extraterrestre, la production suit l'indice de clarté de NASA POWER (r = 0,57) : la relation avec la transparence de l'atmosphère est presque linéaire.

# %% [markdown]
# ### 2.2 Choix de la transformation

# %%
# Faut-il passer au logarithme ? Un log se justifie si la dispersion croît avec le niveau. On
# compare, mois par mois, le niveau moyen et l'écart-type de la production.
mm = train[CIBLE].resample("MS").agg(["mean", "std"])
pente, ord0, r_lin, p_lin, _ = stats.linregress(mm["mean"], mm["std"])
print(f"Écart-type mensuel ~ moyenne mensuelle : pente = {pente:.3f}, r = {r_lin:.2f}, p = {p_lin:.1e}")
print("Part des jours sous 1 kWh/kWc :", round(100 * (train[CIBLE] < 1).mean(), 2), "% ; minimum :",
      round(train[CIBLE].min(), 3))
log_skew = np.log(train[CIBLE].clip(lower=0.05)).skew()
print(f"Asymétrie : série brute {train[CIBLE].skew():.2f} ; après log {log_skew:.2f}")

# %% [markdown]
# **Lecture.** L'écart-type mensuel diminue quand le niveau augmente (pente -0,24 ; r = -0,57 ; p = 4e-19) : c'est l'inverse de la situation qui justifie un logarithme ou une transformation de Box-Cox. Le logarithme aggraverait d'ailleurs l'asymétrie (de -0,82 à -1,99) en étirant les mauvaises journées. **La série est donc modélisée en niveau**, en kWh/kWc, unité directement interprétable. L'hétéroscédasticité, qui suit les saisons, est traitée par un modèle de variance conditionnelle en section 3.3 plutôt que par une transformation.

# %% [markdown]
# ### 2.3 ACF et PACF

# %%
# Saisonnalité annuelle déterministe : on la représente par des termes de Fourier (K harmoniques de
# la période 365,25 jours). La série « désaisonnalisée » est le résidu de cette régression, estimée
# sur l'apprentissage seulement.
t_jour = np.arange(n)


def fourier(K, t=t_jour):
    return np.column_stack([f(2 * np.pi * k * t / 365.25) for k in range(1, K + 1) for f in (np.sin, np.cos)])


X4 = sm.add_constant(fourier(4))
beta4 = np.linalg.lstsq(X4[:n_train], y_train, rcond=None)[0]
anomalie = pd.Series(y_all - X4 @ beta4, index=df.index)
s = train[CIBLE]
variantes = {"série brute": s, "différence d'ordre 1": s.diff().dropna(),
             "désaisonnalisée (Fourier K = 4)": anomalie.iloc[:n_train]}
fig, ax = plt.subplots(3, 2, figsize=(12, 8))
for i, (nom, v) in enumerate(variantes.items()):
    plot_acf(v, lags=40, ax=ax[i, 0], title=f"ACF - {nom}", zero=False)
    plot_pacf(v, lags=40, ax=ax[i, 1], title=f"PACF - {nom}", zero=False, method="ywm")
montrer(fig, "04_acf_pacf")
fig, ax = plt.subplots(figsize=(12, 3))
plot_acf(s, lags=800, ax=ax, title="ACF de la série brute sur 800 retards : cycle annuel", zero=False, marker=None)
montrer(fig, "05_acf_long")
acf_v = sm.tsa.acf(s, nlags=400)
print("ACF série brute, retards 1, 2, 7, 30, 182, 365 :", np.round(acf_v[[1, 2, 7, 30, 182, 365]], 3))
acf_a = sm.tsa.acf(anomalie.iloc[:n_train], nlags=30)
pacf_a = sm.tsa.pacf(anomalie.iloc[:n_train], nlags=30, method="ywm")
print("ACF  désaisonnalisée, retards 1 à 7 :", np.round(acf_a[1:8], 3))
print("PACF désaisonnalisée, retards 1 à 7 :", np.round(pacf_a[1:8], 3))
acf_d = sm.tsa.acf(s.diff().dropna(), nlags=10)
print("ACF différence d'ordre 1, retards 1 à 5 :", np.round(acf_d[1:6], 3))
print("Part de variance expliquée par les termes de Fourier (K = 4) :",
      round(1 - anomalie.iloc[:n_train].var() / s.var(), 3))

# %% [markdown]
# **Lecture.**
# - **Série brute :** ACF de 0,51 au retard 1, 0,39 au retard 2, encore 0,28 au retard 30, puis -0,31 à 182 jours et +0,33 à 365 jours. Cette persistance apparente vient du cycle annuel (figure 05), pas de la météo.
# - **Différence d'ordre 1 :** ACF de -0,37 au retard 1, signature d'une sur-différenciation : la série n'a pas de racine unitaire, il ne faut pas la différencier.
# - **Série désaisonnalisée** (termes de Fourier, 34 % de la variance) : ACF de 0,26 au retard 1, puis 0,07, 0,03 et des valeurs négligeables ; PACF de 0,26 au retard 1, puis nulle. C'est la signature d'un **AR(1)** : la météo d'un jour renseigne faiblement sur celle du lendemain, et presque plus sur celle du surlendemain.
# - **Ordres candidats :** d = 0 ; p de 1 à 3 et q de 0 à 2, comparés en section 3.1 ; cycle annuel représenté par K = 2 à 4 harmoniques. Il n'y a pas de saisonnalité hebdomadaire : la météo ignore le calendrier.

# %% [markdown]
# ### 2.4 Décomposition

# %%
# Décomposition STL (période 365 jours, version robuste aux valeurs extrêmes) : elle sépare la
# tendance lente, le cycle annuel et le résidu météorologique de court terme.
stl = STL(train[CIBLE], period=365, robust=True).fit()
fig, ax = plt.subplots(4, 1, figsize=(12, 8.5), sharex=True)
ax[0].plot(train[CIBLE], lw=0.4); ax[0].set_ylabel("production")
ax[1].plot(stl.trend, color="#e0a030"); ax[1].set_ylabel("tendance")
ax[2].plot(stl.seasonal, lw=0.5, color="#1a8a8a"); ax[2].set_ylabel("saison 365 j")
ax[3].plot(stl.resid, lw=0.4, color="grey"); ax[3].set_ylabel("résidu")
fig.suptitle("Décomposition STL robuste de la production journalière de Tunis (apprentissage)")
montrer(fig, "06_decomposition_stl")
var_tot = train[CIBLE].var()
print("Part de variance : tendance", round(stl.trend.var() / var_tot, 3), "| saison",
      round(stl.seasonal.var() / var_tot, 3), "| résidu", round(stl.resid.var() / var_tot, 3))
print("Tendance : minimum", round(stl.trend.min(), 3), "le", stl.trend.idxmin().date(), "| maximum",
      round(stl.trend.max(), 3), "le", stl.trend.idxmax().date())
pente_tend = np.polyfit(np.arange(len(stl.trend)) / 365.25, stl.trend.to_numpy(), 1)[0]
print(f"Pente linéaire de la tendance : {pente_tend * 1000:.1f} Wh/kWc/jour par an")
res_stl = stl.resid
print("Écart-type du résidu par mois :", res_stl.groupby(res_stl.index.month).std().round(2).to_dict())
print("Asymétrie du résidu :", round(res_stl.skew(), 2), "| kurtosis :", round(res_stl.kurt(), 2))

# %% [markdown]
# **Lecture de chaque composante.**
# - **Saison annuelle :** 65 % de la variance, d'environ 3,1 à 5,4 kWh/kWc, très régulière d'une année à l'autre.
# - **Tendance :** moins de 1 % de la variance. Elle part de 3,90 kWh/kWc (effet de bord du lissage en 2005), culmine à 4,67 en 2017 et croît de 9,5 Wh/kWc par jour et par an, soit environ +3,5 kWh/kWc par an (+0,2 %). C'est faible, et cela peut traduire aussi bien une atmosphère moins chargée en aérosols qu'une dérive de la série satellitaire : on ne l'interprète pas sans mesure au sol.
# - **Résidu :** 60 % de la variance (les parts ne s'additionnent pas exactement, les composantes étant corrélées). C'est la météo de court terme. Son écart-type va de 1,40 kWh/kWc en mars à 0,37 en juillet, et il est asymétrique (-0,90) : les jours de perturbation tirent vers le bas.

# %% [markdown]
# ### 2.5 Valeurs aberrantes

# %%
# Deux familles de valeurs aberrantes, à ne pas confondre.
# 1. Erreurs de données : jours où la base satellitaire a des trous, que PVGIS enregistre comme des
#    zéros. La collecte les repère par deux contrôles de cohérence (hauteur du soleil incompatible avec
#    l'astronomie, irradiation PVGIS très inférieure à celle de deux sources indépendantes) et les
#    corrige (`jour_impute_pvgis`). On montre ici la valeur brute et la valeur corrigée.
imputes = df.index[df["jour_impute_pvgis"] == 1]
f_brut = DATA / "brut" / "pvgis" / f"{SITE}_horaire.parquet"
if not f_brut.exists():                 # cache brut absent (archive allégée) : on retélécharge cette seule série
    from collecte_donnees import pvgis_horaire, pvgis_synthese
    f_brut.parent.mkdir(parents=True, exist_ok=True)
    pvgis_horaire(SITE, pvgis_synthese(SITE)["inputs"]["mounting_system"]["fixed"]["slope"]["value"])
brut_h = pd.read_parquet(f_brut)
brut_j = brut_h["P"].groupby(brut_h.index.floor("D")).sum() / 1000
tab_imp = pd.DataFrame({"PVGIS brut": brut_j.reindex(imputes), "corrigé": df.loc[imputes, CIBLE],
                        "GHI NASA": df.loc[imputes, "ghi_nasa_kwh_m2"], "GHI ERA5": df.loc[imputes, "ghi_era5_kwh_m2"],
                        "nébulosité (%)": df.loc[imputes, "nebulosite_pct"]})
print(f"Erreurs de données (trous de la base SARAH3) : {len(imputes)} jours sur {n} à Tunis\n", tab_imp.round(2).to_string())

# 2. Valeurs extrêmes mais vraies : journées très couvertes ou pluvieuses. La dispersion du résidu STL
#    varie du simple au triple entre l'été et l'hiver : une règle de l'IQR globale signalerait presque
#    tous les jours d'hiver. On utilise donc un boxplot glissant (quartiles sur 61 jours centrés).
FEN = 61
q1 = res_stl.rolling(FEN, center=True, min_periods=30).quantile(0.25)
q3 = res_stl.rolling(FEN, center=True, min_periods=30).quantile(0.75)
iqr = q3 - q1
q1g, q3g = res_stl.quantile(0.25), res_stl.quantile(0.75)
ab_global = (res_stl < q1g - 1.5 * (q3g - q1g)) | (res_stl > q3g + 1.5 * (q3g - q1g))
ab15 = (res_stl < q1 - 1.5 * iqr) | (res_stl > q3 + 1.5 * iqr)
ab3 = (res_stl < q1 - 3 * iqr) | (res_stl > q3 + 3 * iqr)
pluie = train["precipitation_mm"] >= 5
couvert = train["nebulosite_pct"] >= 80
poussiere = train["aerosols_aod"] >= 0.8
print(f"\nRègle de l'IQR globale : {int(ab_global.sum())} jours ({100 * ab_global.mean():.1f} %), dont "
      f"{int((ab_global & np.isin(train.index.month, [11, 12, 1, 2, 3])).sum())} de novembre à mars")
print(f"Boxplot glissant, seuil 1,5 IQR : {int(ab15.sum())} jours ({100 * ab15.mean():.1f} %) ; "
      f"{int((ab15 & (res_stl < 0)).sum())} bas, {int((ab15 & (res_stl > 0)).sum())} hauts")
bas = ab15 & (res_stl < 0)
print(f"  parmi les jours bas : pluie >= 5 mm {int((bas & pluie).sum())}, nébulosité >= 80 % {int((bas & couvert).sum())}, "
      f"aérosols >= 0,8 {int((bas & poussiere).sum())}, au moins l'un des trois {int((bas & (pluie | couvert | poussiere)).sum())}")
print(f"Boxplot glissant, seuil 3 IQR : {int(ab3.sum())} jours")
print("Jours corrigés à la collecte parmi les jours signalés :", int(train.loc[ab15, "jour_impute_pvgis"].sum()))
tab_ab = train.loc[ab15, [CIBLE, "nebulosite_pct", "precipitation_mm", "aerosols_aod"]].assign(residu=res_stl[ab15])
print("Les 8 jours les plus bas :\n", tab_ab.sort_values("residu").head(8).round(2).to_string())
print("Mois des jours signalés :", tab_ab.index.month.value_counts().sort_index().to_dict())
fig, ax = plt.subplots(figsize=(12, 3.5))
ax.plot(res_stl, lw=0.4, color="grey")
ax.fill_between(res_stl.index, q1 - 1.5 * iqr, q3 + 1.5 * iqr, color="#1a8a8a", alpha=0.2, label="boxplot glissant (61 j) : bornes 1,5 IQR")
expl = ab15 & (pluie | couvert | poussiere)
ax.scatter(res_stl.index[expl], res_stl[expl], color="#2a78d6", s=10, label="pluie, ciel couvert ou poussières", zorder=3)
ax.scatter(res_stl.index[ab15 & ~expl], res_stl[ab15 & ~expl], color="red", s=10, label="autre", zorder=3)
ax.set_title("Résidu STL et jours signalés par le boxplot glissant"); ax.legend(fontsize=8, ncol=3)
montrer(fig, "07_aberrants")

# %% [markdown]
# **Lecture et traitement.**
# - **Erreurs de données, corrigées :** 13 jours à Tunis où PVGIS donnait 0 à 1,5 kWh/kWc alors que NASA POWER et ERA5 voyaient une journée ordinaire (2,2 à 7,2 kWh/m²) sous une nébulosité modérée. Ce sont des trous de la base satellitaire SARAH3 (dix journées entièrement à zéro, trois en partie). Les garder aurait créé de faux records de volatilité et biaisé tous les modèles. Ils sont imputés à la collecte (énergie NASA du jour multipliée par le rapport PVGIS/NASA des 31 jours voisins) et signalés par `jour_impute_pvgis`.
# - **Règle de l'IQR globale, inadaptée :** elle signale 1 093 jours (17,5 %), dont 616 de novembre à mars, simplement parce que la dispersion est plus forte en hiver.
# - **Boxplot glissant (61 jours) :** 803 jours signalés (12,9 %), 595 bas et 208 hauts ; 323 au seuil strict de 3 IQR. La moitié des jours bas (298) s'expliquent par une pluie d'au moins 5 mm (174 jours), un ciel couvert à plus de 80 % (195) ou des poussières (55 jours avec une épaisseur optique d'au moins 0,8). Les 8 jours les plus bas cumulent ciel couvert et pluie ou poussières (le 2 avril 2016 : épaisseur optique de 1,30). L'autre moitié tombe surtout en été, où la dispersion locale est si faible qu'une baisse modeste est déjà signalée, ou correspond à des nuages mal situés par la réanalyse.
# - **Décision :** ces valeurs extrêmes sont vraies et conservées, sans variable indicatrice : imprévisibles ex ante, elles doivent élargir les intervalles. Les modèles ex post les expliquent par la météo, et leur concentration en saison humide est modélisée par la variance conditionnelle (section 3.3).

# %% [markdown]
# ### 2.6 Stationnarité

# %%
# ADF (H0 : racine unitaire) et KPSS (H0 : stationnarité) ont des hypothèses nulles opposées :
# on ne conclut que lorsque les deux tests racontent la même histoire.
def tests_stationnarite(v, nom, regression="c"):
    v = pd.Series(v).dropna()
    adf_stat, adf_p, adf_lag, *_ = adfuller(v, autolag="AIC", regression=regression)
    kpss_stat, kpss_p, _, _ = kpss(v, regression=regression, nlags="auto")
    if adf_p < 0.05 and kpss_p >= 0.05:
        concl = "stationnaire"
    elif adf_p >= 0.05 and kpss_p < 0.05:
        concl = "non stationnaire (racine unitaire)"
    elif adf_p < 0.05 and kpss_p < 0.05:
        concl = "désaccord (saisonnalité ou rupture ?)"
    else:
        concl = "non concluant"
    return {"série": nom, "ADF stat": round(adf_stat, 3), "ADF p": round(adf_p, 4), "ADF retards": adf_lag,
            "KPSS stat": round(kpss_stat, 3), "KPSS p": round(kpss_p, 4), "conclusion à 5 %": concl}


lignes = []
for col, lib in ((CIBLE, "production"), ("nebulosite_pct", "nébulosité"), ("t2m_moy_c", "température")):
    v = train[col]
    lignes.append(tests_stationnarite(v, f"{lib}"))
    lignes.append(tests_stationnarite(v.diff(), f"{lib} - diff. ordre 1"))
    Xf = sm.add_constant(fourier(4))[:n_train]
    lignes.append(tests_stationnarite(v.to_numpy() - Xf @ np.linalg.lstsq(Xf, v.to_numpy(), rcond=None)[0],
                                      f"{lib} - désaisonnalisée (Fourier)"))
lignes.append(tests_stationnarite(anomalie.iloc[:n_train], "production désaisonnalisée, avec tendance", "ct"))
Xf = sm.add_constant(fourier(4))[:n_train]
t_des = train["t2m_moy_c"].to_numpy() - Xf @ np.linalg.lstsq(Xf, train["t2m_moy_c"].to_numpy(), rcond=None)[0]
lignes.append(tests_stationnarite(t_des, "température désaisonnalisée, avec tendance", "ct"))
pente_t = np.polyfit(np.arange(n_train) / 365.25, t_des, 1)[0]
print(f"Tendance linéaire de la température désaisonnalisée : {10 * pente_t:+.2f} °C par décennie")
tab_stat = pd.DataFrame(lignes).set_index("série")
tab_stat.to_csv(RES / "py_stationnarite.csv")
print(tab_stat.to_string())
print("\nNote : la p-value du KPSS est bornée entre 0,01 et 0,10 par les tables de statsmodels.")

# %% [markdown]
# **Lecture.**
# - **Production, nébulosité et température en niveau :** l'ADF rejette la racine unitaire (p < 0,001) et le KPSS ne rejette pas la stationnarité (p > 0,10). Les deux tests s'accordent : les séries sont stationnaires, le cycle annuel les ramenant chaque année au même niveau.
# - **Différence d'ordre 1 :** stationnaire elle aussi, mais sur-différenciée (ACF de -0,37 au retard 1, section 2.3).
# - **Température désaisonnalisée :** le KPSS rejette la stationnarité autour d'une constante (statistique 1,93) mais pas autour d'une tendance (0,041). La température de Tunis est stationnaire autour d'une tendance de **+0,59 °C par décennie** sur 2005-2022, ordre de grandeur compatible avec le réchauffement observé autour de la Méditerranée. La production désaisonnalisée est stationnaire avec ou sans tendance.
# - **Ordre de différenciation retenu : d = 0 et D = 0.** Le cycle annuel est déterministe et représenté par des termes de Fourier. En R, `tseries::adf.test` (tendance incluse, nombre de retards fixé) aboutit à la même conclusion.

# %% [markdown]
# ### 2.7 Choix des variables explicatives (plus de 50 candidates)
#
# Les jeux de données contiennent plus de 50 variables. On les classe selon leur pouvoir explicatif
# avec trois critères complémentaires, calculés sur l'apprentissage seulement :
# - la corrélation de rang de Spearman (lien monotone, insensible aux valeurs extrêmes) ;
# - l'information mutuelle (lien quelconque, y compris non linéaire) ;
# - l'importance par permutation d'un modèle de gradient boosting, mesurée sur les 15 % les plus
#   récents de l'apprentissage (apport propre de la variable une fois les autres connues).
#
# Deux usages sont distingués, car ils n'ont pas le droit aux mêmes informations :
# - **prévision ex ante** de la production du lendemain : seulement ce qui est connu la veille
#   (retards, météo observée de la veille, astronomie du lendemain) ;
# - **estimation ex post** de la production du jour à partir de la météo du jour (cas d'une prévision
#   météo parfaite). Les variables d'éclairement issues de PVGIS (dont la production est calculée) en sont
#   exclues : elles rendraient le problème trivial.

# %%
# Préparation des deux tableaux de candidates. Les variables météo « de la veille » sont décalées
# d'un jour pour ne contenir que de l'information disponible au moment de la prévision.
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_selection import mutual_info_regression
from sklearn.inspection import permutation_importance

METEO = ["nebulosite_pct", "nebulosite_nasa_pct", "ensoleillement_h", "precipitation_mm", "humidite_pct",
         "point_rosee_c", "pression_hpa", "rafales_max_kmh", "et0_mm", "t2m_moy_c", "t2m_max_c", "t2m_min_c",
         "amplitude_thermique_c", "vent_moy_ms", "aerosols_aod", "indice_uv", "albedo", "ghi_era5_kwh_m2",
         "ghi_nasa_kwh_m2", "indice_clarte", "par_kwh_m2", "ghi_ciel_clair_kwh_m2"]
ASTRO = ["irr_extraterrestre_kwh_m2", "duree_jour_astro_h", "hauteur_soleil_midi_deg", "jds_sin", "jds_cos"]
ex_ante = pd.DataFrame({f"{c}_veille": df[c].shift(1) for c in METEO}, index=df.index)
for c in ASTRO:
    ex_ante[c] = df[c]
for c in ("pv_veille", "pv_j7", "pv_moy7_passe", "pv_ecart_type7_passe", "ghi_veille", "ghi_moy7_passe"):
    ex_ante[c] = df[c]
# Exclusion des sources de rayonnement pour l'ex post : ce serait presque la cible elle-même.
EXPOST_COLS = [c for c in METEO if c not in ("ghi_era5_kwh_m2", "ghi_nasa_kwh_m2", "indice_clarte", "par_kwh_m2",
                                              "ensoleillement_h", "et0_mm", "indice_uv")] + ASTRO
ex_post = df[EXPOST_COLS].copy()
ex_post["neb_x_potentiel"] = df["nebulosite_pct"] / 100 * df["irr_extraterrestre_kwh_m2"]   # effet multiplicatif
print("Candidates ex ante :", ex_ante.shape[1], "| candidates ex post :", ex_post.shape[1])


def classer_variables(X, y, nom):
    """Spearman, information mutuelle et importance par permutation, sur l'apprentissage seulement."""
    ok = X.iloc[:n_train].notna().all(axis=1) & y.iloc[:n_train].notna()
    Xa, ya = X.iloc[:n_train][ok], y.iloc[:n_train][ok]
    coupe_ = int(len(Xa) * 0.85)
    spear = Xa.apply(lambda c: stats.spearmanr(c, ya)[0])
    mi = pd.Series(mutual_info_regression(Xa, ya, random_state=SEED), index=X.columns)
    gb = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=SEED).fit(Xa.iloc[:coupe_], ya.iloc[:coupe_])
    perm = permutation_importance(gb, Xa.iloc[coupe_:], ya.iloc[coupe_:], n_repeats=5, random_state=SEED,
                                  scoring="neg_mean_squared_error")
    r2 = gb.score(Xa.iloc[coupe_:], ya.iloc[coupe_:])
    tab_ = pd.DataFrame({"|Spearman|": spear.abs(), "info. mutuelle": mi,
                         "permutation (hausse du MSE)": perm.importances_mean}, index=X.columns)
    tab_["rang moyen"] = tab_.rank(ascending=False).mean(axis=1)
    tab_ = tab_.sort_values("rang moyen")
    print(f"{nom} : R² du gradient boosting sur la validation = {r2:.3f}")
    return tab_


imp_ante = classer_variables(ex_ante, df[CIBLE], "Ex ante (production du lendemain)")
imp_post = classer_variables(ex_post, df[CIBLE], "Ex post (production du jour, météo du jour connue)")
imp_ante.to_csv(RES / "py_importance_variables_ex_ante.csv")
imp_post.to_csv(RES / "py_importance_variables_ex_post.csv")
print("\nEx ante, 12 premières :\n", imp_ante.head(12).round(3).to_string())
print("\nEx post, 12 premières :\n", imp_post.head(12).round(3).to_string())

# %%
# Redondance : facteur d'inflation de la variance (VIF) des variables retenues. Un VIF élevé
# (> 10) signale une variable presque combinaison linéaire des autres, inutile dans un modèle linéaire.
from statsmodels.stats.outliers_influence import variance_inflation_factor

SEL_POST = ["nebulosite_pct", "precipitation_mm", "humidite_pct", "amplitude_thermique_c", "aerosols_aod",
            "nebulosite_nasa_pct", "pression_hpa"]
Xv_ = sm.add_constant(pd.concat([ex_post[SEL_POST].iloc[:n_train],
                                 pd.DataFrame(fourier(2)[:n_train], index=df.index[:n_train])], axis=1).dropna())
vif = pd.Series([variance_inflation_factor(Xv_.to_numpy(), i) for i in range(1, len(SEL_POST) + 1)], index=SEL_POST)
print("VIF des variables météo retenues (avec saisonnalité) :", vif.round(2).to_dict())
fig, ax = plt.subplots(1, 2, figsize=(13, 5))
for a, (tab_, titre) in zip(ax, ((imp_ante, "Ex ante : production du lendemain"),
                                 (imp_post, "Ex post : production du jour"))):
    top = tab_.head(15).sort_values("permutation (hausse du MSE)")
    a.barh(top.index, top["permutation (hausse du MSE)"], color="#2a78d6", height=0.6)
    a.set_title(f"{titre}\n(15 premières selon le rang moyen des trois critères)", fontsize=10)
    a.set_xlabel("importance par permutation (hausse du MSE)")
    a.tick_params(axis="y", labelsize=8)
montrer(fig, "08_importance_variables")

# %% [markdown]
# **Lecture et choix.**
# - **Ex ante, la production du lendemain est peu prévisible :** avec 33 variables, le gradient boosting n'explique que 40 % de la variance sur la validation. Les variables utiles sont le rayonnement de la veille (ensoleillement, irradiation ERA5 ou NASA, rayonnement photosynthétique), la position dans l'année (rayonnement extraterrestre, cosinus du jour) et surtout la nébulosité satellite de la veille (plus forte importance par permutation : 0,12).
# - **Redondance :** les trois sources d'irradiation ont chacune une corrélation de Spearman d'environ 0,66 avec la cible, mais une importance par permutation presque nulle : elles se remplacent l'une l'autre. Plus de variables n'apporte pas plus d'information.
# - **Ex post, la météo du jour explique 79 % de la variance.** La nébulosité satellite de NASA domine (importance 0,92), devant le potentiel solaire du jour (rayonnement extraterrestre et par ciel clair), l'amplitude thermique (un ciel clair donne une forte amplitude), l'humidité et la pluie.
# - **Multicolinéarité :** VIF de 5,4 et 6,0 pour les deux nébulosités, inférieurs à 2 pour les autres variables retenues : acceptable (seuil usuel de 10).
# - **Choix.** Pour les modèles ex post (SARIMAX météo, réseaux ex post), on garde les variables qu'**une prévision météo fournit** : nébulosité ERA5, pluie, humidité, amplitude thermique et aérosols, plus l'interaction nébulosité x potentiel solaire. La nébulosité NASA est écartée bien qu'elle soit la plus informative : c'est une observation satellite, disponible après coup mais pas en prévision ; elle servirait à l'estimation en temps réel. Les variables de rayonnement sont exclues car quasi tautologiques. Pour les modèles ex ante (XGBoost, réseaux), on garde les retards, la météo de la veille et l'astronomie.

# %% [markdown]
# ## 3. Modélisation classique
# ### 3.1 ARIMA et SARIMA
#
# **Pourquoi pas un SARIMA journalier de période 365 ?** La seule saisonnalité de la production est
# annuelle (le soleil ne connaît pas les jours de la semaine). Un SARIMA de période 365 demanderait un
# état de plus de 365 dimensions, estimé sur 17 cycles seulement. On suit la recommandation classique
# (Hyndman et Athanasopoulos, *Forecasting: Principles and Practice*, chap. 10) : régression harmonique
# dynamique, c'est-à-dire un ARIMA sur la série dont le cycle annuel est représenté par des termes de
# Fourier. Le SARIMA saisonnier au sens strict (P, D, Q, s) est estimé en 3.1 bis sur la série mensuelle,
# où la période (s = 12) le permet.

# %%
# Recherche manuelle guidée par l'ACF/PACF de la série désaisonnalisée : d = 0 (section 2.6), ordres
# p et q faibles, nombre d'harmoniques K à choisir. Tous les modèles ont la même différenciation :
# leurs AIC/BIC sont comparables.
BRULAGE = 7       # premiers résidus écartés : l'initialisation du filtre les fausse
duree, nb_param = {}, {}


def ajuster_arima(order, K, X_extra=None, y=y_train):
    """ARIMA à erreurs corrélées sur termes de Fourier (+ variables exogènes éventuelles)."""
    X = fourier(K)[:len(y)] if K else None
    if X_extra is not None:
        X = X_extra[:len(y)] if X is None else np.column_stack([X, X_extra[:len(y)]])
    return ARIMA(y, exog=X, order=order, trend="c").fit(method="innovations_mle", gls=True)


t0 = time.time()
grille = []
for K in (2, 3, 4):
    for order in [(1, 0, 0), (2, 0, 0), (3, 0, 0), (1, 0, 1), (2, 0, 1), (1, 0, 2), (2, 0, 2)]:
        m = ajuster_arima(order, K)
        grille.append({"ordre": order, "K": K, "AIC": m.aic, "BIC": m.bic, "sigma": np.sqrt(m.params[-1])})
grille = pd.DataFrame(grille).sort_values("BIC").reset_index(drop=True)
grille.round(3).to_csv(RES / "py_grille_arima.csv", index=False)
print(grille.round(2).head(12).to_string())
ORDRE, K_F = grille.loc[0, "ordre"], int(grille.loc[0, "K"])
print(f"\nModèle manuel retenu (BIC minimal) : ARIMA{ORDRE} + Fourier K = {K_F}  ({time.time() - t0:.0f} s)")

# %%
# Confirmation par recherche automatique (pmdarima, équivalent Python d'auto.arima) : mêmes termes de
# Fourier en variables exogènes, ordres et différenciation choisis par l'algorithme.
import pmdarima as pm
from pmdarima.arima import ndiffs

print("Différenciation suggérée : d (ADF) =", ndiffs(y_train, test="adf"), "| d (KPSS) =",
      ndiffs(y_train, test="kpss"), "| d (PP) =", ndiffs(y_train, test="pp"))
t0 = time.time()
auto = pm.auto_arima(y_train, X=fourier(K_F)[:n_train], seasonal=False, stepwise=True,
                     information_criterion="aic", max_p=4, max_q=4, maxiter=50,
                     suppress_warnings=True, error_action="ignore")
ORDRE_AUTO = auto.order
print(f"pmdarima.auto_arima : ARIMA{ORDRE_AUTO} + Fourier K = {K_F}, constante = {auto.with_intercept}, "
      f"AIC = {auto.aic():.1f}  ({time.time() - t0:.0f} s)")

# %%
# Modèles comparés : ARIMA manuel, ARIMA automatique, et ARIMA manuel enrichi de la météo du jour
# (« ex post » : nébulosité, pluie, humidité, amplitude thermique, aérosols, plus le terme
# d'interaction nébulosité x potentiel solaire, car un ciel couvert coûte plus de kWh en été).
EXO_POST = ["nebulosite_pct", "neb_x_potentiel", "precipitation_mm", "humidite_pct", "amplitude_thermique_c",
            "aerosols_aod"]
X_meteo = ex_post[EXO_POST].ffill().bfill().to_numpy(float)
specs = {"ARIMA-Fourier manuel": (ORDRE, None), "ARIMA-Fourier auto": (ORDRE_AUTO, None),
         "SARIMAX météo": (ORDRE, X_meteo)}
modeles = {}
for nom, (o, Xe) in specs.items():
    t0 = time.time()
    m = auto.arima_res_ if nom == "ARIMA-Fourier auto" else ajuster_arima(o, K_F, Xe)
    modeles[nom] = (m, Xe)
    duree[nom], nb_param[nom] = time.time() - t0, len(m.params)
    print(f"{nom:22s} ARIMA{o} K={K_F}  AIC = {m.aic:9.1f}  BIC = {m.bic:9.1f}  sigma = {np.sqrt(m.params[-1]):.3f} kWh/kWc"
          f"  ({duree[nom]:.1f} s)")
m_man, m_auto, m_meteo = (modeles[k][0] for k in specs)
noms_m = ["const"] + [f"fourier_{i}" for i in range(2 * K_F)] + EXO_POST
coef = pd.DataFrame({"coef": m_meteo.params, "écart-type": m_meteo.bse, "p": m_meteo.pvalues},
                    index=noms_m + list(m_meteo.param_names[len(noms_m):])).round(5)
coef.to_csv(RES / "py_coef_sarimax_meteo.csv")
print("\nCoefficients du SARIMAX météo :\n", coef.to_string())
print("\nParamètres ARMA du modèle manuel :", {k: round(v, 4) for k, v in zip(m_man.param_names, m_man.params)
                                              if k.startswith(("ar.", "ma.", "sigma"))})

# %% [markdown]
# **Lecture.**
# - **Recherche manuelle :** le BIC retient ARIMA(1,0,0) avec K = 2 harmoniques (BIC de 18 977,6). L'AIC préférerait K = 4 (18 924,0), mais ce gain ne justifie pas quatre paramètres de plus.
# - **Recherche automatique :** avec les mêmes termes de Fourier, `pmdarima.auto_arima` retient exactement le même modèle, comme `auto.arima` en R. Les tests de différenciation (ADF, KPSS, Phillips-Perron) donnent tous d = 0. Les deux approches convergent, ce qui conforte l'identification par l'ACF et la PACF.
# - **Coefficients :** AR(1) = 0,263, cohérent avec l'ACF de la série désaisonnalisée (0,26) ; écart-type de l'erreur à un jour de 1,10 kWh/kWc.
# - **SARIMAX météo :** l'écart-type de l'erreur tombe à 0,767 kWh/kWc (-30 %) et l'AIC de 18 930 à 14 428. Chaque coefficient a un sens physique : -0,026 kWh/kWc par point de nébulosité (-0,26 pour 10 points), effet un peu atténué en été (interaction positive de 0,047, p = 0,008) ; -0,063 par mm de pluie ; **-0,96 par unité d'épaisseur optique des aérosols** (un épisode de poussières sahariennes à 1,0 coûte environ 1 kWh/kWc, soit 20 % d'une journée moyenne) ; +0,093 par degré d'amplitude thermique. L'humidité n'est pas significative (p = 0,09). Le coefficient AR(1) tombe à 0,11 : la persistance de la production venait surtout de celle de la météo.

# %%
# Diagnostic des résidus : un modèle n'est acceptable que si ses résidus ressemblent à un bruit
# blanc (Ljung-Box), idéalement gaussien (Jarque-Bera) et de variance constante (ARCH-LM).
def diagnostic(resid, nom, n_arma):
    r = np.asarray(resid)[BRULAGE:]
    lb = acorr_ljungbox(r, lags=[10, 30], model_df=n_arma)
    jb_stat, jb_p, skew, kurt = jarque_bera(r)
    lm, lm_p, _, _ = het_arch(r, nlags=7)
    rho = sm.tsa.acf(r, nlags=30)[1:]
    return {"modèle": nom, "LB(10) p": lb["lb_pvalue"].iloc[0], "LB(30) p": lb["lb_pvalue"].iloc[1],
            "max |ACF| (1-30)": np.abs(rho).max(), "au retard": int(np.abs(rho).argmax()) + 1,
            "JB p": jb_p, "skewness": skew, "kurtosis": kurt, "ARCH-LM(7) stat": lm, "ARCH-LM(7) p": lm_p}


diag = []
for nom, (m, _) in modeles.items():
    n_arma = sum(1 for p_ in m.param_names if p_.startswith(("ar.", "ma.")))
    diag.append(diagnostic(m.resid, nom, n_arma))
tab_diag = pd.DataFrame(diag).set_index("modèle")
tab_diag.to_csv(RES / "py_diagnostics_arima.csv")
print(tab_diag.round(4).to_string())
print("Seuil de significativité d'une autocorrélation (2 / racine de n) :", round(2 / np.sqrt(n_train - BRULAGE), 3))
r = np.asarray(m_man.resid)[BRULAGE:]
print("Écart-type des résidus par saison (manuel) : hiver",
      round(r[np.isin(train.index[BRULAGE:].month, [12, 1, 2])].std(), 3), "| été",
      round(r[np.isin(train.index[BRULAGE:].month, [6, 7, 8])].std(), 3))

fig, ax = plt.subplots(2, 2, figsize=(12, 7))
ax[0, 0].plot(train.index[BRULAGE:], r, lw=0.4); ax[0, 0].set_title(f"Résidus de l'ARIMA{ORDRE} + Fourier")
plot_acf(r, lags=40, ax=ax[0, 1], zero=False, title="ACF des résidus")
ax[1, 0].hist(r, bins=80, density=True, color="#1f3a5f", alpha=0.7)
xx = np.linspace(r.min(), r.max(), 200); ax[1, 0].plot(xx, stats.norm.pdf(xx, r.mean(), r.std()), color="#e0a030")
ax[1, 0].set_title("Histogramme et loi normale de même variance")
plot_acf(r ** 2, lags=40, ax=ax[1, 1], zero=False, title="ACF des résidus au carré (effets ARCH)")
montrer(fig, "09_diagnostic_arima")

# %% [markdown]
# **Lecture du diagnostic.**
# - **Indépendance (Ljung-Box) :** non rejetée pour l'ARIMA-Fourier (p = 0,09 à 10 retards, 0,25 à 30). La plus forte autocorrélation résiduelle vaut 0,035 pour un seuil de 0,025 avec 6 238 observations : négligeable. Le SARIMAX météo laisse une légère autocorrélation à 30 retards (p = 0,017, maximum de 0,034).
# - **Normalité (Jarque-Bera) :** rejetée (p < 0,001), avec une asymétrie de -0,94 et une kurtosis de 3,71. Les mauvaises surprises (journée couverte inattendue) sont plus fortes que les bonnes, la production ne pouvant pas dépasser celle du ciel clair. Les intervalles gaussiens sont donc approximatifs ; leur couverture réelle est mesurée en section 6.
# - **Homoscédasticité (ARCH-LM) :** massivement rejetée (statistique de 235, p de l'ordre de 1e-47). L'écart-type des résidus vaut 1,21 kWh/kWc en hiver contre 0,64 en été, et l'ACF des carrés décroît lentement : c'est l'objet de la section 3.3.
# - **Bilan :** la moyenne conditionnelle est bien spécifiée, la variance ne l'est pas.

# %% [markdown]
# ### 3.1 bis SARIMA saisonnier sur la série mensuelle (s = 12)

# %%
# À la maille mensuelle, la période saisonnière vaut 12 : on peut identifier (p,d,q)(P,D,Q)[12] à la
# lecture de l'ACF/PACF, comme le demande l'énoncé, puis confirmer par auto_arima.
from pmdarima.arima import nsdiffs

ym = df[CIBLE].resample("MS").sum()
nm = len(ym)
nm_train = int(nm * 0.9)
ym_train = ym.iloc[:nm_train]
print(f"Série mensuelle : {nm} mois, apprentissage {nm_train} ({ym.index[0]:%Y-%m} -> {ym.index[nm_train - 1]:%Y-%m}),"
      f" test {nm - nm_train}")
print("D suggéré : OCSB =", nsdiffs(ym_train.to_numpy(), m=12, test="ocsb"), "| Canova-Hansen =",
      nsdiffs(ym_train.to_numpy(), m=12, test="ch"))
fig, ax = plt.subplots(2, 2, figsize=(12, 5.5))
plot_acf(ym_train, lags=36, ax=ax[0, 0], zero=False, title="ACF - production mensuelle")
plot_pacf(ym_train, lags=36, ax=ax[0, 1], zero=False, title="PACF - production mensuelle", method="ywm")
d12 = ym_train.diff(12).dropna()
plot_acf(d12, lags=36, ax=ax[1, 0], zero=False, title="ACF - différence saisonnière (12)")
plot_pacf(d12, lags=36, ax=ax[1, 1], zero=False, title="PACF - différence saisonnière (12)", method="ywm")
montrer(fig, "10_acf_mensuel")
print("ACF diff. saisonnière, retards 1, 2, 12, 24 :", np.round(sm.tsa.acf(d12, nlags=24)[[1, 2, 12, 24]], 3))
print("Stationnarité de la différence saisonnière :", tests_stationnarite(d12, "diff12"))

grille_m = []
for order in [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)]:
    for seas in [(0, 1, 1), (1, 1, 0), (1, 1, 1), (2, 1, 0)]:
        mm_ = ARIMA(ym_train.to_numpy(), order=order, seasonal_order=seas + (12,), trend="n").fit()
        grille_m.append({"ordre": order, "saisonnier": seas, "AIC": mm_.aic, "BIC": mm_.bic})
grille_m = pd.DataFrame(grille_m).sort_values("BIC").reset_index(drop=True)
grille_m.round(2).to_csv(RES / "py_grille_sarima_mensuel.csv", index=False)
print(grille_m.round(1).head(8).to_string())
ORDRE_M, SAISON_M = grille_m.loc[0, "ordre"], grille_m.loc[0, "saisonnier"]
auto_m = pm.auto_arima(ym_train.to_numpy(), m=12, seasonal=True, stepwise=True, information_criterion="aic",
                       suppress_warnings=True, error_action="ignore")
print(f"Manuel : SARIMA{ORDRE_M}{SAISON_M}[12] | auto_arima : SARIMA{auto_m.order}{auto_m.seasonal_order[:3]}[12]"
      f", constante = {auto_m.with_intercept}")
m_mens = ARIMA(ym_train.to_numpy(), order=ORDRE_M, seasonal_order=SAISON_M + (12,), trend="n").fit()
print("Paramètres :", {k: round(v, 3) for k, v in zip(m_mens.param_names, m_mens.params)})
rm = np.asarray(m_mens.resid)[13:]
print("Diagnostic : LB(12) p =", round(acorr_ljungbox(rm, lags=[12])["lb_pvalue"].iloc[0], 4),
      "| JB p =", round(jarque_bera(rm)[1], 4), "| ARCH-LM(4) p =", round(het_arch(rm, nlags=4)[1], 4))

# Prévision à 6 mois depuis chaque origine du test, comparée au naïf saisonnier (même mois de
# l'année précédente) et à la moyenne mensuelle de l'apprentissage.
HM = 6
orig_m = np.arange(nm_train - 1, nm - HM)
ymv = ym.to_numpy()
clim_m = ym_train.groupby(ym_train.index.month).mean()
complet_m = m_mens.apply(ymv)
complet_auto_m = auto_m.arima_res_.apply(ymv)
pm_ = {"Naïf saisonnier (même mois N-1)": np.stack([ymv[t + 1 - 12:t + 1 + HM - 12] for t in orig_m]),
       "Moyenne mensuelle": np.stack([clim_m.loc[ym.index[t + 1:t + 1 + HM].month].to_numpy() for t in orig_m]),
       "SARIMA manuel": np.stack([complet_m.get_prediction(start=t + 1, end=t + HM, dynamic=0).predicted_mean for t in orig_m]),
       "SARIMA auto": np.stack([complet_auto_m.get_prediction(start=t + 1, end=t + HM, dynamic=0).predicted_mean for t in orig_m])}
Ym = np.stack([ymv[t + 1:t + 1 + HM] for t in orig_m])
tab_m = pd.DataFrame({nom: {"RMSE": np.sqrt(np.mean((Ym - P) ** 2)), "MAE": np.mean(np.abs(Ym - P)),
                            "MAPE (%)": 100 * np.mean(np.abs(Ym - P) / Ym)} for nom, P in pm_.items()}).T
tab_m.to_csv(RES / "py_metriques_mensuel.csv")
print(f"\nÉvaluation sur {len(orig_m)} origines, horizon 6 mois (kWh/kWc/mois) :\n", tab_m.round(2).to_string())

# %% [markdown]
# **Lecture.**
# - **Identification :** OCSB et Canova-Hansen ne demandent pas de différence saisonnière (D = 0, saisonnalité déterministe). L'ACF de la différence saisonnière présente pourtant le pic négatif au retard 12 (-0,51) typique d'une moyenne mobile saisonnière ; le BIC retient SARIMA(0,0,0)(0,1,1)[12], dont le coefficient saisonnier vaut -0,889. Proche de -1, il annule presque la différence saisonnière : le modèle revient à une moyenne mensuelle lentement mobile, ce qui rejoint le verdict des tests. `auto_arima` retient SARIMA(1,0,0)(1,0,1)[12] avec constante, sans différence.
# - **Diagnostic :** résidus blancs (Ljung-Box p = 0,45), gaussiens (Jarque-Bera p = 0,21) et homoscédastiques (ARCH-LM p = 0,83). À la maille mensuelle, les aléas journaliers se compensent : les défauts du modèle journalier disparaissent.
# - **Prévision à 6 mois (18 origines) :** le SARIMA (RMSE de 12,36 kWh/kWc par mois) fait jeu égal avec la moyenne mensuelle de l'apprentissage (12,26) et bat nettement le naïf saisonnier (17,70). À cet horizon, seul le cycle annuel est prévisible ; l'année précédente est un mauvais prédicteur car elle porte sa propre météo.

# %% [markdown]
# ### 3.2 Modèles multivariés : VAR, causalité de Granger et cointégration

# %%
# VAR sur (production, nébulosité, température) de Tunis. Les trois séries sont stationnaires autour
# d'un cycle annuel déterministe (section 2.6) : VAR en niveaux, avec les termes de Fourier en
# variables exogènes pour absorber ce cycle.
VARS = [CIBLE, "nebulosite_pct", "t2m_moy_c"]
endog_var = df[VARS].ffill().to_numpy()
Xv = fourier(3)
sel = VAR(endog_var[:n_train], exog=Xv[:n_train]).select_order(14)
print("Ordre choisi par critère :", sel.selected_orders)
crit = pd.DataFrame({"AIC": sel.ics["aic"], "BIC": sel.ics["bic"], "HQIC": sel.ics["hqic"]}).round(4)
crit.index.name = "p"
crit.to_csv(RES / "py_var_criteres.csv")
print(crit.to_string())

# %%
# On retient l'ordre du BIC s'il blanchit les résidus, sinon celui de l'AIC : le BIC pénalise
# davantage, mais il ne doit pas laisser d'autocorrélation.
P_VAR = max(sel.selected_orders["bic"], 1)
var_fit = VAR(endog_var[:n_train], exog=Xv[:n_train]).fit(P_VAR)
blanc = var_fit.test_whiteness(nlags=20)
print(f"VAR({P_VAR}) - Portmanteau(20) : stat = {blanc.test_statistic:.1f}, p = {blanc.pvalue:.4f}")
P_AIC = sel.selected_orders["aic"]
if blanc.pvalue < 0.05 and P_AIC > P_VAR:
    var_aic = VAR(endog_var[:n_train], exog=Xv[:n_train]).fit(P_AIC)
    b2 = var_aic.test_whiteness(nlags=max(20, P_AIC + 6))
    print(f"VAR({P_AIC}) - Portmanteau({max(20, P_AIC + 6)}) : stat = {b2.test_statistic:.1f}, p = {b2.pvalue:.4f}")
    P_VAR, var_fit = P_AIC, var_aic
print(f"\nOrdre retenu : VAR({P_VAR})")
norm_v = var_fit.test_normality()
print(f"Normalité multivariée (Jarque-Bera) : stat = {norm_v.test_statistic:.1f}, p = {norm_v.pvalue:.4f}")
rv = var_fit.resid
for j, nom in enumerate(VARS):
    lb = acorr_ljungbox(rv[:, j], lags=[10]); lm_p = het_arch(rv[:, j], nlags=7)[1]
    print(f"  équation {nom:15s} : Ljung-Box(10) p = {lb['lb_pvalue'].iloc[0]:.4f} | ARCH-LM(7) p = {lm_p:.4g}")
print("Stabilité (racines hors du cercle unité) :", var_fit.is_stable())
print("Corrélation des résidus (contemporaine) :\n", pd.DataFrame(np.corrcoef(rv.T), index=VARS, columns=VARS).round(3))

# %%
# Causalité de Granger dans tous les sens : la physique dit que les nuages réduisent la production,
# mais les deux séries mesurent le même état du ciel ; le test dira si le passé de l'une aide à
# prévoir l'autre au-delà de son propre passé.
lignes_g = []
for i, cause in enumerate(VARS):
    for j, effet in enumerate(VARS):
        if i != j:
            g = var_fit.test_causality(j, [i], kind="f")
            lignes_g.append({"cause": cause, "effet": effet, "F": g.test_statistic, "p": g.pvalue})
granger = pd.DataFrame(lignes_g)
granger.to_csv(RES / "py_granger.csv", index=False)
print(granger.round(4).to_string(index=False))

# L'orthogonalisation (Cholesky) dépend de l'ordre des variables : on place la nébulosité en premier,
# car les nuages agissent sur la production du jour même et non l'inverse. VAR identique, colonnes permutées.
var_irf = VAR(endog_var[:n_train][:, [1, 0, 2]], exog=Xv[:n_train]).fit(P_VAR)
irf = var_irf.irf(10)
rep = irf.orth_irfs[:, 1, 0]          # réponse orthogonalisée de la production à un choc de nébulosité
ic = irf.stderr(orth=True)[:, 1, 0]
fig, ax = plt.subplots(figsize=(8, 3.5))
ax.plot(rep, marker="o", color="#1f3a5f")
ax.fill_between(range(len(rep)), rep - 1.96 * ic, rep + 1.96 * ic, alpha=0.2)
ax.axhline(0, color="k", lw=0.8); ax.set_xlabel("jours après le choc"); ax.set_ylabel("kWh/kWc")
ax.set_title("Réponse de la production à un choc d'un écart-type de nébulosité (VAR, orthogonalisée)")
montrer(fig, "11_var_irf")
print("Réponse (kWh/kWc) aux jours 0..6 :", np.round(rep[:7], 3), "| écart-type du choc de nébulosité :",
      round(np.sqrt(var_fit.sigma_u[1, 1]), 1), "points")
print("Part de la variance d'erreur de prévision de la production à 7 jours due à la nébulosité :",
      round(float(var_irf.fevd(7).decomp[1, 6, 0]), 3))

# %%
# Extension multi-pays : la météo de l'Espagne aide-t-elle à prévoir la production de Tunis ? Les
# perturbations atlantiques traversent souvent la péninsule Ibérique avant d'atteindre la Tunisie.
# VAR bivariés sur les anomalies (cycle annuel retiré), ordre choisi par le BIC.
def anomalie_site(site, col=CIBLE):
    v = panel[panel["site"] == site].set_index("date")[col].asfreq("D").to_numpy()
    b = np.linalg.lstsq(X4[:n_train], v[:n_train], rcond=None)[0]
    return v - X4 @ b


lignes_x = []
for amont in ("seville", "madrid", "barcelone", "marseille", "tozeur"):
    paire = np.column_stack([anomalie_site(SITE), anomalie_site(amont)])[:n_train]
    p_ = max(VAR(paire).select_order(7).selected_orders["bic"], 1)
    vx = VAR(paire).fit(p_)
    g_a = vx.test_causality(0, [1], kind="f")
    g_b = vx.test_causality(1, [0], kind="f")
    corr0 = np.corrcoef(paire.T)[0, 1]
    corr1 = np.corrcoef(paire[1:, 0], paire[:-1, 1])[0, 1]
    lignes_x.append({"site amont": SITES[amont]["ville"], "ordre VAR": p_, "corr. même jour": corr0,
                     "corr. Tunis(t) / amont(t-1)": corr1, "F (amont -> Tunis)": g_a.test_statistic,
                     "p (amont -> Tunis)": g_a.pvalue, "F (Tunis -> amont)": g_b.test_statistic,
                     "p (Tunis -> amont)": g_b.pvalue})
granger_x = pd.DataFrame(lignes_x)
granger_x.to_csv(RES / "py_granger_multi_sites.csv", index=False)
print(granger_x.round(4).to_string(index=False))

# %% [markdown]
# **Lecture.**
# - **Ordre :** l'AIC et le BIC choisissent tous deux 3 retards. Le test Portmanteau multivarié rejette de peu la blancheur (p = 0,018), mais chaque équation passe le test de Ljung-Box (p = 0,54 ; 0,26 ; 0,08) et le VAR est stable. Ses résidus ne sont pas gaussiens et présentent un effet ARCH, comme ceux de l'ARIMA.
# - **Causalité de Granger :** le passé de la nébulosité aide fortement à prévoir la production (F = 98,8), et le passé de la production aide aussi à prévoir la nébulosité (F = 14,3). La relation est bidirectionnelle parce que les deux séries mesurent, chacune imparfaitement, le même état du ciel. La production de la veille aide à prévoir la température (F = 19,3) : une journée claire réchauffe le sol et l'air, effet physique attendu. La température n'aide que marginalement à prévoir la production (p = 0,034). Rappel : la causalité de Granger mesure la prévisibilité, pas la causalité physique.
# - **Réponse impulsionnelle (nébulosité placée en premier) :** un choc d'un écart-type de nébulosité (21,7 points) réduit la production de 0,66 kWh/kWc le jour même, de 0,35 le lendemain et de 0,13 à J+2 ; l'effet disparaît en 4 jours. Les chocs de nébulosité expliquent 44,5 % de la variance d'erreur de prévision de la production à 7 jours.
# - **Météo des autres pays :** le même jour, les anomalies de Tunis ne sont pas corrélées à celles de Séville, Madrid, Barcelone ou Marseille (|r| < 0,08). En revanche, l'anomalie de la veille à Barcelone (r = 0,12) et à Marseille (0,07) aide à prévoir Tunis (F = 108,5 et 37,0 ; p < 0,001), alors que l'inverse est beaucoup plus faible ; Séville aide à prévoir Tunis (p < 0,001) sans réciproque (p = 0,24). C'est cohérent avec des perturbations qui traversent le nord-ouest de la Méditerranée avant d'atteindre la Tunisie, mais le test ne prouve pas ce mécanisme et le gain reste modeste (de l'ordre de 1,5 % de variance). Tozeur, à 370 km, est corrélée le jour même (0,35).

# %%
# Cointégration : le test n'a de sens que pour des séries intégrées d'ordre 1. On l'applique
# d'abord au VAR de Tunis pour montrer ce qu'il renvoie sur des séries stationnaires.
eg_stat, eg_p, eg_crit = coint(train[CIBLE], train["nebulosite_pct"], trend="c", autolag="AIC")
print(f"Engle-Granger (production, nébulosité) : stat = {eg_stat:.3f}, p = {eg_p:.4f}")
joh = coint_johansen(endog_var[:n_train], det_order=0, k_ar_diff=max(P_VAR - 1, 1))
tab_joh = pd.DataFrame({"H0": [f"r <= {i}" for i in range(len(VARS))], "trace": joh.lr1, "crit. 95 %": joh.cvt[:, 1],
                        "valeur propre max": joh.lr2, "crit. 95 % (vp max)": joh.cvm[:, 1]}).round(3)
print("Johansen (Tunis : production, nébulosité, température) :\n", tab_joh.to_string(index=False))
def rang_johansen(res):
    """Procédure séquentielle de la trace : le rang est le premier r dont l'hypothèse « rang <= r » n'est
    pas rejetée à 5 % (compter les rejets serait faux quand un test intermédiaire rejette)."""
    for r_ in range(len(res.lr1)):
        if res.lr1[r_] <= res.cvt[r_, 1]:
            return r_
    return len(res.lr1)


print("Rang estimé (procédure séquentielle) :", rang_johansen(joh), "sur", len(VARS))

# %% [markdown]
# **Un cas réellement non stationnaire : la production solaire nationale mesurée.** Les séries PVGIS
# simulent une installation de puissance constante : elles n'ont pas de tendance. La production
# nationale mesurée par RTE (France) et REE (Espagne) croît au contraire avec le parc installé. C'est
# sur ces deux séries, à la maille mensuelle et en logarithme, que la question de la cointégration se
# pose vraiment : les deux parcs partagent-ils une tendance commune de long terme ?

# %%
# Séries mensuelles en log, désaisonnalisées par régression sur des indicatrices de mois (la
# saisonnalité est commune et déterministe : elle ne doit pas créer une fausse relation).
rte = pd.read_csv(JEUX / "fr_solaire_national_rte_journalier.csv", index_col="date", parse_dates=True)
ree = pd.read_csv(JEUX / "es_fotovoltaica_ree_journalier.csv", index_col="date", parse_dates=True)
nat = pd.concat({"France": rte["production_gwh"].resample("MS").sum(min_count=25),
                 "Espagne": ree["produccion_gwh"].resample("MS").sum(min_count=25)}, axis=1).dropna()
nat = nat.loc[:"2026-08-01"]
lnat = np.log(nat)
indic = pd.get_dummies(lnat.index.month, drop_first=True).astype(float).to_numpy()
Xd = np.column_stack([np.ones(len(lnat)), indic])
ldes = lnat - Xd[:, 1:] @ np.linalg.lstsq(Xd, lnat.to_numpy(), rcond=None)[0][1:]
print(f"Période commune : {nat.index[0]:%Y-%m} -> {nat.index[-1]:%Y-%m} ({len(nat)} mois)")
lignes_n = []
for c in ldes.columns:
    lignes_n.append(tests_stationnarite(ldes[c], f"log {c} (désaisonnalisé), avec tendance", "ct"))
    lignes_n.append(tests_stationnarite(ldes[c].diff(), f"log {c} - diff. ordre 1"))
tab_stat_nat = pd.DataFrame(lignes_n).set_index("série")
print(tab_stat_nat.to_string())
p_nat = max(VAR(ldes.diff().dropna().to_numpy()).select_order(6).selected_orders["aic"], 1)
eg_n = coint(ldes["France"], ldes["Espagne"], trend="ct", autolag="AIC")
print(f"\nEngle-Granger (avec tendance) : stat = {eg_n[0]:.3f}, p = {eg_n[1]:.4f}")
joh_n = coint_johansen(ldes.to_numpy(), det_order=1, k_ar_diff=p_nat)
tab_joh_n = pd.DataFrame({"H0": ["r = 0", "r <= 1"], "trace": joh_n.lr1, "crit. 95 %": joh_n.cvt[:, 1],
                          "valeur propre max": joh_n.lr2, "crit. 95 % (vp max)": joh_n.cvm[:, 1]}).round(3)
tab_joh_n.to_csv(RES / "py_johansen_national.csv", index=False)
tab_joh.to_csv(RES / "py_johansen.csv", index=False)
RANG_N = rang_johansen(joh_n)
print(f"Johansen (tendance linéaire, {p_nat} retards en différences) :\n", tab_joh_n.to_string(index=False))
print("Rang de cointégration estimé (procédure séquentielle) :", RANG_N)

# %%
# VECM : estimé si un rang de cointégration est détecté (et, à titre de vérification, avec un rang
# imposé à 1 sinon). Alpha mesure la vitesse de retour vers la relation de long terme.
vecm = VECM(lnat.to_numpy(), k_ar_diff=p_nat, coint_rank=1, deterministic="li", seasons=12).fit()
beta = vecm.beta.ravel()
print("Vecteur de cointégration beta (normalisé sur la France) :", np.round(beta / beta[0], 4))
print("Coefficients d'ajustement alpha [France, Espagne] :", np.round(vecm.alpha.ravel(), 4),
      "| p-values :", np.round(vecm.pvalues_alpha.ravel(), 4))
for k, pays_ in enumerate(("France", "Espagne")):
    a_ = vecm.alpha[k, 0]
    if -2 < a_ < 0:
        print(f"Demi-vie de l'écart pour {pays_} : {np.log(0.5) / np.log(1 + a_):.1f} mois")
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
ax[0].plot(lnat.index, lnat["France"], label="France (RTE)", color=COULEUR_PAYS["France"])
ax[0].plot(lnat.index, lnat["Espagne"], label="Espagne (REE)", color=COULEUR_PAYS["Espagne"])
ax[0].set_ylabel("log(GWh/mois)"); ax[0].legend(); ax[0].set_title("Production solaire nationale mesurée (log)")
ect = lnat.to_numpy() @ beta
ax[1].plot(lnat.index, ect - ect.mean(), color="#1f3a5f")
ax[1].axhline(0, color="k", lw=0.8); ax[1].set_title("Écart à la relation de long terme estimée (VECM)")
montrer(fig, "12_cointegration_national")

# %% [markdown]
# **Lecture : où la cointégration s'applique, et où elle ne s'applique pas.**
# - **Tunis : non applicable.** Les trois séries sont stationnaires (section 2.6). Le test de Johansen rejette toutes les hypothèses (trace de 2 129, 993 et 62 pour des seuils de 29,8 ; 15,5 et 3,8) : le rang est plein, ce qui signifie que le système est stationnaire en niveaux. Le test d'Engle-Granger « rejette l'absence de cointégration » (statistique de -6,28), mais c'est trompeur : une combinaison de séries stationnaires est toujours stationnaire. La bonne représentation est le VAR en niveaux.
# - **Productions nationales mesurées : séries I(1), non cointégrées.** Sur 2014-2026 (152 mois), le log de la production désaisonnalisée n'est stationnaire ni en France ni en Espagne (ADF avec tendance : p = 0,19 et 0,36 ; le KPSS rejette), alors que ses différences le sont. Les deux séries sont intégrées d'ordre 1 : la question de la cointégration se pose vraiment, et la réponse est non. Engle-Granger donne p = 0,38 ; le test de la trace ne rejette pas « rang = 0 » (15,1 contre 18,4). Le rejet isolé de « rang <= 1 » (5,1 contre 3,8) signale une tendance propre à l'une des séries, pas une relation commune. R conclut de même (trace de 15,3 contre 25,3, avec indicatrices saisonnières).
# - **VECM de vérification (rang imposé à 1) :** coefficients d'ajustement de -0,0007 et -0,0008, soit des demi-vies de 900 à 1 000 mois : aucune force de rappel. Les deux parcs suivent des politiques nationales distinctes : la production espagnole a été multipliée par 6,7 entre 2018 et 2025 (de 7,4 à 49,3 TWh), la française par 3,1 (de 10,6 à 32,5 TWh). Un VAR en différences, et non un VECM, serait la représentation adaptée.
