"""Figures du rapport (matplotlib).

Règles suivies : un seul axe par figure, traits fins, grille discrète, texte à l'encre, couleur attachée à
l'entité dans un ordre fixe (France, Tunisie, Espagne ; crystSi, CIS, CdTe), légende dès deux séries,
étiquettes directes quand elles tiennent. Chaque figure a son tableau dans le rapport.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")                                      # pas d'écran : les figures sont écrites dans des fichiers
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from solarvision.config import load_cities, load_params

SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]                 # ordre fixe : bleu, orange, vert d'eau
COUNTRY_COLOR = {"France": SERIES[0], "Tunisie": SERIES[1], "Espagne": SERIES[2]}
TECH_COLOR = {"crystSi": SERIES[0], "CIS": SERIES[1], "CdTe": SERIES[2]}
MODEL_LABELS = {"persistance": "Persistance", "climatologie": "Climatologie", "arima_fourier": "AR(1) + Fourier",
                "xgboost": "XGBoost", "prophet": "Prophet", "lstm": "LSTM", "gru": "GRU", "lstm_global": "LSTM global",
                "xgboost_expost": "XGBoost + météo", "lstm_expost": "LSTM + météo", "gru_expost": "GRU + météo"}
MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "DejaVu Sans"], "font.size": 9, "text.color": INK, "axes.labelcolor": INK_2,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "lines.linewidth": 2,
        "legend.frameon": False, "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left"})


_style()


def _save(fig, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return path


def _country_legend(ax, present: list[str]) -> None:
    handles = [plt.Line2D([], [], marker="s", linestyle="", color=COUNTRY_COLOR[c], markersize=6, label=c)
               for c in COUNTRY_COLOR if c in present]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=3, handletextpad=0.3, columnspacing=1.6)


def cities_map(cities: list[dict], out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    for c in cities:
        ax.scatter(c["lon"], c["lat"], s=42, color=COUNTRY_COLOR[c["pays"]], edgecolor=SURFACE, linewidth=1.2, zorder=3)
        ax.annotate(c["nom"], (c["lon"], c["lat"]), xytext=(5, 3), textcoords="offset points", fontsize=7.5, color=INK_2)
    ax.set_xlabel("Longitude (°)")
    ax.set_ylabel("Latitude (°)")
    ax.set_title("Villes de l'étude")
    _country_legend(ax, [c["pays"] for c in cities])
    return _save(fig, out, "01_villes")


def seasonal_profiles(panel: pd.DataFrame, out: Path) -> Path:
    """Production moyenne par mois, moyenne des villes de chaque pays."""
    column = f"pv_{load_params()['pv']['reference_technology']}_kwh_kwc"
    month = pd.DatetimeIndex(panel["date"]).month
    profile = panel.groupby(["pays", month])[column].mean().unstack(0)
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for country in COUNTRY_COLOR:
        if country in profile:
            ax.plot(range(1, 13), profile[country], color=COUNTRY_COLOR[country], marker="o", markersize=4, label=country)
    ax.set_xticks(range(1, 13), MONTHS)
    ax.set_ylim(0, None)
    ax.set_ylabel("kWh/kWc par jour")
    ax.set_title("Production moyenne par mois (2005-2023)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=3)
    return _save(fig, out, "02_profils_saisonniers")


def gain_by_horizon(wide: pd.DataFrame, out: Path) -> Path:
    """Gain de RMSE sur la climatologie selon l'horizon, moyenne des villes, pour trois modèles ex ante."""
    reference = load_params()["pv"]["reference_technology"]
    m = wide[(wide["technologie"] == reference) & (wide["horizon"] != "tous")].copy()
    m["horizon"] = m["horizon"].astype(int)
    table = m.pivot_table(index=["ville", "horizon"], columns="modele", values="RMSE")
    models = [x for x in ("arima_fourier", "xgboost", "lstm_global") if x in table]
    gain = pd.DataFrame({x: 100 * (1 - table[x] / table["climatologie"]) for x in models}).groupby(level="horizon").mean()
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.axhline(0, color=AXIS, linewidth=1)
    for x, color in zip(models, SERIES, strict=False):
        ax.plot(gain.index, gain[x], color=color, marker="o", markersize=4, label=MODEL_LABELS[x])
    ax.set_xlabel("Horizon (jours)")
    ax.set_ylabel("Gain de RMSE sur la climatologie (%)")
    ax.set_title("Gain sur la climatologie selon l'horizon, moyenne des villes (0 = climatologie)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=3)
    return _save(fig, out, "03_gain_par_horizon")


def gain_by_city(summary: pd.DataFrame, out: Path) -> Path:
    data = summary.sort_values("gain_vs_climatologie_pct")
    names = [load_cities()[c].nom for c in data["ville"]]
    fig, ax = plt.subplots(figsize=(6.4, 0.2 * len(data) + 1.1))
    ax.barh(names, data["gain_vs_climatologie_pct"], color=[COUNTRY_COLOR[p] for p in data["pays"]], height=0.62)
    for y, value in enumerate(data["gain_vs_climatologie_pct"]):
        ax.annotate(f"{value:.1f}".replace(".", ","), (value, y), xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=7.5, color=INK_2)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Gain de RMSE du meilleur modèle ex ante (%)")
    ax.set_title("Gain sur la climatologie, par ville (J+1 à J+7)")
    _country_legend(ax, list(data["pays"]))
    return _save(fig, out, "04_gain_par_ville")


def models_overview(wide: pd.DataFrame, out: Path) -> Path:
    """RMSE moyen de chaque modèle ; la couleur sépare ex ante et ex post."""
    reference = load_params()["pv"]["reference_technology"]
    m = wide[(wide["technologie"] == reference) & (wide["horizon"] == "tous")]
    table = m.groupby(["modele", "scenario"])["RMSE"].mean().reset_index().sort_values("RMSE", ascending=False)
    colors = [SERIES[1] if s == "ex_post" else SERIES[0] for s in table["scenario"]]
    fig, ax = plt.subplots(figsize=(6.4, 0.3 * len(table) + 1.0))
    ax.barh([MODEL_LABELS.get(x, x) for x in table["modele"]], table["RMSE"], color=colors, height=0.62)
    for y, value in enumerate(table["RMSE"]):
        ax.annotate(f"{value:.3f}".replace(".", ","), (value, y), xytext=(4, 0), textcoords="offset points", va="center",
                    fontsize=7.5, color=INK_2)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("RMSE moyen (kWh/kWc)")
    ax.set_title("Erreur moyenne des modèles, toutes villes")
    ax.legend(handles=[plt.Line2D([], [], marker="s", linestyle="", color=SERIES[0], markersize=6, label="ex ante (opérationnel)"),
                       plt.Line2D([], [], marker="s", linestyle="", color=SERIES[1], markersize=6, label="ex post (météo observée)")],
              loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=2)
    return _save(fig, out, "05_modeles")


def loss_curves(curves: pd.DataFrame, city: str, out: Path) -> Path:
    """Courbes de perte du LSTM de la ville : apprentissage et validation, ex ante puis ex post."""
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.9), sharey=True)
    for ax, (model, title) in zip(axes, (("lstm", "LSTM ex ante"), ("lstm_expost", "LSTM ex post")), strict=True):
        c = curves[(curves["ville"] == city) & (curves["modele"] == model)]
        ax.plot(c["epoque"], c["perte_apprentissage"], color=SERIES[0], label="Apprentissage")
        ax.plot(c["epoque"], c["perte_validation"], color=SERIES[1], label="Validation")
        if len(c):
            best = int(c["meilleure_epoque"].iloc[0])
            ax.axvline(best, color=AXIS, linestyle=(0, (2, 3)), linewidth=1)
            ax.annotate(f"arrêt : époque {best}", (best, ax.get_ylim()[1]), xytext=(4, -10), textcoords="offset points",
                        fontsize=7.5, color=MUTED)
        ax.set_title(title)
        ax.set_xlabel("Époque")
    axes[0].set_ylabel("Erreur quadratique (cible normalisée)")
    axes[0].legend(loc="upper right")
    return _save(fig, out, "06_courbes_perte")


def technology_yield(indicators: pd.DataFrame, out: Path) -> Path:
    """Production annuelle moyenne par pays et par technologie."""
    table = indicators.pivot_table(index="pays", columns="technologie", values="rendement_annuel_kwh_kwc")
    countries = [c for c in COUNTRY_COLOR if c in table.index]
    technologies = [t for t in TECH_COLOR if t in table.columns]
    fig, ax = plt.subplots(figsize=(6.4, 3.3))
    width = 0.26
    for k, tech in enumerate(technologies):
        x = np.arange(len(countries)) + (k - 1) * (width + 0.02)
        ax.bar(x, table.loc[countries, tech], width=width, color=TECH_COLOR[tech], label=tech)
        for xi, value in zip(x, table.loc[countries, tech], strict=True):
            ax.annotate(f"{value:.0f}", (xi, value), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7.5, color=INK_2)
    ax.set_xticks(np.arange(len(countries)), countries)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("kWh/kWc par an")
    ax.set_title("Production annuelle moyenne par technologie")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=3)
    return _save(fig, out, "07_technologies")


def technology_decision(recommendation: pd.DataFrame, out: Path) -> Path:
    """Écart de score entre les deux premières technologies de chaque ville, avec son intervalle."""
    data = recommendation.sort_values("ecart_score")
    names = [load_cities()[c].nom for c in data["ville"]]
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(6.4, 0.2 * len(data) + 1.2))
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.hlines(y, data["ecart_score_ic95_bas"], data["ecart_score_ic95_haut"], color=AXIS, linewidth=1.5)
    for tech, color in TECH_COLOR.items():
        sel = (data["technologie_recommandee"] == tech).to_numpy()
        if sel.any():
            ax.scatter(data["ecart_score"][sel], y[sel], s=34, color=color, edgecolor=SURFACE, linewidth=1.2, zorder=3, label=tech)
    ax.set_yticks(y, names)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Écart de score entre la première et la deuxième technologie (intervalle à 95 %)")
    ax.set_title("Technologie recommandée : l'avance est-elle nette ?")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=3, title="Première technologie")
    return _save(fig, out, "08_decision_technologie")


def npv_by_city(economics: pd.DataFrame, out: Path) -> Path:
    """Valeur actuelle nette médiane et intervalle P10-P90, technologie de référence."""
    reference = load_params()["pv"]["reference_technology"]
    data = economics[economics["technologie"] == reference].sort_values("van_eur_p50")
    names = [load_cities()[c].nom for c in data["ville"]]
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(6.4, 0.2 * len(data) + 1.2))
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.hlines(y, data["van_eur_p10"], data["van_eur_p90"], color=[COUNTRY_COLOR[p] for p in data["pays"]], linewidth=1.5, alpha=0.55)
    ax.scatter(data["van_eur_p50"], y, s=34, color=[COUNTRY_COLOR[p] for p in data["pays"]], edgecolor=SURFACE, linewidth=1.2, zorder=3)
    ax.set_yticks(y, names)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Valeur actuelle nette sur 25 ans (€) : médiane et intervalle P10-P90")
    ax.set_title("Valeur actuelle nette d'une installation de 3 kWc (hypothèses à vérifier)")
    _country_legend(ax, list(data["pays"]))
    return _save(fig, out, "09_van_par_ville")


def tornado(table: pd.DataFrame, city: str, out: Path) -> Path | None:
    """Sensibilité de la valeur actuelle nette à chaque hypothèse, pour une ville."""
    labels = {"self_consumption": "Part autoconsommée", "discount_rate": "Taux d'actualisation", "inflation": "Hausse du prix de l'électricité",
              "om_share": "Entretien", "retail_price": "Prix d'achat", "export_price": "Prix de rachat",
              "capex_per_kwp": "Coût par kWc", "capex_multiplier": "Surcoût de la technologie", "degradation": "Dégradation"}
    data = table[table["ville"] == city].sort_values("amplitude_eur")
    data = data[data["amplitude_eur"] > 0]
    if data.empty:
        return None
    base = data["van_centrale_eur"].iloc[0]
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(6.4, 0.3 * len(data) + 1.2))
    ax.barh(y, data["van_valeur_basse_eur"] - base, left=base, color=SERIES[0], height=0.6, label="Valeur basse de l'hypothèse")
    ax.barh(y, data["van_valeur_haute_eur"] - base, left=base, color=SERIES[1], height=0.6, label="Valeur haute de l'hypothèse")
    ax.axvline(base, color=INK_2, linewidth=1)
    ax.set_yticks(y, [labels.get(h, h) for h in data["hypothese"]])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Valeur actuelle nette (€)")
    ax.set_title(f"Sensibilité de la valeur actuelle nette - {load_cities()[city].nom}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 0), borderaxespad=4.4, ncol=2)
    return _save(fig, out, "10_sensibilite_van")
