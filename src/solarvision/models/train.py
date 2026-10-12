"""Entraînement et prévision de tous les modèles classiques, ville par ville, avec reprise.

Les prévisions et les observations sont enregistrées date par date (reports/forecasts/<ville>.parquet) :
les métriques et les tests se recalculent ensuite sans réentraîner.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from solarvision.config import DATA, REPORTS, load_params
from solarvision.data.process import IMPUTED
from solarvision.features.panel import load_splits
from solarvision.models import baselines, ml, statistical
from solarvision.models.protocol import CitySeries, origins, to_long

FOURIER = ["fourier_sin_1", "fourier_cos_1", "fourier_sin_2", "fourier_cos_2"]
EX_ANTE, EX_POST = "ex_ante", "ex_post"


def reports_dir(fast: bool) -> Path:
    return REPORTS / "fast" if fast else REPORTS


def data_dir(fast: bool) -> Path:
    return DATA / "fast" if fast else DATA


def load_city(city: str, root: Path) -> CitySeries:
    """Lignes du panel pour une ville, triées par date, et son indice de coupure."""
    frame = pd.read_parquet(root / "processed" / "panel_journalier.parquet", filters=[("ville", "==", city)])
    frame = frame.sort_values("date").reset_index(drop=True)
    return CitySeries(city, frame, load_splits(root)[city]["n_train"])


def run_city(city: str, fast: bool = False, force: bool = False) -> dict:
    """Tous les modèles classiques d'une ville. Renvoie les durées ; ne refait rien si le fichier existe."""
    out = reports_dir(fast) / "forecasts" / f"{city}.parquet"
    if out.exists() and not force:
        return {"ville": city, "statut": "déjà fait"}
    series = load_city(city, data_dir(fast))
    frame, pos = series.frame, origins(series.n, series.n_train)
    reference = load_params()["pv"]["reference_technology"]
    parts, timing, arima_info = [], {}, {}

    def timed(label: str, function):
        t0 = time.time()
        result = function()
        timing[label] = round(timing.get(label, 0) + time.time() - t0, 1)
        return result

    for technology in load_params()["pv"]["technologies"]:
        values = frame[f"pv_{technology}_kwh_kwc"].to_numpy()
        normal = frame[f"normale_{technology}"].to_numpy()
        parts.append(to_long(series, technology, "persistance", EX_ANTE, baselines.persistence(values, pos)))
        parts.append(to_long(series, technology, "climatologie", EX_ANTE, baselines.climatology(normal, pos)))
        parts.append(to_long(series, technology, "xgboost", EX_ANTE,
                             timed("xgboost", lambda t=technology: ml.xgboost_direct(frame, t, pos))))
        if technology != reference:
            continue                                       # les modèles coûteux ne tournent que sur la technologie de référence
        ar = timed("arima_fourier", lambda v=values: statistical.forecast_ar1_regression(v, frame[FOURIER].to_numpy(), pos))
        parts.append(to_long(series, technology, "arima_fourier", EX_ANTE, ar["predicted"], ar["lower"], ar["upper"]))
        arima_info = {"phi_premier": float(ar["phi"][0]), "phi_min": float(ar["phi"].min()), "phi_max": float(ar["phi"].max()),
                      "sigma_premier": float(np.sqrt(ar["sigma2"][0]))}
        pr = timed("prophet", lambda v=values: ml.prophet_forecast(series.dates, v, pos))
        parts.append(to_long(series, technology, "prophet", EX_ANTE, pr["predicted"], pr["lower"], pr["upper"]))
        parts.append(to_long(series, technology, "xgboost_expost", EX_POST,
                             timed("xgboost_expost", lambda t=technology: ml.xgboost_direct(frame, t, pos, ex_post=True))))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    pd.concat(parts, ignore_index=True).to_parquet(tmp, index=False)
    tmp.replace(out)                                       # écriture atomique : un fichier présent est complet
    info = {"ville": city, "statut": "fait", "origines": int(len(pos)), "durees_s": timing, "arima_fourier": arima_info,
            "jours_imputes_apprentissage": int(frame[IMPUTED].iloc[: series.n_train].sum()),
            "jours_imputes_test": int(frame[IMPUTED].iloc[series.n_train:].sum())}
    out.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def train_all(cities: list[str], fast: bool = False, force: bool = False, workers: int = 8) -> list[dict]:
    """Lance les villes en parallèle (un processus par ville). Une ville en échec n'arrête pas les autres."""
    results = []
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(cities)))) as pool:
        futures = {pool.submit(run_city, c, fast, force): c for c in cities}
        for future in as_completed(futures):
            city = futures[future]
            try:
                info = future.result()
            except Exception as err:                       # noqa: BLE001
                info = {"ville": city, "statut": f"échec : {err}"}
            results.append(info)
            print(f"{time.strftime('%H:%M:%S')} {city:12s} {info['statut']} {info.get('durees_s', '')}", flush=True)
    return results


def sensitivity_to_imputed_days(cities: list[str], fast: bool = False) -> pd.DataFrame:
    """Les jours imputés pèsent-ils sur les résultats ? On réestime sans eux et on compare sur le même test.

    Les jours imputés sont tous dans l'apprentissage : la question porte donc sur l'estimation, pas sur
    la mesure de l'erreur. Trois modèles sont réestimés sur la technologie de référence.
    """
    from solarvision.evaluation.metrics import compute_metrics
    from solarvision.features.panel import climatology as seasonal_normal
    from solarvision.models.protocol import target_matrix

    technology, rows = load_params()["pv"]["reference_technology"], []
    for city in cities:
        series = load_city(city, data_dir(fast))
        frame, pos = series.frame, origins(series.n, series.n_train)
        column = f"pv_{technology}_kwh_kwc"
        values, imputed = frame[column].to_numpy(), frame[IMPUTED].to_numpy().astype(bool)
        observed = target_matrix(values, pos)
        # Sans les jours imputés : normale recalculée, AR(1) estimé avec ces jours manquants, lignes retirées pour XGBoost.
        masked = pd.Series(np.where(imputed, np.nan, values), index=series.dates)
        normal_without = seasonal_normal(masked, series.n_train)
        frame_without = frame.assign(**{f"normale_{technology}": normal_without})
        exog = frame[FOURIER].to_numpy()
        variants = {
            "climatologie": (baselines.climatology(frame[f"normale_{technology}"].to_numpy(), pos),
                             baselines.climatology(normal_without, pos)),
            "arima_fourier": (statistical.forecast_ar1_regression(values, exog, pos)["predicted"],
                              statistical.forecast_ar1_regression(values, exog, pos, missing_mask=imputed)["predicted"]),
            "xgboost": (ml.xgboost_direct(frame, technology, pos),
                        ml.xgboost_direct(frame_without, technology, pos, exclude=imputed)),
        }
        for model, (with_days, without_days) in variants.items():
            a, b = compute_metrics(observed, with_days), compute_metrics(observed, without_days)
            rows.append({"ville": city, "technologie": technology, "modele": model, "jours_imputes": int(imputed.sum()),
                         "rmse_avec": a["RMSE"], "rmse_sans": b["RMSE"], "ecart_rmse": b["RMSE"] - a["RMSE"],
                         "mae_avec": a["MAE"], "mae_sans": b["MAE"],
                         "ecart_max_prevision": float(np.max(np.abs(with_days - without_days)))})
    table = pd.DataFrame(rows)
    out = reports_dir(fast)
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "sensitivity_imputed.csv", index=False)
    return table
