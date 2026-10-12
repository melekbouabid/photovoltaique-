"""Protocole d'évaluation commun à tous les modèles.

- Une **origine** est le dernier jour observé au moment de prévoir. Les origines couvrent tout
  l'échantillon de test : la première est le dernier jour d'apprentissage.
- Depuis chaque origine, chaque modèle prévoit les jours J+1 à J+7.
- **Chaque origine est évaluée.** Le réajustement, lui, n'a lieu que tous les 30 jours : entre
  deux réajustements, le modèle garde ses paramètres mais utilise les observations les plus récentes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from solarvision.config import load_params
from solarvision.data.process import IMPUTED


@dataclass
class CitySeries:
    """Données d'une ville prêtes pour la modélisation (lignes triées par date)."""

    city: str
    frame: pd.DataFrame       # lignes du panel pour cette ville, index 0..n-1
    n_train: int

    @property
    def dates(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.frame["date"])

    @property
    def n(self) -> int:
        return len(self.frame)


def horizons() -> np.ndarray:
    return np.asarray(load_params()["horizons"])


def origins(n: int, n_train: int) -> np.ndarray:
    """Positions des origines : du dernier jour d'apprentissage au dernier jour qui laisse 7 jours à prévoir."""
    return np.arange(n_train - 1, n - int(horizons().max()))


def target_matrix(values: np.ndarray, origin_positions: np.ndarray) -> np.ndarray:
    """Matrice (origines x horizons) des valeurs aux dates cibles."""
    return np.asarray(values)[origin_positions[:, None] + horizons()[None, :]]


def refit_blocks(n_origins: int) -> list[tuple[int, int]]:
    """Tranches d'origines qui partagent le même ajustement (réajustement tous les 30 jours par défaut)."""
    every = load_params()["evaluation"]["refit_every_days"]
    return [(start, min(start + every, n_origins)) for start in range(0, n_origins, every)]


def to_long(series: CitySeries, technology: str, model: str, scenario: str, predicted: np.ndarray,
            lower: np.ndarray | None = None, upper: np.ndarray | None = None) -> pd.DataFrame:
    """Prévisions d'un modèle au format long : une ligne par origine et par horizon."""
    pos = origins(series.n, series.n_train)
    h = horizons()
    target_pos = pos[:, None] + h[None, :]
    observed = series.frame[f"pv_{technology}_kwh_kwc"].to_numpy()[target_pos]
    dates = series.dates.to_numpy()
    shape = target_pos.shape
    nan = np.full(shape, np.nan)
    return pd.DataFrame({
        "ville": series.city, "technologie": technology, "modele": model, "scenario": scenario,
        "origine": np.repeat(dates[pos], shape[1]), "horizon": np.tile(h, shape[0]).astype("int8"),
        "date_cible": dates[target_pos].ravel(), "observation": observed.ravel().astype("float32"),
        "prevision": np.asarray(predicted, float).ravel().astype("float32"),
        "borne_basse": (nan if lower is None else np.asarray(lower, float)).ravel().astype("float32"),
        "borne_haute": (nan if upper is None else np.asarray(upper, float)).ravel().astype("float32"),
        "cible_imputee": series.frame[IMPUTED].to_numpy()[target_pos].ravel().astype("int8"),
    })
