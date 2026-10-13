"""Fiabilité des technologies photovoltaïques par ville : indicateurs calculés, score, incertitude.

Limites à garder en tête : PVGIS **simule** la production à partir d'images satellitaires. Les écarts
entre technologies viennent donc de leurs modèles de rendement (température, faible éclairement,
spectre), pas de mesures. La dégradation dans le temps et la fiabilité mécanique ne sont pas modélisées.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from solarvision.config import CONFIGS, load_cities, load_params

CRITERIA = ["previsibilite", "stabilite", "sensibilite_temperature", "faible_irradiation", "rendement_annuel"]
STABILITY_PARTS = ["cv_journalier_pct", "cv_mensuel_pct", "ecart_p10_p50_pct"]


def load_reliability_config() -> dict:
    return yaml.safe_load((CONFIGS / "reliability.yaml").read_text(encoding="utf-8"))


def yearly_statistics(frame: pd.DataFrame, technology: str, cfg: dict) -> pd.DataFrame:
    """Statistiques suffisantes par année : les indicateurs s'en déduisent, et le bootstrap recombine les années."""
    ind = cfg["indicators"]
    pv, normal = frame[f"pv_{technology}_kwh_kwc"], frame[f"normale_{technology}"]
    irradiation, t_max = frame["expost_irr_poa_kwh_m2"], frame["expost_t2m_max_c"]
    temperature = frame["expost_t2m_moy_c"]
    ratio = (pv / irradiation).where(irradiation > ind["min_irradiation_kwh_m2"])     # ratio de performance du jour
    low_cut, high_cut = irradiation.quantile(ind["low_irradiation_quantile"]), irradiation.quantile(ind["high_irradiation_quantile"])
    clear = (irradiation > ind["clear_day_min_irradiation_kwh_m2"]) & ratio.notna()
    hot = (t_max > ind["hot_day_threshold_c"]) & clear
    lo, hi = ind["hot_day_reference_range_c"]
    mild = t_max.between(lo, hi) & clear
    low = (irradiation <= low_cut) & ratio.notna()
    high = (irradiation >= high_cut) & ratio.notna()
    dates = pd.DatetimeIndex(frame["date"])
    monthly = pv.groupby([dates.year, dates.month]).sum()
    monthly_anomaly = monthly - monthly.groupby(level=1).transform("mean")           # écart au mois moyen
    x, y = temperature.where(clear), ratio.where(clear)
    day = pd.DataFrame({
        "pv": pv, "anomaly_sq": (pv - normal) ** 2, "n": 1.0,
        "reg_n": clear.astype(float), "reg_x": x, "reg_y": y, "reg_xy": x * y, "reg_xx": x * x,
        "hot_ratio": ratio.where(hot), "hot_n": hot.astype(float), "mild_ratio": ratio.where(mild), "mild_n": mild.astype(float),
        "low_ratio": ratio.where(low), "low_n": low.astype(float), "high_ratio": ratio.where(high), "high_n": high.astype(float),
    })
    yearly = day.groupby(dates.year).sum(min_count=1).fillna(0.0)
    yearly["monthly_anomaly_sq"] = (monthly_anomaly ** 2).groupby(level=0).sum()
    yearly["months"] = monthly.groupby(level=0).size()
    return yearly


def indicators_from_years(yearly: pd.DataFrame, cfg: dict) -> dict[str, float]:
    """Indicateurs d'une ville et d'une technologie à partir des statistiques annuelles (éventuellement rééchantillonnées)."""
    s = yearly.sum()
    annual = yearly["pv"].to_numpy()
    mean_day, mean_month = s["pv"] / s["n"], s["pv"] / s["months"]
    slope = (s["reg_n"] * s["reg_xy"] - s["reg_x"] * s["reg_y"]) / (s["reg_n"] * s["reg_xx"] - s["reg_x"] ** 2)
    mean_ratio = s["reg_y"] / s["reg_n"]
    enough_hot = s["hot_n"] >= cfg["indicators"]["min_hot_days"] and s["mild_n"] > 0
    return {
        "rendement_annuel_kwh_kwc": float(annual.mean()),
        "cv_journalier_pct": float(100 * np.sqrt(s["anomaly_sq"] / s["n"]) / mean_day),
        "cv_mensuel_pct": float(100 * np.sqrt(s["monthly_anomaly_sq"] / s["months"]) / mean_month),
        "ecart_p10_p50_pct": float(100 * (np.quantile(annual, 0.5) - np.quantile(annual, 0.1)) / np.quantile(annual, 0.5)),
        "pente_temperature_pct_par_degre": float(100 * slope / mean_ratio),
        "perte_jours_chauds_pct": float(100 * ((s["hot_ratio"] / s["hot_n"]) / (s["mild_ratio"] / s["mild_n"]) - 1)) if enough_hot else float("nan"),
        "jours_chauds_par_an": float(s["hot_n"] / len(yearly)),
        "ratio_faible_irradiation": float((s["low_ratio"] / s["low_n"]) / (s["high_ratio"] / s["high_n"])),
    }


def criteria_table(indicators: pd.DataFrame) -> pd.DataFrame:
    """Passe des indicateurs bruts aux cinq critères du score (valeurs brutes, avant normalisation)."""
    out = indicators[["ville", "pays", "technologie"]].copy()
    out["previsibilite"] = indicators["wape_meilleur_ex_ante_pct"]
    out["sensibilite_temperature"] = indicators["pente_temperature_pct_par_degre"].abs()
    out["faible_irradiation"] = indicators["ratio_faible_irradiation"]
    out["rendement_annuel"] = indicators["rendement_annuel_kwh_kwc"]
    # Stabilité : moyenne des trois variabilités, chacune ramenée entre 0 et 1 dans le pays pour être comparable.
    parts = indicators.groupby("pays")[STABILITY_PARTS].transform(_min_max)
    out["stabilite"] = parts.mean(axis=1)
    return out


def _min_max(column: pd.Series) -> pd.Series:
    spread = column.max() - column.min()
    return (column - column.min()) / spread if spread > 0 else column * 0.0


def scores(criteria: pd.DataFrame, weights: dict[str, float], cfg: dict) -> pd.Series:
    """Score entre 0 et 1 : somme pondérée des critères, normalisés par pays, tous orientés « plus haut = mieux »."""
    total = pd.Series(0.0, index=criteria.index)
    for name in CRITERIA:
        normalized = criteria.groupby("pays")[name].transform(_min_max)
        if cfg["criteria"][name]["better"] == "lower":
            normalized = 1 - normalized
        total += weights[name] * normalized
    return total / sum(weights.values())


def pareto_front(criteria_city: pd.DataFrame, cfg: dict) -> list[str]:
    """Technologies non dominées dans une ville : aucune autre n'est au moins aussi bonne partout et meilleure quelque part."""
    oriented = criteria_city.set_index("technologie")[CRITERIA].copy()
    for name in CRITERIA:
        if cfg["criteria"][name]["better"] == "lower":
            oriented[name] = -oriented[name]
    front = []
    for tech, row in oriented.iterrows():
        others = oriented.drop(index=tech)
        dominated = ((others >= row).all(axis=1) & (others > row).any(axis=1)).any()
        if not dominated:
            front.append(tech)
    return front


def compute(panel: pd.DataFrame, metrics_wide: pd.DataFrame, forecasts: pd.DataFrame, reports: Path) -> dict[str, pd.DataFrame]:
    """Indicateurs, scores, incertitude et recommandation pour toutes les villes du panel."""
    cfg, params = load_reliability_config(), load_params()
    technologies = params["pv"]["technologies"]
    weights = {k: v["weight"] for k, v in cfg["criteria"].items()}
    cities = load_cities()
    rng = np.random.default_rng(params["seed"])

    # ---- prévisibilité : meilleur modèle ex ante parmi ceux qui existent pour les trois technologies
    ex_ante = metrics_wide[(metrics_wide["scenario"] == "ex_ante") & (metrics_wide["horizon"] == "tous")]
    common = set.intersection(*[set(ex_ante[ex_ante["technologie"] == t]["modele"]) for t in technologies])
    best = ex_ante[ex_ante["modele"].isin(common)].sort_values("WAPE").groupby(["ville", "technologie"]).first()

    yearly, rows = {}, []
    for city, frame in panel.groupby("ville"):
        for tech in technologies:
            stats = yearly_statistics(frame.reset_index(drop=True), tech, cfg)
            yearly[(city, tech)] = stats
            rows.append({"ville": city, "pays": cities[city].pays, "technologie": tech, **indicators_from_years(stats, cfg),
                         "wape_meilleur_ex_ante_pct": float(best.loc[(city, tech), "WAPE"]),
                         "modele_prevision": best.loc[(city, tech), "modele"]})
    indicators = pd.DataFrame(rows)
    criteria = criteria_table(indicators)
    criteria["score"] = scores(criteria, weights, cfg)

    # ---- incertitude : on rééchantillonne des années entières (indicateurs) et des blocs d'origines (prévisibilité)
    replicates = cfg["uncertainty"]["bootstrap_replicates"]
    years = sorted(next(iter(yearly.values())).index)
    errors = forecasts[forecasts["scenario"] == "ex_ante"].assign(
        abs_error=lambda d: (d["observation"] - d["prevision"]).abs().astype("float64"))
    per_origin = errors.groupby(["ville", "technologie", "modele", "origine"])[["abs_error", "observation"]].sum()
    block = params["evaluation"]["bootstrap_block_days"]
    boot_scores = np.empty((replicates, len(criteria)))
    for b in range(replicates):
        drawn_years = rng.choice(years, size=len(years), replace=True)
        boot_rows = []
        n_origins = None
        for (city, tech), stats in yearly.items():
            sample = stats.loc[drawn_years]
            ind = indicators_from_years(sample, cfg)
            daily = per_origin.loc[(city, tech, best.loc[(city, tech), "modele"])]
            if n_origins is None:
                n_origins = len(daily)
                starts = rng.integers(0, n_origins - block + 1, size=int(np.ceil(n_origins / block)))
                picked = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n_origins]   # mêmes blocs pour toutes les séries
            values = daily.to_numpy()[picked]
            ind["wape_meilleur_ex_ante_pct"] = float(100 * values[:, 0].sum() / values[:, 1].sum())
            boot_rows.append({"ville": city, "pays": cities[city].pays, "technologie": tech, **ind})
        boot_criteria = criteria_table(pd.DataFrame(boot_rows))
        boot_scores[b] = scores(boot_criteria, weights, cfg).to_numpy()
    # ---- sensibilité aux poids : le classement tient-il si l'on déplace les poids ?
    w_cfg = cfg["weight_sensitivity"]
    base = np.array([weights[c] for c in CRITERIA])
    drawn = rng.dirichlet(base / base.sum() * w_cfg["concentration"], size=w_cfg["draws"])
    weight_scores = np.column_stack([scores(criteria, dict(zip(CRITERIA, w, strict=True)), cfg).to_numpy() for w in drawn]).T

    level = cfg["uncertainty"]["level"]
    recommendations = []
    for city, block_c in criteria.groupby("ville"):
        index = block_c.index.to_numpy()
        ranked = block_c.sort_values("score", ascending=False)
        first, second = ranked.iloc[0], ranked.iloc[1]
        win_boot = (boot_scores[:, index].argmax(axis=1) == list(index).index(first.name)).mean()
        win_weights = (weight_scores[:, index].argmax(axis=1) == list(index).index(first.name)).mean()
        diff = boot_scores[:, first.name] - boot_scores[:, second.name]
        low, high = np.quantile(diff, [(1 - level) / 2, 1 - (1 - level) / 2])
        tie = bool(win_boot < cfg["uncertainty"]["tie_probability"] or low <= 0)
        ind_city = indicators[indicators["ville"] == city].set_index("technologie")
        a, c = ind_city.loc[first["technologie"]], ind_city.loc[second["technologie"]]
        recommendations.append({
            "ville": city, "pays": first["pays"], "technologie_recommandee": first["technologie"], "score": first["score"],
            "deuxieme_choix": second["technologie"], "score_deuxieme": second["score"],
            "ecart_score": first["score"] - second["score"], "ecart_score_ic95_bas": low, "ecart_score_ic95_haut": high,
            "probabilite_meilleure": win_boot, "robustesse_poids": win_weights, "ex_aequo": tie,
            "front_pareto": ", ".join(pareto_front(block_c, cfg)),
            "justification": (
                f"{first['technologie']} : {a['rendement_annuel_kwh_kwc']:.0f} kWh/kWc/an contre {c['rendement_annuel_kwh_kwc']:.0f} "
                f"pour {second['technologie']} ; erreur de prévision {a['wape_meilleur_ex_ante_pct']:.1f} % contre "
                f"{c['wape_meilleur_ex_ante_pct']:.1f} % ; sensibilité à la température {a['pente_temperature_pct_par_degre']:.2f} %/°C "
                f"contre {c['pente_temperature_pct_par_degre']:.2f} %/°C"
                + (" ; écart dans la marge d'incertitude : ex æquo" if tie else ""))})
    recommendation = pd.DataFrame(recommendations)

    reports.mkdir(parents=True, exist_ok=True)
    indicators.to_csv(reports / "tech_indicators.csv", index=False, float_format="%.6g")
    criteria.to_csv(reports / "tech_scores.csv", index=False, float_format="%.6g")
    recommendation.to_csv(reports / "tech_recommendation.csv", index=False, float_format="%.6g")
    return {"indicators": indicators, "criteria": criteria, "recommendation": recommendation}
