"""Statistiques descriptives et tests de stationnarité, ville par ville, sur l'apprentissage seulement.

Ces tableaux servent au rapport et à la section sur l'IA générative : ce sont les chiffres à fournir
au LLM, pour que chacune de ses affirmations puisse être vérifiée.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from solarvision.config import load_cities, load_params


def city_statistics(frame: pd.DataFrame, n_train: int, technology: str) -> dict:
    """Moments, saisonnalité, persistance et stationnarité d'une ville.

    - ADF : hypothèse nulle = racine unitaire (série non stationnaire). Une petite p-value la rejette.
    - KPSS : hypothèse nulle = série stationnaire. Une petite p-value la rejette.
    Les deux tests se complètent : on conclut à la stationnarité quand l'ADF rejette et que le KPSS ne rejette pas.
    """
    from statsmodels.tsa.stattools import acf, adfuller, kpss

    values = frame[f"pv_{technology}_kwh_kwc"].to_numpy(float)[:n_train]
    anomaly = values - frame[f"normale_{technology}"].to_numpy(float)[:n_train]
    month = pd.DatetimeIndex(frame["date"]).month[:n_train]
    monthly = pd.Series(values).groupby(month).mean()
    out = {"jours_apprentissage": int(n_train), "moyenne": values.mean(), "variance": values.var(ddof=1),
           "ecart_type": values.std(ddof=1), "minimum": values.min(), "maximum": values.max(),
           "skewness": float(stats.skew(values)), "kurtosis_exces": float(stats.kurtosis(values)),
           "mois_le_plus_bas": int(monthly.idxmin()), "moyenne_mois_bas": monthly.min(),
           "mois_le_plus_haut": int(monthly.idxmax()), "moyenne_mois_haut": monthly.max(),
           "rapport_saisonnier": monthly.max() / monthly.min(),
           "part_variance_saisonniere": 1 - anomaly.var() / values.var()}
    correlations = acf(anomaly, nlags=7, fft=True)
    out.update(acf1_ecart_normale=correlations[1], acf2_ecart_normale=correlations[2], acf7_ecart_normale=correlations[7])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                    # le KPSS avertit quand la p-value sort de sa table
        for name, series in (("brute", values), ("ecart_normale", anomaly)):
            adf = adfuller(series, maxlag=30, autolag="AIC")
            k = kpss(series, regression="c", nlags="auto")
            out.update({f"adf_stat_{name}": adf[0], f"adf_p_{name}": adf[1], f"adf_retards_{name}": int(adf[2]),
                        f"kpss_stat_{name}": k[0], f"kpss_p_{name}": k[1]})
    alpha = 0.05
    out["stationnaire_ecart_normale"] = bool(out["adf_p_ecart_normale"] < alpha and out["kpss_p_ecart_normale"] >= alpha)
    return {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in out.items()}


def run(panel: pd.DataFrame, splits: dict, reports: Path) -> pd.DataFrame:
    """Calcule les statistiques de toutes les villes et les écrit dans reports/exploration_stats.csv."""
    technology, cities = load_params()["pv"]["reference_technology"], load_cities()
    rows = []
    for city, frame in panel.groupby("ville"):
        frame = frame.sort_values("date").reset_index(drop=True)
        rows.append({"ville": city, "pays": cities[city].pays, "technologie": technology,
                     **city_statistics(frame, splits[city]["n_train"], technology)})
    table = pd.DataFrame(rows)
    reports.mkdir(parents=True, exist_ok=True)
    table.to_csv(reports / "exploration_stats.csv", index=False, float_format="%.6g")
    return table
