"""Suivi : dérive des données et erreur glissante du modèle en production.

Deux questions, posées ville par ville :
1. Les entrées et la cible ont-elles changé de distribution entre l'apprentissage et la période
   récente ? Mesures : indice de stabilité de population (PSI) et test de Kolmogorov-Smirnov.
2. L'erreur du modèle se dégrade-t-elle par rapport à la climatologie quand les observations arrivent ?

Ces statistiques sont celles que calculent les outils de suivi comme Evidently ; elles sont écrites ici
avec numpy et scipy parce qu'Evidently n'est pas installé sur la machine. Tout tourne en local : il n'y
a ni alerte envoyée, ni réentraînement automatique. Les seuils sont dans configs/params.yaml.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from solarvision.config import load_params
from solarvision.evaluation.evaluate import REFERENCE_MODEL

MONITORED = ["pv_crystSi_kwh_kwc", "expost_nebulosite_pct", "expost_t2m_moy_c", "expost_humidite_pct",
             "expost_precipitation_mm", "expost_aerosols_aod", "expost_ghi_nasa_kwh_m2"]


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Indice de stabilité de population : 0 si les deux distributions coïncident.

    Les classes sont les déciles de la référence. Repères usuels : moins de 0,1 stable,
    de 0,1 à 0,25 à surveiller, au-delà de 0,25 dérive marquée.
    """
    reference, current = reference[~np.isnan(reference)], current[~np.isnan(current)]
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:                                     # variable presque constante (pluie souvent nulle) : pas de classes
        return float("nan")
    edges[0], edges[-1] = -np.inf, np.inf
    expected = np.histogram(reference, edges)[0] / len(reference)
    actual = np.histogram(current, edges)[0] / len(current)
    expected, actual = np.clip(expected, 1e-6, None), np.clip(actual, 1e-6, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def data_drift(panel: pd.DataFrame, splits: dict) -> pd.DataFrame:
    """Dérive de chaque variable suivie, par ville, entre l'apprentissage et le test.

    La comparaison se fait sur l'écart à la moyenne du même mois : sinon une période de test qui ne
    couvre pas des années entières ferait passer la saison pour une dérive.
    """
    cfg = load_params()["monitoring"]
    rows = []
    for city, frame in panel.groupby("ville"):
        n_train = splits[city]["n_train"]
        month = pd.DatetimeIndex(frame["date"]).month
        for column in MONITORED:
            values = frame[column].astype(float)
            monthly_mean = values.iloc[:n_train].groupby(month[:n_train]).mean()       # référence : apprentissage seul
            anomaly = (values - monthly_mean.reindex(month).to_numpy()).to_numpy()
            reference, current = anomaly[:n_train], anomaly[n_train:]
            value = psi(reference, current)
            ks = stats.ks_2samp(reference[~np.isnan(reference)], current[~np.isnan(current)])
            level = "indéterminé" if np.isnan(value) else "alerte" if value >= cfg["psi_alert"] else \
                "à surveiller" if value >= cfg["psi_warning"] else "stable"
            rows.append({"ville": city, "variable": column, "psi": value, "ks_stat": float(ks.statistic),
                         "ks_p": float(ks.pvalue), "ecart_moyen": float(np.nanmean(current) - np.nanmean(reference)),
                         "niveau": level})
    return pd.DataFrame(rows)


def rolling_error(forecasts: pd.DataFrame, model: str) -> pd.DataFrame:
    """Erreur du modèle sur 30 jours glissants, rapportée à celle de la climatologie (horizon J+1)."""
    cfg = load_params()["monitoring"]
    reference = load_params()["pv"]["reference_technology"]
    f = forecasts[(forecasts["technologie"] == reference) & (forecasts["horizon"] == 1)
                  & forecasts["modele"].isin([model, REFERENCE_MODEL])]
    sq = f.assign(sq=(f["observation"].astype(float) - f["prevision"].astype(float)) ** 2) \
        .pivot_table(index=["ville", "date_cible"], columns="modele", values="sq")
    rows = []
    for city, block in sq.groupby(level="ville"):
        rolling = np.sqrt(block.droplevel("ville").rolling(cfg["rolling_window_days"]).mean()).dropna()
        ratio = rolling[model] / rolling[REFERENCE_MODEL]
        rows.append(pd.DataFrame({"ville": city, "date": rolling.index, "rmse_modele": rolling[model].to_numpy(),
                                  "rmse_climatologie": rolling[REFERENCE_MODEL].to_numpy(), "ratio": ratio.to_numpy(),
                                  "alerte": (ratio > cfg["error_ratio_alert"]).to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def run(panel: pd.DataFrame, splits: dict, forecasts: pd.DataFrame, model: str, reports: Path) -> dict:
    """Écrit les tableaux de suivi et un résumé des alertes."""
    out = reports / "monitoring"
    out.mkdir(parents=True, exist_ok=True)
    drift, errors = data_drift(panel, splits), rolling_error(forecasts, model)
    drift.to_csv(out / "drift.csv", index=False, float_format="%.6g")
    errors.to_csv(out / "rolling_error.csv", index=False, float_format="%.6g")
    last = errors.sort_values("date").groupby("ville").tail(1)
    summary = {
        "modele_suivi": model, "variables_suivies": MONITORED, "seuils": load_params()["monitoring"],
        "derive": {level: int(n) for level, n in drift["niveau"].value_counts().items()},
        "variables_en_alerte": drift[drift["niveau"] == "alerte"][["ville", "variable", "psi"]].round(3).to_dict("records"),
        "part_des_jours_en_alerte_erreur_pct": float(100 * errors["alerte"].mean()),
        "villes_en_alerte_erreur_en_fin_de_periode": sorted(last[last["alerte"]]["ville"]),
        "limites": "Suivi local, recalculé à la demande ; aucune alerte n'est envoyée et aucun réentraînement n'est automatique.",
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
