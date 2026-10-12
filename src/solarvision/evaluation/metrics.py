"""Métriques de prévision. Toutes prennent les observations puis les prévisions, de même forme."""
from __future__ import annotations

import numpy as np

METRICS = ["MSE", "RMSE", "MAE", "MAPE", "WAPE"]


def compute_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """MSE, RMSE, MAE, MAPE (%) et WAPE (%).

    Le MAPE est gonflé par les journées très couvertes (observation proche de zéro) ; le WAPE,
    somme des erreurs absolues rapportée à la somme des observations, est plus représentatif.
    """
    observed, predicted = np.asarray(observed, float).ravel(), np.asarray(predicted, float).ravel()
    keep = ~(np.isnan(observed) | np.isnan(predicted))
    observed, error = observed[keep], observed[keep] - predicted[keep]
    if observed.size == 0:
        return {m: float("nan") for m in METRICS}
    mse = float(np.mean(error ** 2))
    return {"MSE": mse, "RMSE": float(np.sqrt(mse)), "MAE": float(np.mean(np.abs(error))),
            "MAPE": float(100 * np.mean(np.abs(error) / np.abs(observed))),
            "WAPE": float(100 * np.sum(np.abs(error)) / np.sum(np.abs(observed)))}


def interval_coverage(observed: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Part des observations (en %) qui tombent dans l'intervalle de prévision."""
    observed, lower, upper = (np.asarray(a, float).ravel() for a in (observed, lower, upper))
    keep = ~(np.isnan(observed) | np.isnan(lower) | np.isnan(upper))
    if not keep.any():
        return float("nan")
    return float(100 * np.mean((observed[keep] >= lower[keep]) & (observed[keep] <= upper[keep])))
