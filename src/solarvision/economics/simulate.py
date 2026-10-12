"""Bénéfices économiques par ville et par technologie, avec incertitude (Monte-Carlo).

Toutes les hypothèses viennent de configs/economics.yaml, où elles sont marquées TODO_VERIFY.
Aucun résultat n'est publié sans intervalle. Ce calcul n'est pas un conseil financier.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from solarvision.config import CONFIGS, load_cities, load_params
from solarvision.economics import finance

RESULTS = {"economie_an1_eur": "Économie sur la facture, première année", "revenu_rachat_an1_eur": "Revenu du surplus, première année",
           "temps_retour_ans": "Temps de retour simple", "van_eur": "Valeur actuelle nette sur la durée de vie",
           "tri_pct": "Taux de rentabilité interne", "lcoe_eur_kwh": "Coût actualisé de l'énergie",
           "co2_evite_t": "CO2 évité sur la durée de vie"}


def load_economics_config() -> dict:
    return yaml.safe_load((CONFIGS / "economics.yaml").read_text(encoding="utf-8"))


def triangular(rng: np.random.Generator, bounds: list[float], size: int) -> np.ndarray:
    """Tirage dans une loi triangulaire [basse, centrale, haute] ; valeur fixe si les trois bornes sont égales."""
    low, mode, high = bounds
    return np.full(size, float(mode)) if low == high else rng.triangular(low, mode, high, size)


def cash_flows(yield_kwh_kwp: np.ndarray, p: dict[str, np.ndarray], peak_kwp: float, years: int) -> dict[str, np.ndarray]:
    """Flux annuels d'une installation pour chaque tirage (lignes) et chaque année (colonnes)."""
    t = np.arange(years)[None, :]
    production = yield_kwh_kwp[:, None] * peak_kwp * (1 - p["degradation"][:, None]) ** t        # usure des modules
    growth = (1 + p["inflation"][:, None]) ** t                                                  # hausse du prix de l'électricité
    savings = production * p["self_consumption"][:, None] * p["retail_price"][:, None] * growth
    export = production * (1 - p["self_consumption"][:, None]) * p["export_price"][:, None] * growth
    capex = p["capex_per_kwp"] * p["capex_multiplier"] * peak_kwp
    costs = np.repeat((p["om_share"] * capex)[:, None], years, axis=1)
    return {"production": production, "savings": savings, "export": export, "costs": costs, "capex": capex,
            "net": savings + export - costs}


def indicators(flows: dict[str, np.ndarray], p: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        "economie_an1_eur": flows["savings"][:, 0], "revenu_rachat_an1_eur": flows["export"][:, 0],
        "temps_retour_ans": finance.payback_years(flows["capex"], flows["net"]),
        "van_eur": finance.npv(flows["capex"], flows["net"], p["discount_rate"]),
        "tri_pct": 100 * finance.irr(flows["capex"], flows["net"]),
        "lcoe_eur_kwh": finance.lcoe(flows["capex"], flows["costs"], flows["production"], p["discount_rate"]),
        "co2_evite_t": flows["production"].sum(axis=1) * p["emission_g_kwh"] / 1e6,
    }


def draw_parameters(rng: np.random.Generator, cfg: dict, country: str, technology: str, size: int) -> dict[str, np.ndarray]:
    c, tech = cfg["countries"][country], cfg["technologies"][technology]
    return {
        "self_consumption": triangular(rng, cfg["system"]["self_consumption_share"], size),
        "discount_rate": triangular(rng, cfg["common"]["discount_rate"], size),
        "inflation": triangular(rng, cfg["common"]["energy_price_inflation"], size),
        "om_share": triangular(rng, cfg["common"]["om_cost_share_of_capex"], size),
        "retail_price": triangular(rng, c["retail_price_eur_kwh"], size),
        "export_price": triangular(rng, c["export_price_eur_kwh"], size),
        "capex_per_kwp": triangular(rng, c["capex_eur_per_kwp"], size),
        "emission_g_kwh": triangular(rng, c["grid_emission_g_co2_kwh"], size),
        "capex_multiplier": triangular(rng, tech["capex_multiplier"], size),
        "degradation": triangular(rng, tech["degradation_per_year"], size),
    }


def central_parameters(cfg: dict, country: str, technology: str) -> dict[str, np.ndarray]:
    """Valeurs centrales de chaque hypothèse (un seul « tirage »), pour l'analyse de sensibilité."""
    c, tech = cfg["countries"][country], cfg["technologies"][technology]
    mid = lambda bounds: np.array([float(bounds[1])])     # noqa: E731
    return {"self_consumption": mid(cfg["system"]["self_consumption_share"]), "discount_rate": mid(cfg["common"]["discount_rate"]),
            "inflation": mid(cfg["common"]["energy_price_inflation"]), "om_share": mid(cfg["common"]["om_cost_share_of_capex"]),
            "retail_price": mid(c["retail_price_eur_kwh"]), "export_price": mid(c["export_price_eur_kwh"]),
            "capex_per_kwp": mid(c["capex_eur_per_kwp"]), "emission_g_kwh": mid(c["grid_emission_g_co2_kwh"]),
            "capex_multiplier": mid(tech["capex_multiplier"]), "degradation": mid(tech["degradation_per_year"])}


def _bounds(cfg: dict, country: str, technology: str) -> dict[str, list[float]]:
    c, tech = cfg["countries"][country], cfg["technologies"][technology]
    return {"self_consumption": cfg["system"]["self_consumption_share"], "discount_rate": cfg["common"]["discount_rate"],
            "inflation": cfg["common"]["energy_price_inflation"], "om_share": cfg["common"]["om_cost_share_of_capex"],
            "retail_price": c["retail_price_eur_kwh"], "export_price": c["export_price_eur_kwh"],
            "capex_per_kwp": c["capex_eur_per_kwp"], "capex_multiplier": tech["capex_multiplier"],
            "degradation": tech["degradation_per_year"]}


def run(panel: pd.DataFrame, reports: Path, metrics_wide: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Simule chaque ville et chaque technologie ; écrit les tableaux par ville, le classement et la sensibilité."""
    cfg, params, cities = load_economics_config(), load_params(), load_cities()
    size, years, peak = cfg["monte_carlo"]["draws"], cfg["system"]["lifetime_years"], cfg["system"]["peak_power_kwp"]
    percentiles = cfg["monte_carlo"]["percentiles"]
    dates = pd.DatetimeIndex(panel["date"])
    rows, tornado, van_draws = [], [], {}
    for city, frame in panel.groupby("ville"):
        country = cities[city].pays
        for technology in params["pv"]["technologies"]:
            annual = frame[f"pv_{technology}_kwh_kwc"].groupby(dates[frame.index].year).sum().to_numpy()
            # Mêmes tirages pour toutes les villes et technologies d'un pays : les comparaisons ne dépendent pas du hasard.
            rng = np.random.default_rng([params["seed"], sum(map(ord, country))])
            p = draw_parameters(rng, cfg, country, technology, size)
            # Incertitude sur le productible : moyenne de N années tirées parmi les années observées.
            yields = rng.choice(annual, size=(size, years), replace=True).mean(axis=1)
            result = indicators(cash_flows(yields, p, peak, years), p)
            van_draws[(city, technology)] = result["van_eur"]
            row = {"ville": city, "pays": country, "technologie": technology, "puissance_kwc": peak,
                   "production_kwh_kwc_an": float(annual.mean()), "probabilite_van_positive": float((result["van_eur"] > 0).mean())}
            for name, values in result.items():
                finite = np.where(np.isfinite(values), values, np.nan)
                for q in percentiles:
                    row[f"{name}_p{q}"] = float(np.nanpercentile(finite, q)) if np.isfinite(finite).any() else float("nan")
            row["part_jamais_rembourse"] = float(np.isinf(result["temps_retour_ans"]).mean())
            rows.append(row)
            if technology == params["pv"]["reference_technology"]:
                # Sensibilité : chaque hypothèse passe de sa valeur basse à sa valeur haute, les autres restant centrales.
                central = central_parameters(cfg, country, technology)
                base = indicators(cash_flows(np.array([annual.mean()]), central, peak, years), central)["van_eur"][0]
                for name, (low, _, high) in _bounds(cfg, country, technology).items():
                    out = []
                    for value in (low, high):
                        varied = {**central, name: np.array([float(value)])}
                        out.append(indicators(cash_flows(np.array([annual.mean()]), varied, peak, years), varied)["van_eur"][0])
                    tornado.append({"ville": city, "pays": country, "technologie": technology, "hypothese": name,
                                    "valeur_basse": low, "valeur_haute": high, "van_centrale_eur": base,
                                    "van_valeur_basse_eur": out[0], "van_valeur_haute_eur": out[1],
                                    "amplitude_eur": abs(out[1] - out[0])})
    by_city = pd.DataFrame(rows)
    ranking = []
    for city, block in by_city.groupby("ville"):
        ordered = block.sort_values("van_eur_p50", ascending=False)
        first, second = ordered.iloc[0], ordered.iloc[1]
        # Les tirages sont communs : on peut compter directement la part des scénarios où la première technologie gagne.
        wins = float((van_draws[(city, first["technologie"])] > van_draws[(city, second["technologie"])]).mean())
        ranking.append({"ville": city, "pays": first["pays"], "meilleure_technologie_van": first["technologie"],
                        "van_p10": first["van_eur_p10"], "van_p50": first["van_eur_p50"], "van_p90": first["van_eur_p90"],
                        "temps_retour_p50": first["temps_retour_ans_p50"], "deuxieme": second["technologie"],
                        "van_p50_deuxieme": second["van_eur_p50"], "probabilite_premiere_devant": wins,
                        "ecart_non_concluant": bool(wins < 0.9)})
    ranking = pd.DataFrame(ranking).sort_values("van_p50", ascending=False)
    tornado = pd.DataFrame(tornado)
    reports.mkdir(parents=True, exist_ok=True)
    by_city.to_csv(reports / "economics_by_city.csv", index=False, float_format="%.6g")
    ranking.to_csv(reports / "economics_ranking.csv", index=False, float_format="%.6g")
    tornado.to_csv(reports / "economics_tornado.csv", index=False, float_format="%.6g")
    tables = {"by_city": by_city, "ranking": ranking, "tornado": tornado}
    if metrics_wide is not None:
        tables["forecast_value"] = forecast_value(metrics_wide, cfg, reports)
    return tables


def forecast_value(metrics_wide: pd.DataFrame, cfg: dict, reports: Path) -> pd.DataFrame:
    """Que vaut une meilleure prévision ? Coût annuel des écarts entre le plan et la production réelle.

    Modèle de coût explicite : chaque kWh d'erreur absolue coûte une pénalité. On compare un plan fondé
    sur la climatologie à un plan fondé sur le meilleur modèle ex ante. Si le gain est faible, il est
    affiché tel quel.
    """
    params, cities = load_params(), load_cities()
    peak, size = cfg["system"]["peak_power_kwp"], cfg["monte_carlo"]["draws"]
    penalty = triangular(np.random.default_rng(params["seed"]), cfg["forecast_value"]["imbalance_penalty_eur_kwh"], size)
    m = metrics_wide[(metrics_wide["technologie"] == params["pv"]["reference_technology"]) & (metrics_wide["horizon"] == "tous")
                     & (metrics_wide["scenario"] == "ex_ante")]
    rows = []
    for city, block in m.groupby("ville"):
        mae = block.set_index("modele")["MAE"]
        best = mae.idxmin()
        saved_kwh = (mae["climatologie"] - mae[best]) * peak * 365           # kWh d'erreur évités par an
        gain = saved_kwh * penalty
        rows.append({"ville": city, "pays": cities[city].pays, "meilleur_modele_ex_ante": best,
                     "mae_climatologie": mae["climatologie"], "mae_meilleur": mae[best],
                     "erreur_evitee_kwh_an": saved_kwh,
                     "cout_erreur_climatologie_eur_an_p50": float(np.percentile(mae["climatologie"] * peak * 365 * penalty, 50)),
                     **{f"gain_eur_an_p{q}": float(np.percentile(gain, q)) for q in cfg["monte_carlo"]["percentiles"]}})
    table = pd.DataFrame(rows)
    table.to_csv(reports / "forecast_value.csv", index=False, float_format="%.6g")
    return table
